"""MyLim / Loescher (porting di Leone25/mylim-downloader).

Il token JWT si copia dal localStorage di mylim.loescher.it
(F12 → Applicazione → Archiviazione locale → token).
"""
import os

import requests

from .common import sanitize, UA_SIMPLE

LABEL = "MyLim (Loescher)"
AUTH_FIELDS = [("token", "Token JWT (da localStorage di mylim.loescher.it)", False, True)]
AUTH_HELP = (
    "1. Apri mylim.loescher.it nel browser e fai login\n"
    "2. Premi F12 → Applicazione → Archiviazione locale → https://mylim.loescher.it\n"
    "3. Copia il valore di 'token' e incollalo qui"
)
ID_LABEL = "ISBN"
ID_HELP = "Codice ISBN del volume, oppure selezionalo dalla lista."
OPTIONS = []
API = "https://loeda.loescher.it/mialim2/api/v1"

NEEDS_LOGIN = True
NEEDS_LIST = True


def login(creds):
    token = creds["token"].strip().strip('"')
    # verifica subito il token
    r = requests.get(f"{API}/book/sommari/", headers={**UA_SIMPLE, "Authorization": "JWT " + token}, timeout=20)
    if r.status_code in (401, 403):
        from .common import LoginError
        raise LoginError("Token non valido o scaduto. Ricopialo da mylim.loescher.it.")
    r.raise_for_status()
    return {"token": token, "sommari": r.json()}


def list_books(state):
    books = []
    for b in state.get("sommari") or []:
        opera = b.get("opera", {})
        books.append({
            "id": str(opera.get("isbn", "")),
            "title": f"{opera.get('nome', '?')} — {opera.get('autore', '')}".strip(),
        })
    return [b for b in books if b["id"]]


def download(state, book_id, out_dir, options, progress):
    token = state["token"]
    isbn = book_id.strip()
    progress(0, 1, "Richiedo il PDF…")
    info = requests.get(f"{API}/book/pdf/{isbn}/",
                        headers={**UA_SIMPLE, "Authorization": "JWT " + token}, timeout=20).json()
    url = info.get("url")
    if not url:
        raise RuntimeError("Il server non ha fornito il link al PDF.")
    progress(0, 1, "Scarico il PDF…")
    r = requests.get(url, headers=UA_SIMPLE, timeout=60)
    r.raise_for_status()
    # titolo dalla lista se disponibile
    title = isbn
    for b in state.get("sommari") or []:
        if str(b.get("opera", {}).get("isbn")) == isbn:
            title = b["opera"].get("nome", isbn)
            break
    out = os.path.join(out_dir, sanitize(f"{isbn} - {title}") + ".pdf")
    with open(out, "wb") as fh:
        fh.write(r.content)
    progress(1, 1, "PDF salvato!")
    return out
