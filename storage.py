"""Scritture atomiche dei dati locali."""
import os
import tempfile
from pathlib import Path

def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def download_folder():
    if os.environ.get("FOLIO_SMOKE_HOME"):
        return str(Path(os.environ["FOLIO_SMOKE_HOME"]) / "Folio")
    documents = Path.home() / 'Documents'
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                documents = Path(os.path.expandvars(winreg.QueryValueEx(key, 'Personal')[0]))
        except OSError:
            pass
    return str(documents / 'Folio')
