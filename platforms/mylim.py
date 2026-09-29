"""MyLim / Loescher (rif. Leone25/mylim-downloader + bundle ufficiale mylim).

Login con email+password (api-token-auth) oppure token JWT manuale.
"""
import os

import requests

from .common import LoginError, sanitize, UA_SIMPLE

LABEL = "MyLim (Loescher)"
AUTH_FIELDS = [
    ("email", "Email account MyLim", False, True),
    ("password", "Password", True, True),
    ("token", "Token JWT manuale (solo se il login non va)", False, False),
]
AUTH_HELP = "Accedi con email e password del tuo account MyLim/Loescher."
ID_LABEL = "ISBN"
ID_HELP = "Codice ISBN del volume, oppure selezionalo dalla lista."
OPTIONS = []
API = "https://loeda.loescher.it/mialim2/api/v1"

NEEDS_LOGIN = True
NEEDS_LIST = True


def _check_token(token):
    r = requests.get(f"{API}/book/sommari/",
                     headers={**UA_SIMPLE, "Authorization": "JWT " + token}, timeout=20)
    if r.status_code in (401, 403):
        return None
    r.raise_for_status()
    return r.json()


def login(creds):
    token = (creds.get("token") or "").strip().strip('"')
    if not token:
        email, password = creds["email"].strip(), creds["password"]
        r = requests.post(
            "https://loeda.loescher.it/loescher/api/v2/api-token-auth/",
            json={"username": email, "password": password, "app": "mylim"},
            headers=UA_SIMPLE, timeout=20,
        )
        if r.status_code in (400, 401, 403):
            raise LoginError("Email e/o password non corretti.")
        if not r.ok:
            raise LoginError(f"Login non riuscito (HTTP {r.status_code}).")
        data = r.json() if r.content else {}
        for field in ("token", "token_loescher", "access", "jwt", "key"):
            if data.get(field):
                token = data[field]
                break
        if not token:
            raise LoginError("Login riuscito ma token non trovato: incolla il token JWT manuale.")
    sommari = _check_token(token)
    if sommari is None:
        raise LoginError("Token non valido o scaduto.")
    return {"token": token, "sommari": sommari}


def list_books(state):
    books = []
    for b in state.get("sommari") or []:
        opera = b.get("opera", {})
        if opera.get("isbn"):
            books.append({
                "id": str(opera["isbn"]),
                "title": f"{opera.get('nome', '?')} — {opera.get('autore', '')}".strip(),
            })
    return books


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
    r = requests.get(url, headers=UA_SIMPLE, timeout=300)
    r.raise_for_status()
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
