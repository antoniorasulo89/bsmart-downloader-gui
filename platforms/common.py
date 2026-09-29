"""Utilità condivise dai moduli delle piattaforme."""
import re
import requests

UA_SIMPLE = {"User-Agent": "Mozilla/5.0"}
UA_CHROME = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}


class LoginError(RuntimeError):
    """Credenziali errate o login non riuscito."""


def sanitize(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip()[:150] or "libro"


def new_session(ua=UA_SIMPLE):
    s = requests.Session()
    s.headers.update(ua)
    return s
