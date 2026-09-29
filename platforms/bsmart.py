"""bSmart + digibook24 (porting di Leone25/bSmart-downloader)."""
import base64
import io
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import msgpack
from Crypto.Cipher import AES

from .common import LoginError, sanitize, UA_SIMPLE

LABEL = "bSmart / digibook24"
AUTH_FIELDS = [
    ("email", "Email", False, True),
    ("password", "Password", True, True),
    ("cookie", "Cookie manuale (solo se entri con Google/Microsoft)", False, False),
]
AUTH_HELP = (
    "Accedi con email e password bSmart.\n"
    "Se entri con Google/Microsoft, incolla invece il cookie manuale "
    "_bsw_session_v1_production (F12 → Cookie)."
)
ID_LABEL = "ID libro"
ID_HELP = "L'ID numerico dopo /books/ nell'URL, oppure selezionalo dalla lista."
OPTIONS = [("resources", "Scarica allegati invece del libro", False)]
SITES = {"bsmart": "www.bsmart.it", "digibook24": "web.digibook24.com"}

NEEDS_LOGIN = True
NEEDS_LIST = True


# ---------- login ----------

def login_with_credentials(email, password):
    s = requests.Session()
    s.headers.update(UA_SIMPLE)
    r = s.get("https://www.bsmart.it/users/sign_in", timeout=20)
    if r.status_code != 200:
        raise LoginError("Sito bSmart non raggiungibile. Riprova più tardi.")
    m = re.search(r'id="new_user".*?authenticity_token" value="([^"]+)"', r.text, re.S)
    if not m:
        raise LoginError("Pagina di login cambiata: usa il cookie manuale.")
    data = {
        "authenticity_token": m.group(1),
        "user[email]": email,
        "user[password]": password,
        "user[remember_me]": "0",
        "commit": "Accedi",
    }
    p = s.post("https://www.bsmart.it/users/sign_in", data=data, timeout=20)
    low = p.text.lower()
    if "email o password non validi" in low:
        raise LoginError("Email o password non validi.")
    if "/users/sign_in" in p.url and 'id="new_user"' in p.text:
        raise LoginError("Login non riuscito (controlla email/password).")
    cookie = s.cookies.get("_bsw_session_v1_production")
    if not cookie:
        raise LoginError("Login riuscito ma cookie non trovato: usa il cookie manuale.")
    return cookie


def login(creds):
    site = creds.get("_site", "bsmart")
    base = SITES[site]
    cookie = (creds.get("cookie") or "").strip().strip('"').strip("'")
    if not cookie:
        cookie = login_with_credentials(creds["email"].strip(), creds["password"])
    return {"base": base, "cookie": cookie}


# ---------- api (porting di src/api.js) ----------

def get_user_info(base, cookie):
    r = requests.get(
        f"https://{base}/api/v5/user",
        headers={**UA_SIMPLE, "cookie": f"_bsw_session_v1_production={cookie}"},
        timeout=20,
    )
    if r.status_code != 200:
        raise LoginError("Cookie/sessione non valida. Riprova il login.")
    return r.json()


def get_books(base, headers):
    h = {**UA_SIMPLE, **headers}
    books = requests.get(
        f"https://{base}/api/v6/books?page_thumb_size=medium&per_page=25000",
        headers=h, timeout=20,
    ).json()
    preatt = requests.get(f"https://{base}/api/v5/books/preactivations", headers=h, timeout=20).json()
    for p in preatt:
        if p.get("no_bsmart") is False:
            books.extend(p.get("books", []))
    seen, out = set(), []
    for b in books:
        if b["id"] in seen:
            continue
        seen.add(b["id"])
        out.append(b)
    return out


