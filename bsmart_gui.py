"""
bSmart-downloader GUI
Interfaccia grafica facile per il progetto https://github.com/Leone25/bSmart-downloader
Replica in Python la logica di index.js + src/api.js + src/crypto.js
"""

import base64
import io
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor

import requests
import msgpack
from Crypto.Cipher import AES


SITES = {
    "bSmart": "www.bsmart.it",
    "digibook24 (EdiErmes)": "web.digibook24.com",
}

HEADERS_UA = {"User-Agent": "Mozilla/5.0"}


# ---------- logica di rete (porting da src/api.js) ----------

class LoginError(RuntimeError):
    pass


def login_with_credentials(email, password):
    """Fa login su www.bsmart.it con email+password e restituisce il cookie _bsw_session_v1_production.

    Replica il form Devise di /users/sign_in (testato: errore 'Email o password non validi').
    Solleva LoginError in caso di credenziali errate.
    """
    s = requests.Session()
    s.headers.update(HEADERS_UA)
    r = s.get("https://www.bsmart.it/users/sign_in", timeout=20)
    if r.status_code != 200:
        raise LoginError("Sito bSmart non raggiungibile. Riprova più tardi.")
    m = re.search(r'id="new_user".*?authenticity_token" value="([^"]+)"', r.text, re.S)
    if not m:
        raise LoginError("Pagina di login cambiata: usa il metodo cookie manuale.")
    data = {
        "authenticity_token": m.group(1),
        "user[email]": email,
        "user[password]": password,
        "user[remember_me]": "0",
        "commit": "Accedi",
    }
    p = s.post("https://www.bsmart.it/users/sign_in", data=data, timeout=20)
    low = p.text.lower()
    if "email o password non validi" in low or "invalid" in low and "sign_in" in p.url:
        raise LoginError("Email o password non validi.")
    if "/users/sign_in" in p.url and 'id="new_user"' in p.text:
        raise LoginError("Login non riuscito (controlla email/password o eventuale CAPTCHA).")
    cookie = s.cookies.get("_bsw_session_v1_production")
    if not cookie:
        raise LoginError("Login riuscito ma cookie non trovato: usa il metodo cookie manuale.")
    return cookie


