"""Indice locale dei PDF: metadati persistenti, presenza verificata a ogni lettura."""
import json
import os
from pathlib import Path
import tempfile
import time
import threading
from functools import wraps
from filelock import FileLock
from storage import atomic_write
from platforms.common import valid_pdf


def index_path():
    base = os.environ.get("APPDATA") if os.name == "nt" else os.environ.get("XDG_CONFIG_HOME")
    return Path(base or Path.home() / ".config") / "Folio" / "library.json"


def locked(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return guarded


class Library:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(index_path())
        self.lock = threading.RLock()
        self.warning = None
        self.error = None
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("Formato inatteso")
            self.records = []
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                    continue
                r = dict(record)
                r["title"] = r.get("title") if isinstance(r.get("title"), str) else Path(r["path"]).stem
                for field in ("platform", "book_id"):
                    if not isinstance(r.get(field), str):
                        r[field] = None
                self.records.append(r)
        except FileNotFoundError:
            self.records = []
        except ValueError:
            backup = self.path.with_name(self.path.name + f".corrupt.{time.time_ns()}")
            try:
                atomic_write(backup, self.path.read_bytes())
                self.warning = "Indice non valido: copia originale conservata, biblioteca ricostruita dai PDF."
            except OSError:
                self.error = "Indice non valido e copia non creabile: archivio conservato, aggiornamento sospeso."
                self.warning = self.error
            self.records = []
        except OSError:
            self.records = []
            self.error = "Indice biblioteca non leggibile: archivio conservato, aggiornamento sospeso."
            self.warning = self.error

    @locked
    def add(self, path, title=None, platform=None, book_id=None):
        file = Path(path).resolve()
        if not file.is_file() or file.suffix.lower() != ".pdf" or not valid_pdf(file):
            return False
        key = os.path.normcase(str(file))
        self.records = [r for r in self.records if os.path.normcase(r["path"]) != key]
        self.records.insert(0, {"path": str(file), "title": title if isinstance(title, str) and title else file.stem,
                               "platform": platform if isinstance(platform, str) else None, "book_id": str(book_id) if book_id is not None else None})
        self._save()
        return True

    def _save(self):
        if self.error:
            raise OSError(self.error)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, FileLock(str(self.path) + '.lock', timeout=10):
            try:
                latest = Library(self.path)
                if latest.error:
                    raise OSError(latest.error)
                disk = latest.records
            except FileNotFoundError:
                disk = []
            keys = {os.path.normcase(r["path"]) for r in self.records}
            self.records.extend(r for r in disk if os.path.normcase(r["path"]) not in keys)
            atomic_write(self.path, json.dumps(self.records, ensure_ascii=False, indent=2).encode("utf-8"))

    @locked
    def available(self):
        return [r for r in self.records if Path(r["path"]).is_file() and valid_pdf(r["path"])]

    @locked
    def discover(self, folder):
        folder = Path(folder)
        known = {os.path.normcase(r["path"]) for r in self.records}
        changed = False
        if folder.is_dir():
            for file in sorted(folder.iterdir()):
                if file.suffix.lower() != ".pdf":
                    continue
                file = file.resolve()
                key = os.path.normcase(str(file))
                if key not in known and valid_pdf(file):
                    self.records.insert(0, {"path": str(file), "title": file.stem,
                                           "platform": None, "book_id": None})
                    known.add(key)
                    changed = True
        if changed:
            self._save()
