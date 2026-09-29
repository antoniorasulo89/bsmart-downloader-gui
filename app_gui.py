"""
ScaricaLibri — interfaccia unica per bSmart, Sanoma, Zanichelli,
HUB Young/Kids, MyLim e Hoepli demo.
Porting Python dei downloader di https://github.com/Leone25
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from platforms import PLATFORMS, BY_KEY


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ScaricaLibri — downloader multi-piattaforma")
        self.geometry("700x720")
        self.state = None
        self.books = []
        self.auth_vars = {}
        self.opt_vars = {}
        self._build()

    # ---------- layout ----------
    def _build(self):
        pad = {"padx": 10, "pady": 4}

        f0 = ttk.LabelFrame(self, text="Piattaforma")
        f0.pack(fill="x", **pad)
        self.plat_var = tk.StringVar(value=PLATFORMS[0]["label"])
        self.plat_box = ttk.Combobox(f0, textvariable=self.plat_var,
                                     values=[p["label"] for p in PLATFORMS],
                                     state="readonly", width=40)
        self.plat_box.pack(fill="x", padx=6, pady=6)
        self.plat_box.bind("<<ComboboxSelected>>", lambda _e: self._render_auth())

        self.auth_frame = ttk.LabelFrame(self, text="1. Accedi")
        self.auth_frame.pack(fill="x", **pad)

        f2 = ttk.LabelFrame(self, text="2. Scegli il libro")
        f2.pack(fill="both", expand=True, **pad)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_books())
        self.search_entry = ttk.Entry(f2, textvariable=self.search_var, width=40)
        self.search_entry.pack(anchor="w", padx=6, pady=2)
        self.book_list = tk.Listbox(f2, height=9)
        self.book_list.pack(fill="both", expand=True, padx=6, pady=4)
        self.book_list.bind("<<ListboxSelect>>", self._on_select)
        row = ttk.Frame(f2)
        row.pack(fill="x", padx=6, pady=2)
        self.id_label = ttk.Label(row, text="ID libro:")
        self.id_label.pack(side="left")
        self.book_id_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.book_id_var, width=30).pack(side="left", padx=6)
        self.id_help_btn = ttk.Button(row, text="?", width=3, command=self._id_help)
        self.id_help_btn.pack(side="left")

        f3 = ttk.LabelFrame(self, text="3. Scarica")
        f3.pack(fill="x", **pad)
        r3 = ttk.Frame(f3)
        r3.pack(fill="x", padx=6, pady=2)
        ttk.Label(r3, text="Cartella:").pack(side="left")
        self.out_var = tk.StringVar(value=os.getcwd())
        ttk.Entry(r3, textvariable=self.out_var, width=40).pack(side="left", padx=6, expand=True, fill="x")
        ttk.Button(r3, text="Sfoglia…", command=self._browse).pack(side="left")
        self.opt_frame = ttk.Frame(f3)
        self.opt_frame.pack(fill="x", padx=6)
        self._render_opts()
        self.dl_btn = ttk.Button(f3, text="⬇  SCARICA", command=self._download_thread)
        self.dl_btn.pack(fill="x", padx=6, pady=6)
        self.prog = ttk.Progressbar(f3, mode="determinate", maximum=100)
        self.prog.pack(fill="x", padx=6, pady=2)
        self.status_var = tk.StringVar(value="Pronto. Scegli la piattaforma e accedi.")
        ttk.Label(f3, textvariable=self.status_var).pack(anchor="w", padx=6)

        self.log = tk.Text(self, height=7, state="disabled")
        self.log.pack(fill="both", expand=False, **pad)
        self._render_auth()

    def _entry(self):
        return BY_KEY[[k for k, p in BY_KEY.items() if p["label"] == self.plat_var.get()][0]]

    def _render_auth(self):
        for w in self.auth_frame.winfo_children():
            w.destroy()
        self.auth_vars = {}
        e = self._entry()
        mod = e["mod"]
        if not mod.NEEDS_LOGIN:
            ttk.Label(self.auth_frame, text="Nessun login richiesto per questa piattaforma.").pack(
                anchor="w", padx=6, pady=6)
            self._render_opts()
            self._render_id()
            return
        if getattr(mod, "AUTH_HELP", None):
            ttk.Label(self.auth_frame, text=mod.AUTH_HELP, justify="left").pack(anchor="w", padx=6, pady=2)
        for key, label, is_pw, req in mod.AUTH_FIELDS:
            ttk.Label(self.auth_frame, text=label + ("" if req else " (facoltativo)") + ":").pack(
                anchor="w", padx=6)
            var = tk.StringVar()
            ttk.Entry(self.auth_frame, textvariable=var, width=50,
                      show="•" if is_pw else "").pack(fill="x", padx=6, pady=2)
            self.auth_vars[key] = var
        ttk.Button(self.auth_frame, text="ACCEDI E CARICA I LIBRI",
                   command=self._load_books_thread).pack(fill="x", padx=6, pady=6)
        self._render_opts()
        self._render_id()

    def _render_opts(self):
        for w in self.opt_frame.winfo_children():
            w.destroy()
        self.opt_vars = {}
        for key, label, default in self._entry()["mod"].OPTIONS:
            var = tk.BooleanVar(value=default)
            ttk.Checkbutton(self.opt_frame, text=label, variable=var).pack(anchor="w")
            self.opt_vars[key] = var

    def _render_id(self):
        mod = self._entry()["mod"]
        self.id_label.config(text=mod.ID_LABEL + ":")
        self.book_list.delete(0, "end")
        self.books = []
        self.book_id_var.set("")

    # ---------- helpers ----------
    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _set_status(self, msg, pct=None):
        try:
            self.status_var.set(msg)
            if pct is not None:
                self.prog["value"] = pct
            self.update_idletasks()
        except tk.TclError:
            pass

    def _id_help(self):
        m = self._entry()["mod"]
        messagebox.showinfo(m.ID_LABEL, getattr(m, "ID_HELP", ""))

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
            if q in f"{b['id']} {b['title']}".lower():
                label = f"{b['id']} — {b['title']}"
                if b.get("ok") is False:
                    label += " (non scaricabile)"
                self.book_list.insert("end", label)

    def _on_select(self, _evt=None):
        sel = self.book_list.curselection()
        if sel:
            self.book_id_var.set(self.book_list.get(sel[0]).split(" — ")[0])

    def _progress(self, done, total, msg):
        pct = (done / total * 100) if total else 0
        self.after(0, lambda: self._set_status(msg, pct))

    # ---------- rete ----------
    def _load_books_thread(self):
        threading.Thread(target=self._load_books, daemon=True).start()

    def _load_books(self):
        e = self._entry()
        mod = e["mod"]
        creds = {"_site": e["site"]}
        for key, label, _pw, req in mod.AUTH_FIELDS:
            v = self.auth_vars[key].get().strip()
            if req and not v:
                messagebox.showwarning("Dati mancanti", f"Inserisci: {label}")
                return
            creds[key] = v
        label = e["label"]
        self._set_status("Accesso in corso…", 0)
        self._log(f"[{label}] login…")
        try:
            self.state = mod.login(creds)
            user = self.state.get("username")
            if user:
                self._log(f"Ciao {user}!")
            if mod.NEEDS_LIST:
                self._log("Carico i libri…")
                self.books = mod.list_books(self.state)
                for line in (self.state.get("_debug") or []):
                    self._log(f"[diagnostica] {line}")
                self._log(f"Trovati {len(self.books)} libri.")
                self.after(0, self._filter_books)
                self._set_status(f"Trovati {len(self.books)} libri. Scegli e scarica.", 0)
            else:
                self.books = mod.list_books(self.state)
                if self.books:
                    self.after(0, lambda: self.book_id_var.set(self.books[0]["id"]))
                self._set_status("Pronto per il download.", 0)
        except Exception as ex:
            self._log(f"ERRORE: {ex}")
            self._set_status("Errore. Vedi log.")
            messagebox.showerror("Errore", str(ex))

    def _download_thread(self):
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        e = self._entry()
        mod = e["mod"]
        if mod.NEEDS_LOGIN and not self.state:
            messagebox.showwarning("Non connesso", "Prima premi 'ACCEDI E CARICA I LIBRI'.")
            return
        state = self.state or mod.login({})
        book_id = self.book_id_var.get().strip()
        if not book_id:
            messagebox.showwarning("Dato mancante", f"Inserisci: {mod.ID_LABEL}")
            return
        opts = {k: v.get() for k, v in self.opt_vars.items()}
        self.dl_btn.config(state="disabled")
        try:
            path = mod.download(state, book_id, self.out_var.get(), opts, self._progress)
            self._log(f"Fatto! Salvato in: {path}")
            messagebox.showinfo("Completato", f"Salvato in:\n{path}")
        except Exception as ex:
            self._log(f"ERRORE: {ex}")
            self._set_status("Errore. Vedi log.")
            messagebox.showerror("Errore download", str(ex))
        finally:
            self.dl_btn.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
