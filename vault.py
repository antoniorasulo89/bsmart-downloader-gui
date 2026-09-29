"""Portachiavi locale multipiattaforma.

Windows: DPAPI (solo lo stesso utente può decifrare).
macOS: Keychain tramite comando `security`.
Linux: Secret Service tramite `secret-tool`. Nessun salvataggio in chiaro.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
from storage import atomic_write
from filelock import FileLock

_LOCK = threading.RLock()

SERVICE = "ScaricaLibri"


def _vault_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, "ScaricaLibri")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "vault.dat")


# ---------- Windows DPAPI ----------

def _win_protect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    blob_in = Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data),
                                          ctypes.POINTER(ctypes.c_byte)))
    blob_out = Blob()
    if not crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0,
                                    ctypes.byref(blob_out)):
        raise OSError("DPAPI CryptProtectData fallita")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _win_unprotect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    blob_in = Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data),
                                          ctypes.POINTER(ctypes.c_byte)))
    blob_out = Blob()
    if not crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0,
                                      ctypes.byref(blob_out)):
        raise OSError("DPAPI CryptUnprotectData fallita")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


# ---------- backend generico ----------

def _store_blob(raw: bytes):
    if sys.platform == "win32":
        atomic_write(_vault_path(), _win_protect(raw))
    elif sys.platform == "darwin" and shutil.which("security"):
        subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE,
                        "-a", "vault", "-w", raw.decode("latin1")],
                       check=True, capture_output=True, timeout=20)
    elif shutil.which("secret-tool"):
        p = subprocess.run(["secret-tool", "store", "--label=ScaricaLibri",
                            "service", SERVICE, "account", "vault"],
                           input=raw, capture_output=True, timeout=20)
        if p.returncode != 0:
            raise OSError("secret-tool store fallito")
    else:
        raise OSError("Portachiavi sicuro non disponibile. Le credenziali restano solo in memoria.")


def _load_blob():
    if sys.platform == "win32":
        with open(_vault_path(), "rb") as fh:
            return _win_unprotect(fh.read())
    elif sys.platform == "darwin" and shutil.which("security"):
        p = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-w"],
                           capture_output=True, timeout=20)
        if p.returncode == 44:
            raise FileNotFoundError("nessuna voce nel portachiavi")
        if p.returncode != 0:
            raise OSError("Accesso al portachiavi non riuscito")
        return p.stdout.strip().decode("latin1").encode("latin1")
    elif shutil.which("secret-tool"):
        p = subprocess.run(["secret-tool", "lookup", "service", SERVICE, "account", "vault"],
                           capture_output=True, timeout=20)
        if p.returncode != 0:
            raise OSError("Accesso al portachiavi non riuscito")
        if not p.stdout:
            raise FileNotFoundError("nessuna voce nel portachiavi")
        return p.stdout
    else:
        raise OSError("Portachiavi sicuro non disponibile")


def load_all():
    try:
        data = json.loads(_load_blob().decode("utf-8"))
        if not isinstance(data, dict) or any(not isinstance(v, dict) for v in data.values()):
            raise ValueError("Archivio inatteso")
        return data
    except FileNotFoundError:
        return {}
    except Exception:
        raise OSError("Portachiavi non leggibile. Le credenziali esistenti non saranno sovrascritte.") from None


def save_all(vault):
    _store_blob(json.dumps(vault).encode("utf-8"))


def get_creds(platform_key):
    return load_all().get(platform_key, {})


def set_account(platform_key, credentials):
    with _LOCK, FileLock(_vault_path() + ".lock", timeout=10):
        v = load_all()
        v[platform_key] = dict(credentials)
        save_all(v)


def set_creds(platform_key, email, password):
    set_account(platform_key, {"email": email, "password": password})


def del_creds(platform_key):
    with _LOCK, FileLock(_vault_path() + ".lock", timeout=10):
        if legacy_exists():
            raise OSError("È presente il vecchio archivio Linux in chiaro. Usa Elimina vecchio archivio nella pagina Account.")
        v = load_all()
        if platform_key in v:
            del v[platform_key]
            save_all(v)


def legacy_exists():
    return sys.platform not in ('win32', 'darwin') and os.path.isfile(_vault_path())

def remove_legacy():
    """Rimozione esplicita dell’intero vecchio archivio Linux in chiaro."""
    if legacy_exists():
        os.unlink(_vault_path())
