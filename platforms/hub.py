"""HUB Young / HUB Kids (Mondadori).

Login con email+password via loginJsonp + internalLogin
(rif. vvettoretti/hubscuola-downloader), libreria con getLibrary,
download pacchetto + capitoli e merge PDF.
"""
import io
import json
import os
import sqlite3
import tempfile
import zipfile

from . import network as requests
from pypdf import PdfReader, PdfWriter

from .common import response_json, save_pdf, checked_zip, svg_pdf, LoginError, sanitize, UA_SIMPLE

LABEL = "HUB Scuola (Young + Kids)"
AUTH_FIELDS = [
    ("email", "Email account HUB Scuola", False, True),
    ("password", "Password", True, True),
    ("token", "Token-session manuale (solo se il login non va)", False, False),
]
AUTH_HELP = "Accedi con email e password del tuo account HUB Scuola."
ID_LABEL = "ID volume"
ID_HELP = "L'ID numerico del volume, oppure selezionalo dalla lista."
OPTIONS = []

NEEDS_LOGIN = True
NEEDS_LIST = True


def login(creds):
    token = (creds.get("token") or "").strip()
    if not token:
        email, password = creds["email"].strip(), creds["password"]
        r = requests.get(
            "https://bce.mondadorieducation.it//app/mondadorieducation/login/loginJsonp",
            params={"username": email, "password": password},
            headers=UA_SIMPLE, timeout=20,
        )
        try:
            data = r.json()
        except Exception:
            raise LoginError("Server HUB non raggiungibile. Riprova più tardi.")
        if data.get("result") != "OK" or not (data.get("data") or {}).get("sessionId"):
            raise LoginError("Email e/o password non corretti.")
        d = data["data"]
        il = response_json(requests.post(
            "https://ms-api.hubscuola.it/user/internalLogin",
            json={"username": d.get("username", email),
                  "sessionId": d["sessionId"],
                  "jwt": d.get("hubEncryptedUser")},
            headers={**UA_SIMPLE, "Content-Type": "application/json"},
            timeout=20,
        ))
        token = il.get("tokenId")
        if not token:
            raise LoginError("Login HUB non completato. Riprova.")
    return {"token": token, "sections": {}}


def _h(state):
    return {**UA_SIMPLE, "Token-Session": state["token"], "token-session": state["token"]}


def list_books(state):
    books = []
    authorized = 0
    for section in ("young", "kids"):
        r = requests.get(f"https://ms-api.hubscuola.it/getLibrary/{section}",
                         headers=_h(state), timeout=20)
        if r.status_code == 401:
            continue
        r.raise_for_status()
        authorized += 1
        data = response_json(r)
        items = data if isinstance(data, list) else data.get("books") or data.get("data") or []
        for b in items:
            bid = str(b.get("id", ""))
            if not bid:
                continue
            tag = f" [{section}]" if any(x["id"] == bid for x in books) else ""
            books.append({"id": bid, "title": b.get("title", bid) + tag})
            state["sections"].setdefault(bid, section)
    if not authorized:
        raise LoginError("Sessione HUB scaduta. Riaccedi.")
    return books


def download(state, book_id, out_dir, options, progress):
    token = state["token"]
    volume = book_id.strip()
    platform = (state.get("sections") or {}).get(volume, "young")

    # titolo dalla libreria se disponibile
    title = f"volume-{volume}"
    try:
        for b in list_books(state):
            if b["id"] == volume:
                title = b["title"]
                break
    except Exception:
        pass

    tmp = tempfile.mkdtemp(prefix="hub_")
    try:
        progress(0, 1, f"Scarico '{title}'…")
        z = requests.get(
            f"https://ms-mms.hubscuola.it/downloadPackage/{volume}/publication.zip?tokenId={token}",
            headers=_h(state), timeout=300,
        )
        if z.status_code != 200:
            raise RuntimeError(f"Pacchetto non scaricabile (HTTP {z.status_code}).")
        pack_dir = os.path.join(tmp, "pack")
        with zipfile.ZipFile(io.BytesIO(z.content)) as zh:
            checked_zip(zh).extractall(pack_dir)

        progress(0, 1, "Leggo l'indice dei capitoli…")
        db_path = None
        for root, _dirs, files in os.walk(pack_dir):
            if "publication.db" in files:
                db_path = os.path.join(root, "publication.db")
                break
        if not db_path:
            raise RuntimeError("Pacchetto inatteso: publication.db non trovato.")
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

        writer = PdfWriter()
        pages = 0
        for i, ch in enumerate(chapters):
            cid = ch.get("chapterId")
            if not cid:
                continue
            progress(i, len(chapters), f"Scarico capitolo {i + 1}/{len(chapters)}…")
            try:
                u = requests.get(
                    f"https://ms-mms.hubscuola.it/public/{volume}/{cid}.zip?tokenId={token}&app=v2",
                    headers=_h(state), timeout=300,
                )
                if u.status_code != 200:
                    raise RuntimeError(f"Capitolo {i + 1} non scaricato (HTTP {u.status_code}).")
                with zipfile.ZipFile(io.BytesIO(u.content)) as zh:
                    checked_zip(zh)
                    chapter_pages = 0
                    for name in sorted(zh.namelist()):
                        if name.lower().endswith(".pdf"):
                            reader = PdfReader(io.BytesIO(zh.read(name)))
                            for pg in reader.pages:
                                writer.add_page(pg)
                                pages += 1
                                chapter_pages += 1
                    if not chapter_pages:
                        raise RuntimeError(f"Capitolo {i + 1} senza pagine PDF.")
            except Exception:
                raise RuntimeError(f"Download incompleto: capitolo {i + 1} non disponibile. Nessun PDF salvato.") from None
        if pages == 0:
            raise RuntimeError("Nessuna pagina scaricata (volume non disponibile?).")

        progress(1, 1, "Salvo il PDF…")
        out = os.path.join(out_dir, sanitize(title) + ".pdf")
        out = save_pdf(writer, out_dir, title)
        progress(1, 1, "PDF salvato!")
        return out
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
