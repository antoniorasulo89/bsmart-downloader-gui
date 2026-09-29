"""Portachiavi locale multipiattaforma.

Windows: DPAPI (solo lo stesso utente può decifrare).
macOS: Keychain tramite comando `security`.
Linux: Secret Service tramite `secret-tool`, oppure file con permessi 0600.
"""
import json
import os
import shutil
import subprocess
import sys

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
        with open(_vault_path(), "wb") as fh:
            fh.write(_win_protect(raw))
    elif sys.platform == "darwin" and shutil.which("security"):
        subprocess.run(["security", "delete-generic-password", "-s", SERVICE],
                       capture_output=True)
        subprocess.run(["security", "add-generic-password", "-s", SERVICE,
                        "-a", "vault", "-w", raw.decode("latin1")],
                       check=True, capture_output=True)
    elif shutil.which("secret-tool"):
        p = subprocess.run(["secret-tool", "store", "--label=ScaricaLibri",
                            "service", SERVICE, "account", "vault"],
                           input=raw, capture_output=True)
        if p.returncode != 0:
            raise OSError("secret-tool store fallito")
    else:
        with open(_vault_path(), "wb") as fh:
            fh.write(raw)
        os.chmod(_vault_path(), 0o600)


def _load_blob():
    if sys.platform == "win32":
        with open(_vault_path(), "rb") as fh:
            return _win_unprotect(fh.read())
    elif sys.platform == "darwin" and shutil.which("security"):
        p = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-w"],
                           capture_output=True)
        if p.returncode != 0:
            raise OSError("nessuna voce nel portachiavi")
        return p.stdout.strip().decode("latin1").encode("latin1")
    elif shutil.which("secret-tool"):
        p = subprocess.run(["secret-tool", "lookup", "service", SERVICE, "account", "vault"],
                           capture_output=True)
        if p.returncode != 0 or not p.stdout:
            raise OSError("nessuna voce nel portachiavi")
        return p.stdout
    else:
        with open(_vault_path(), "rb") as fh:
            return fh.read()


def load_all():
    try:
        return json.loads(_load_blob().decode("utf-8"))
    except Exception:
        return {}


def save_all(vault):
    _store_blob(json.dumps(vault).encode("utf-8"))


def get_creds(platform_key):
    return load_all().get(platform_key, {})


def set_creds(platform_key, email, password):
    v = load_all()
    v[platform_key] = {"email": email, "password": password}
    save_all(v)


def del_creds(platform_key):
    v = load_all()
    if platform_key in v:
        del v[platform_key]
        save_all(v)