def get_book_info(base, book_id, headers):
    r = requests.get(f"https://{base}/api/v6/books/by_book_id/{book_id}",
                     headers={**UA_SIMPLE, **headers}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError("ID libro non valido.")
    return r.json()


def get_book_resources(base, book, headers):
    h = {**UA_SIMPLE, **headers}
    info, page = [], 1
    while True:
        r = requests.get(
            f"https://{base}/api/v5/books/{book['id']}/{book['current_edition']['revision']}/resources?per_page=500&page={page}",
            headers=h, timeout=20,
        ).json()
        info.extend(r)
        if len(r) < 500:
            break
        page += 1
    return info


# ---------- crypto (porting di src/crypto.js) ----------

def fetch_encryption_key():
    page = requests.get("https://my.bsmart.it/", headers=UA_SIMPLE, timeout=20).text
    scripts = [m for m in re.findall(r'<script[^>]+src="([^"]+\.js[^"]*)"[^>]*>', page) if m.startswith("/")]
    if not scripts:
        raise RuntimeError("Impossibile trovare la chiave di cifratura.")
    pattern = re.compile(
        r'var\s+([A-Za-z_$\.][\w$]*)=String\.fromCharCode\(([^)]*)\),([A-Za-z_$][\w$]*)=["\']constructor["\'];\3\[\3\]\[\3\]\((.*?)\)\(\)',
        re.S,
    )
    for script in scripts:
        txt = requests.get("https://my.bsmart.it" + script, headers=UA_SIMPLE, timeout=20).text
        m = pattern.search(txt)
        if not m:
            continue
        char_var, char_codes, _, expression = m.group(1), m.group(2), m.group(3), m.group(4)
        chars = [chr(int(e.strip())) for e in char_codes.split(",")]
        idxs = [int(x) for x in re.findall(re.escape(char_var) + r"\[(\d+)\]", expression)]
        if not idxs:
            continue
        snippet = "".join(chars[i] for i in idxs if 0 <= i < len(chars))
        for c in re.findall(r'[\'"]([A-Za-z0-9+/]{20,}={0,2})[\'"]', snippet):
            try:
                key = base64.b64decode(c)
                if len(key) == 16:
                    return key
            except Exception:
                continue
    raise RuntimeError("Impossibile estrarre la chiave di cifratura dal sito bSmart.")


def decrypt_file(data: bytes, key: bytes) -> bytes:
    unpacker = msgpack.Unpacker(raw=False)
    unpacker.feed(data[:256])
    header = unpacker.unpack()
    start = header["start"] if isinstance(header, dict) else header[0]
    first_part = data[256:start]
    second_part = data[start:]
    cipher = AES.new(key, AES.MODE_CBC, first_part[:16])
    dec = cipher.decrypt(first_part[16:])
    pad = dec[-1]
    if 1 <= pad <= 16 and all(b == pad for b in dec[-pad:]):
        dec = dec[:-pad]
    return bytes(dec) + bytes(second_part)


# ---------- interfaccia standard ----------

def list_books(state):
    user = get_user_info(state["base"], state["cookie"])
    state["headers"] = {"auth_token": user["auth_token"]}
    state["username"] = user.get("name") or user.get("email") or "?"
    books = get_books(state["base"], state["headers"])
    return [{"id": str(b["id"]), "title": b.get("title", "?")} for b in books]


def download(state, book_id, out_dir, options, progress):
    from pypdf import PdfReader, PdfWriter

    base, headers = state["base"], state["headers"]
    progress(0, 1, "Leggo info libro…")
    book = get_book_info(base, book_id.strip(), headers)
    info = get_book_resources(base, book, headers)
    assets = [a for r in info for a in r.get("assets", [])]
    progress(0, 1, "Recupero chiave di cifratura…")
    key = fetch_encryption_key()

    if options.get("resources"):
        assets = [a for a in assets if a.get("use") == "launch_file"]
    else:
        assets = [a for a in assets if a.get("use") == "page_pdf"]
    if not assets:
        raise RuntimeError("Nessun contenuto trovato per questo libro.")

    datas = [None] * len(assets)
    lock = threading.Lock()
    done = {"n": 0}

    def job(i, asset):
        r = requests.get(asset["url"], headers=UA_SIMPLE, timeout=30)
        r.raise_for_status()
        data = r.content
        if asset.get("encrypted", True) is not False:
            data = decrypt_file(data, key)
        with lock:
            done["n"] += 1
            progress(done["n"], len(assets), f"Scaricate {done['n']}/{len(assets)} pagine…")
        return bytes(data)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(job, i, a) for i, a in enumerate(assets)]
        for i, f in enumerate(futs):
            datas[i] = f.result()

    out_base = sanitize(f"{book.get('id', book_id)} - {book.get('title', book_id)}")
    if options.get("resources"):
        folder = os.path.join(out_dir, out_base)
        os.makedirs(folder, exist_ok=True)
        for i, a in enumerate(assets):
            with open(os.path.join(folder, os.path.basename(a.get("filename", f"file_{i}"))), "wb") as fh:
                fh.write(datas[i])
        progress(1, 1, "Allegati salvati.")
        return folder

    writer = PdfWriter()
    for i, data in enumerate(datas):
        reader = PdfReader(io.BytesIO(data))
        writer.add_page(reader.pages[0])
        progress(i + 1, len(datas), f"Unisco pagina {i + 1}/{len(datas)}…")
    out_pdf = os.path.join(out_dir, out_base + ".pdf")
    with open(out_pdf, "wb") as fh:
        writer.write(fh)
    progress(1, 1, "PDF salvato!")
    return out_pdf
