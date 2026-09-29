"""Portachiavi locale: salva email+password cifrate con DPAPI di Windows.

Solo lo stesso utente Windows può decifrarle. Niente dipendenze extra
(stdlib + ctypes), quindi funziona anche nell'exe.
"""
import ctypes
import json
import os
from ctypes import wintypes


def _vault_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "ScaricaLibri")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "vault.dat")


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _protect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = _Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = _Blob()
    if not crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI CryptProtectData fallita")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _unprotect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = _Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = _Blob()
    if not crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI CryptUnprotectData fallita")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def load_all():
    try:
        with open(_vault_path(), "rb") as fh:
            return json.loads(_unprotect(fh.read()).decode("utf-8"))
    except Exception:
        return {}


def save_all(vault):
    with open(_vault_path(), "wb") as fh:
        fh.write(_protect(json.dumps(vault).encode("utf-8")))


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