def get_user_info(base_site, cookie):
    r = requests.get(
        f"https://{base_site}/api/v5/user",
        headers={**HEADERS_UA, "cookie": f"_bsw_session_v1_production={cookie}"},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError("Cookie non valida (errore 401/altro). Ricopia il cookie _bsw_session_v1_production.")
    return r.json()


def get_books(base_site, headers):
    h = {**HEADERS_UA, **headers}
    books = requests.get(
        f"https://{base_site}/api/v6/books?page_thumb_size=medium&per_page=25000",
        headers=h, timeout=20,
    ).json()
    preatt = requests.get(f"https://{base_site}/api/v5/books/preactivations", headers=h, timeout=20).json()
    for p in preatt:
        if p.get("no_bsmart") is False:
            books.extend(p.get("books", []))
    seen = set()
    out = []
    for b in books:
        if b["id"] in seen:
            continue
        seen.add(b["id"])
        out.append(b)
    return out


def get_book_info(base_site, book_id, headers):
    h = {**HEADERS_UA, **headers}
    r = requests.get(f"https://{base_site}/api/v6/books/by_book_id/{book_id}", headers=h, timeout=20)
    if r.status_code != 200:
        raise RuntimeError("ID libro non valido.")
    return r.json()


def get_book_resources(base_site, book, headers):
    h = {**HEADERS_UA, **headers}
    info = []
    page = 1
    while True:
        r = requests.get(
            f"https://{base_site}/api/v5/books/{book['id']}/{book['current_edition']['revision']}/resources?per_page=500&page={page}",
            headers=h, timeout=20,
        ).json()
        info.extend(r)
        if len(r) < 500:
            break
        page += 1
    return info


# ---------- crypto (porting da src/crypto.js) ----------

def fetch_encryption_key():
    page = requests.get("https://my.bsmart.it/", headers=HEADERS_UA, timeout=20).text
    scripts = [m for m in re.findall(r'<script[^>]+src="([^"]+\.js[^"]*)"[^>]*>', page) if m.startswith("/")]
    if not scripts:
        raise RuntimeError("Impossibile trovare la chiave di cifratura (nessun bundle JS).")
    pattern = re.compile(
        r'var\s+([A-Za-z_$\.][\w$]*)=String\.fromCharCode\(([^)]*)\),([A-Za-z_$][\w$]*)=["\']constructor["\'];\3\[\3\]\[\3\]\((.*?)\)\(\)',
        re.S,
    )
    for script in scripts:
        txt = requests.get("https://my.bsmart.it" + script, headers=HEADERS_UA, timeout=20).text
        m = pattern.search(txt)
        if not m:
            continue
        char_var, char_codes, _, expression = m.group(1), m.group(2), m.group(3), m.group(4)
        chars = [chr(int(e.strip())) for e in char_codes.split(",")]
        idxs = [int(x) for x in re.findall(re.escape(char_var) + r"\[(\d+)\]", expression)]
        if not idxs:
            continue
        snippet = "".join(chars[i] for i in idxs if 0 <= i < len(chars))
        km = re.search(r'[\'"]([A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?[\'"]', snippet)
        # cerca stringa base64 valida da 16 byte (24 char con =)
        candidates = re.findall(r'[\'"]([A-Za-z0-9+/]{20,}={0,2})[\'"]', snippet)
        for c in candidates:
            try:
                key = base64.b64decode(c)
                if len(key) == 16:
                    return key
            except Exception:
                continue
        if km:
            try:
                return base64.b64decode(km.group(0).strip('\'"'))
            except Exception:
                pass
    raise RuntimeError("Impossibile estrarre la chiave di cifratura dal sito bSmart.")


def decrypt_file(data: bytes, key: bytes) -> bytes:
    unpacker = msgpack.Unpacker(raw=False)
    unpacker.feed(data[:256])
    header = unpacker.unpack()
    start = header["start"] if isinstance(header, dict) else header[0]
    first_part = data[256:start]
    second_part = data[start:]
    iv = first_part[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    dec = cipher.decrypt(first_part[16:])
    # rimuovi padding PKCS#7
    pad = dec[-1]
    if 1 <= pad <= 16 and all(b == pad for b in dec[-pad:]):
        dec = dec[:-pad]
    return bytes(dec) + bytes(second_part)


def sanitize(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()[:150]


# ---------- GUI ----------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("bSmart Downloader - interfaccia facile")
        self.geometry("680x700")
        self.resizable(True, True)
        self.books = []
        self.headers = None
        self.base_site = None
        self._build()

    def _build(self):
        pad = {"padx": 10, "pady": 4}

        # 1. Login
        f1 = ttk.LabelFrame(self, text="1. Accedi con email e password bSmart")
        f1.pack(fill="x", **pad)
        ttk.Label(f1, text="Sito:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.site_var = tk.StringVar(value="bSmart")
        ttk.Combobox(f1, textvariable=self.site_var, values=list(SITES.keys()),
                     state="readonly", width=28).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(f1, text="Email:").grid(row=1, column=0, sticky="w", padx=6)
        self.email_var = tk.StringVar()
        ttk.Entry(f1, textvariable=self.email_var, width=40).grid(row=1, column=1, columnspan=2, sticky="ew", padx=6, pady=2)

        ttk.Label(f1, text="Password:").grid(row=2, column=0, sticky="w", padx=6)
        self.pw_var = tk.StringVar()
        self.pw_entry = ttk.Entry(f1, textvariable=self.pw_var, width=40, show="•")
        self.pw_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=2)
        self.pw_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(f1, text="mostra", variable=self.pw_show,
                        command=lambda: self.pw_entry.config(show="" if self.pw_show.get() else "•")).grid(row=2, column=2, padx=4)
        f1.columnconfigure(1, weight=1)
        ttk.Button(f1, text="2. ACCEDI E CARICA I MIEI LIBRI", command=self._load_books_thread).grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=6)

        # accesso manuale con cookie (solo per Google/Microsoft/ELI)
        self.manual_frame = ttk.LabelFrame(self, text="Avanzato: hai login con Google/Microsoft? Usa il cookie manuale")
        self.manual_frame.pack(fill="x", **pad)
        ttk.Label(self.manual_frame, text="Cookie _bsw_session_v1_production:").pack(anchor="w", padx=6)
        man_row = ttk.Frame(self.manual_frame)
        man_row.pack(fill="x", padx=6, pady=2)
        self.cookie_var = tk.StringVar()
        self.cookie_entry = ttk.Entry(man_row, textvariable=self.cookie_var, width=40, show="•")
        self.cookie_entry.pack(side="left", expand=True, fill="x")
        ttk.Button(man_row, text="?", width=3, command=self._help_cookie).pack(side="left", padx=4)

        # 2. Libri
        f2 = ttk.LabelFrame(self, text="2. Scegli il libro")
        f2.pack(fill="both", expand=True, **pad)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_books())
        ttk.Entry(f2, textvariable=self.search_var, width=40).pack(anchor="w", padx=6, pady=2)
        self.search_var.set("")
        # placeholder semplice
        self.book_list = tk.Listbox(f2, height=10)
        self.book_list.pack(fill="both", expand=True, padx=6, pady=4)
        self.book_list.bind("<<ListboxSelect>>", self._on_select)
        row = ttk.Frame(f2)
        row.pack(fill="x", padx=6, pady=2)
        ttk.Label(row, text="ID libro:").pack(side="left")
        self.book_id_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.book_id_var, width=12).pack(side="left", padx=6)
        ttk.Label(row, text="(oppure seleziona dalla lista)").pack(side="left")

        # 3. Download
        f3 = ttk.LabelFrame(self, text="3. Scarica")
        f3.pack(fill="x", **pad)
        r3 = ttk.Frame(f3)
        r3.pack(fill="x", padx=6, pady=2)
        ttk.Label(r3, text="Cartella:").pack(side="left")
        self.out_var = tk.StringVar(value=os.getcwd())
        ttk.Entry(r3, textvariable=self.out_var, width=45).pack(side="left", padx=6, expand=True, fill="x")
        ttk.Button(r3, text="Sfoglia…", command=self._browse).pack(side="left")
        self.res_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f3, text="Scarica allegati invece del libro", variable=self.res_var).pack(anchor="w", padx=6)
        self.dl_btn = ttk.Button(f3, text="⬇  SCARICA PDF", command=self._download_thread)
        self.dl_btn.pack(fill="x", padx=6, pady=6)
        self.prog = ttk.Progressbar(f3, mode="determinate", maximum=100)
        self.prog.pack(fill="x", padx=6, pady=2)
        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(f3, textvariable=self.status_var).pack(anchor="w", padx=6)

        # log
        self.log = tk.Text(self, height=8, state="disabled")
        self.log.pack(fill="both", expand=False, **pad)

    # ----- helpers -----
    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _set_status(self, msg, pct=None):
        self.status_var.set(msg)
        if pct is not None:
            self.prog["value"] = pct
        self.update_idletasks()

    def _help_cookie(self):
        messagebox.showinfo(
            "Cookie manuale (solo Google/Microsoft/ELI)",
            "Serve SOLO se accedi con Google, Microsoft o account editore.\n\n"
            "1. Apri my.bsmart.it nel browser e fai login\n"
            "2. Premi F12 → Archiviazione/Applicazione → Cookie\n"
            "3. Copia il valore di _bsw_session_v1_production\n"
            "4. Incollalo nel campo 'Avanzato' (senza virgolette)",
        )

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get())
        if d:
            self.out_var.set(d)

    def _filter_books(self):
        if not hasattr(self, "book_list"):
            return
        q = self.search_var.get().lower()
        self.book_list.delete(0, "end")
        for b in self.books:
            label = f"{b['id']} — {b.get('title', '?')}"
            if q in label.lower():
                self.book_list.insert("end", label)

    def _on_select(self, _evt=None):
        sel = self.book_list.curselection()
        if sel:
            self.book_id_var.set(self.book_list.get(sel[0]).split(" — ")[0])

    # ----- rete -----
    def _load_books_thread(self):
        threading.Thread(target=self._load_books, daemon=True).start()

    def _load_books(self):
        manual_cookie = self.cookie_var.get().strip().strip('"').strip("'")
        email = self.email_var.get().strip()
        password = self.pw_var.get()
        if not manual_cookie and (not email or not password):
            messagebox.showwarning("Dati mancanti", "Inserisci email e password, oppure il cookie manuale.")
            return
        self.base_site = SITES[self.site_var.get()]
        self._set_status("Accesso in corso…")
        try:
            if manual_cookie:
                cookie = manual_cookie
                self._log("Uso cookie manuale…")
            else:
                self._log("Login con email e password…")
                cookie = login_with_credentials(email, password)
                self._log("Login riuscito!")
            self._log(f"Connessione a {self.base_site}…")
            user = get_user_info(self.base_site, cookie)
            self.headers = {"auth_token": user["auth_token"]}
            self._log(f"Ciao {user.get('name', user.get('email', '?'))}! Carico i libri…")
            self.books = get_books(self.base_site, self.headers)
            if not self.books:
                self._log("Nessun libro trovato nella libreria.")
            else:
                self._log(f"Trovati {len(self.books)} libri.")
            self.after(0, self._filter_books)
            self._set_status(f"Trovati {len(self.books)} libri. Scegli l'ID.", 0)
        except Exception as e:
            self._log(f"ERRORE: {e}")
            self._set_status("Errore di accesso. Controlla il cookie.")
            messagebox.showerror("Errore", str(e))

    def _download_thread(self):
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        if not self.headers:
            messagebox.showwarning("Non connesso", "Prima premi 'Accedi e carica i miei libri'.")
            return
        book_id = self.book_id_var.get().strip()
        if not book_id:
            messagebox.showwarning("ID mancante", "Inserisci o seleziona l'ID del libro.")
            return
        self.dl_btn.config(state="disabled")
        try:
            self._set_status("Leggo info libro…")
            book = get_book_info(self.base_site, book_id, self.headers)
            info = get_book_resources(self.base_site, book, self.headers)
            assets = [a for r in info for a in r.get("assets", [])]
            key = fetch_encryption_key()
            self._log("Chiave di cifratura ottenuta.")
            if self.res_var.get():
                assets = [a for a in assets if a.get("use") == "launch_file"]
                mode = "allegati"
            else:
                assets = [a for a in assets if a.get("use") == "page_pdf"]
                mode = "pagine"
            if not assets:
                raise RuntimeError("Nessun contenuto trovato per questo libro.")
            self._log(f"Scarico {len(assets)} {mode}…")
            out_base = sanitize(f"{book.get('id', book_id)} - {book.get('title', book_id)}")
            out_dir = self.out_var.get()

            datas = [None] * len(assets)

            def job(i, asset):
                r = requests.get(asset["url"], headers=HEADERS_UA, timeout=30)
                r.raise_for_status()
                data = r.content
                if asset.get("encrypted", True) is not False:
                    data = decrypt_file(data, key)
                return i, bytes(data)

            done = {"n": 0}
            with ThreadPoolExecutor(max_workers=4) as ex:
                futs = [ex.submit(job, i, a) for i, a in enumerate(assets)]
                for f in futs:
                    i, data = f.result()
                    datas[i] = data
                    done["n"] += 1
                    pct = done["n"] / len(assets) * (90 if not self.res_var.get() else 100)
                    self.after(0, lambda p=pct, n=done["n"]: self._set_status(f"Scaricati {n}/{len(assets)}…", p))

            if self.res_var.get():
                folder = os.path.join(out_dir, out_base)
                os.makedirs(folder, exist_ok=True)
                for i, a in enumerate(assets):
                    fname = os.path.basename(a.get("filename", f"file_{i}"))
                    with open(os.path.join(folder, fname), "wb") as fh:
                        fh.write(datas[i])
                self._set_status("Allegati salvati.", 100)
                self._log(f"Fatto! Cartella: {folder}")
            else:
                from pypdf import PdfReader, PdfWriter
                writer = PdfWriter()
                for i, data in enumerate(datas):
                    reader = PdfReader(io.BytesIO(data))
                    writer.add_page(reader.pages[0])
                    self.after(0, lambda p=90 + (i + 1) / len(datas) * 10:
                               self._set_status(f"Unisco pagina {i + 1}/{len(datas)}…", p))
                out_pdf = os.path.join(out_dir, out_base + ".pdf")
                with open(out_pdf, "wb") as fh:
                    writer.write(fh)
                self._set_status("PDF salvato!", 100)
                self._log(f"Fatto! File: {out_pdf}")
                messagebox.showinfo("Completato", f"Libro salvato in:\n{out_pdf}")
        except Exception as e:
            self._log(f"ERRORE: {e}")
            messagebox.showerror("Errore download", str(e))
            self._set_status("Errore. Vedi log.")
        finally:
            self.dl_btn.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
