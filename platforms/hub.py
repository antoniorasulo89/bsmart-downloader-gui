"""HUB Young / HUB Kids (porting di Leone25/hub-young-downloader).

Serve il Volume ID (dall'URL young.hubscuola.it/viewer/########)
e il token-session (F12 → Rete → richiesta con il Volume ID → token-session).
"""
import io
import json
import os
import sqlite3
import tempfile
import zipfile

import requests
from pypdf import PdfReader, PdfWriter

from .common import LoginError, sanitize, UA_SIMPLE

LABEL = "HUB Young / HUB Kids"
AUTH_FIELDS = [
    ("volume", "Volume ID (numero dopo /viewer/ nell'URL)", False, True),
    ("token", "Token-session (da F12 → Rete, vedi ?)", False, True),
]
AUTH_HELP = (
    "1. Apri il libro nel lettore web (young.hubscuola.it) e fai login\n"
    "2. Il Volume ID è il numero nell'URL: /viewer/########\n"
    "3. Premi F12 → Rete, ricarica la pagina, clicca la richiesta con il Volume ID\n"
    "4. In basso copia il valore 'token-session' e incollalo qui"
)
ID_LABEL = "Volume ID"
ID_HELP = "Il numero dopo /viewer/ nell'URL del libro."
OPTIONS = []

NEEDS_LOGIN = True
NEEDS_LIST = False  # un volume alla volta, niente libreria


def _api_me(platform, volume, token):
    # platform: "young" o "kids"
    r = requests.get(
        f"https://ms-api.hubscuola.it/me{platform}/publication/{volume}",
        headers={**UA_SIMPLE, "Token-Session": token, "Content-Type": "application/json"},
        timeout=20,
    )
    if r.status_code == 401:
        raise LoginError("Token-session non valido o libro non posseduto.")
    if r.status_code == 500:
        raise RuntimeError("Volume ID non valido.")
    r.raise_for_status()
    return r.json()


def login(creds):
    platform = creds.get("_site", "young")
    volume = creds["volume"].strip()
    token = creds["token"].strip()
    info = _api_me(platform, volume, token)
    return {"platform": platform, "volume": volume, "token": token,
            "title": info.get("title", f"volume-{volume}")}


def list_books(state):
    return [{"id": state["volume"], "title": state.get("title", state["volume"])}]


def download(state, book_id, out_dir, options, progress):
    platform, token = state["platform"], state["token"]
    volume = (book_id or state["volume"]).strip()
    info = _api_me(platform, volume, token)
    title = info.get("title", f"volume-{volume}")

    tmp = tempfile.mkdtemp(prefix="hub_")
    try:
        progress(0, 3, f"Scarico '{title}'…")
        z = requests.get(
            f"https://ms-mms.hubscuola.it/downloadPackage/{volume}/publication.zip?tokenId={token}",
            headers={**UA_SIMPLE, "Token-Session": token}, timeout=120,
        )
        if z.status_code != 200:
            raise RuntimeError(f"Errore download pacchetto (HTTP {z.status_code}).")
        with zipfile.ZipFile(io.BytesIO(z.content)) as zh:
            zh.extractall(os.path.join(tmp, "pack"))

        progress(1, 3, "Leggo l'indice dei capitoli…")
        db_path = os.path.join(tmp, "pack", "publication", "publication.db")
        if not os.path.exists(db_path):
            # cerca il db in caso di struttura diversa
            found = None
            for root, _dirs, files in os.walk(os.path.join(tmp, "pack")):
                if "publication.db" in files:
                    found = os.path.join(root, "publication.db")
                    break
            if not found:
                raise RuntimeError("Pacchetto inatteso: publication.db non trovato.")
            db_path = found
        db = sqlite3.connect(db_path)
        try:
            row = db.execute(
                "SELECT offline_value FROM offline_tbl WHERE offline_path=?",
                (f"me{platform}/publication/{volume}",),
            ).fetchone()
        finally:
            db.close()
        if not row:
            raise RuntimeError("Indice capitoli non trovato nel pacchetto.")
        chapters = json.loads(row[0])["indexContents"]["chapters"]

        targets = [c for c in chapters
                   if c.get("children") and all(not isinstance(x, (int, float)) for x in c["children"])]
        if not targets:
            raise RuntimeError("Nessun capitolo scaricabile trovato.")

        writer = PdfWriter()
        for i, ch in enumerate(targets):
            cid = ch["chapterId"]
            progress(i, len(targets), f"Scarico capitolo {i + 1}/{len(targets)}…")
            u = requests.get(
                f"https://ms-mms.hubscuola.it/public/{volume}/{cid}.zip?tokenId={token}&app=v2",
                headers={**UA_SIMPLE, "Token-Session": token}, timeout=120,
            )
            u.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(u.content)) as zh:
                zh.extractall(os.path.join(tmp, "build"))
            base = os.path.join(tmp, "build", str(cid))
            if not os.path.isdir(base):
                # struttura con sottocartella diversa: prendi la prima
                subs = [d for d in os.listdir(os.path.join(tmp, "build"))
                        if os.path.isdir(os.path.join(tmp, "build", d))]
                base = os.path.join(tmp, "build", subs[-1]) if subs else base
            for f in sorted(os.listdir(base)):
                if f.lower().endswith(".pdf"):
                    with open(os.path.join(base, f), "rb") as fh:
                        reader = PdfReader(fh)
                        for page in reader.pages:
                            writer.add_page(page)

        progress(1, 1, "Salvo il PDF…")
        out = os.path.join(out_dir, sanitize(title) + ".pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        progress(1, 1, "PDF salvato!")
        return out
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
