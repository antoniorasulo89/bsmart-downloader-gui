"""digibook24 usa l’accesso editore: nessuna password inviata a bSmart."""
from . import bsmart
from .common import LoginError
LABEL = "digibook24 (EdiErmes)"
AUTH_FIELDS = [("cookie", "Cookie sessione digibook24", True, True)]
AUTH_HELP = "Accedi a web.digibook24.com dal browser e copia il cookie _bsw_session_v1_production. Le password editore non vengono inviate a bSmart."
ID_LABEL, ID_HELP = bsmart.ID_LABEL, bsmart.ID_HELP
OPTIONS = bsmart.OPTIONS
NEEDS_LOGIN = NEEDS_LIST = True

def login(creds):
    if not (creds.get("cookie") or "").strip():
        raise LoginError("Per digibook24 serve il cookie dell’accesso editore nel browser.")
    return bsmart.login(dict(creds, _site="digibook24"))

list_books = bsmart.list_books
download = bsmart.download
