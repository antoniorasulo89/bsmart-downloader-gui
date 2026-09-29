"""Sanoma (porting di Leone25/sanoma-downloader).

Login con email+password, download dello ZIP, estrazione delle pagine SVG
e conversione in PDF con PyMuPDF (niente Inkscape richiesto).
"""
import io
import os
import re
import tempfile
import zipfile

import fitz
import requests

from .common import LoginError, sanitize, UA_SIMPLE

LABEL = "Sanoma"
AUTH_FIELDS = [("email", "Email account Sanoma", False, True),
               ("password", "Password", True, True)]
AUTH_HELP = "Accedi con email e password del tuo account Sanoma."
ID_LABEL = "ID libro (gedi)"
ID_HELP = "Il codice 'gedi' del libro, oppure selezionalo dalla lista."
OPTIONS = []
API = "https://npmoffline.sanoma.it/mcs/api/v1"

NEEDS_LOGIN = True
NEEDS_LIST = True


def login(creds):
    email, password = creds["email"].strip(), creds["password"]
    try:
        r = requests.post(
            f"{API}/login",
            headers={**UA_SIMPLE, "Content-Type": "application/json", "X-Timezone-Offset": "+0200"},
            json={"id": email, "password": password},
            timeout=20,
        ).json()
    except Exception:
        raise LoginError("Server Sanoma non raggiungibile. Riprova più tardi.")
    if r.get("code") != 0:
        raise LoginError(f"Login non riuscito: {r.get('message', 'email o password errati')}.")
    try:
        return {"token": r["result"]["data"]["access_token"]}
    except KeyError:
        raise LoginError("Risposta di login inattesa dal server Sanoma.")


def _auth(state):
    return {**UA_SIMPLE, "X-Auth-Token": "Bearer " + state["token"]}


def list_books(state):
    r = requests.get(f"{API}/books?app=true", headers=_auth(state), timeout=20).json()
    books = []
    for b in (r.get("result") or {}).get("data", []):
        books.append({"id": str(b.get("gedi", "")), "title": b.get("name", "?"),
                      "url_download": b.get("url_download")})
    # salva url per il download senza rifare la lista
    state["by_id"] = {b["id"]: b for b in books}
    return [{"id": b["id"], "title": b["title"]} for b in books if b["id"]]


def download(state, book_id, out_dir, options, progress):
    gid = book_id.strip()
    book = (state.get("by_id") or {}).get(gid)
    if book is None:  # lista non caricata o ID manuale: ricarica
        for b in list_books(state):
            pass
        book = (state.get("by_id") or {}).get(gid)
    if book is None or not book.get("url_download"):
        raise RuntimeError("Libro non trovato nella tua libreria.")
    title = book["title"]

    tmp = tempfile.mkdtemp(prefix="sanoma_")
    try:
        progress(0, 1, f"Scarico '{title}'…")
        z = requests.get(book["url_download"], headers=_auth(state), timeout=300)
        if not z.ok:
            raise RuntimeError("Download dello ZIP non riuscito.")
        zpath = os.path.join(tmp, "book.zip")
        with open(zpath, "wb") as fh:
            fh.write(z.content)

        progress(0, 1, "Estraggo le pagine…")
        pages_dir = os.path.join(tmp, "pages")
        with zipfile.ZipFile(zpath) as zh:
            for name in zh.namelist():
                m = re.search(r"(?:^|/)pages/(.+)$", name)
                if not m or name.endswith("/"):
                    continue
                dest = os.path.join(pages_dir, m.group(1))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zh.open(name) as src, open(dest, "wb") as fh:
                    fh.write(src.read())

        folders = sorted(
            (d for d in os.listdir(pages_dir)
             if os.path.isdir(os.path.join(pages_dir, d)) and re.fullmatch(r"\d+", d)),
            key=int,
        )
        if not folders:
            raise RuntimeError("ZIP inatteso: nessuna pagina trovata.")

        doc = fitz.open()
        for i, n in enumerate(folders):
            progress(i, len(folders), f"Converto pagina {i + 1}/{len(folders)}…")
            svg_path = os.path.join(pages_dir, n, f"{n}.svg")
            if not os.path.exists(svg_path):
                # qualche pagina può avere nome diverso: prendi il primo svg
                cands = [f for f in os.listdir(os.path.join(pages_dir, n)) if f.lower().endswith(".svg")]
                if not cands:
                    continue
                svg_path = os.path.join(pages_dir, n, cands[0])
            with open(svg_path, "rb") as fh:
                svg = fitz.open(stream=fh.read(), filetype="svg")
            doc.insert_pdf(fitz.open(stream=svg.convert_to_pdf(), filetype="pdf"))
            svg.close()

        progress(1, 1, "Salvo il PDF…")
        out = os.path.join(out_dir, sanitize(title) + ".pdf")
        doc.save(out)
        doc.close()
        progress(1, 1, "PDF salvato!")
        return out
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
