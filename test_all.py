"""Test offline dei moduli platforms (mock di rete dove serve)."""
import base64
import io
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from unittest.mock import patch

import pymupdf as fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from platforms import PLATFORMS
import xml.etree.ElementTree as ET
from platforms import bsmart, mylim, hub, sanoma, zanichelli
from platforms.common import LoginError

fails = []


def check(name, fn):
    try:
        with tempfile.TemporaryDirectory() as library_dir, patch("library.index_path", return_value=os.path.join(library_dir, "library.json")):
            fn()
            import gc
            gc.collect()
        print("OK  ", name)
    except Exception as e:
        fails.append(name)
        print("FAIL", name, "->", type(e).__name__, str(e)[:300])


# 1. registro interfacce
def t_registry():
    assert len(PLATFORMS) == 6, len(PLATFORMS)
    for p in PLATFORMS:
        m = p["mod"]
        for attr in ("LABEL", "AUTH_FIELDS", "ID_LABEL", "OPTIONS", "NEEDS_LOGIN",
                     "NEEDS_LIST", "login", "list_books", "download"):
            assert hasattr(m, attr), f"{p['key']} manca {attr}"

check("registry 6 piattaforme", t_registry)


# 2. bsmart decrypt roundtrip (formato reale)
def t_bsmart_decrypt():
    import msgpack
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    key = get_random_bytes(16)
    iv = get_random_bytes(16)
    plain = b"%PDF-1.4 test"
    pad = 16 - len(plain) % 16
    ct = AES.new(key, AES.MODE_CBC, iv).encrypt(plain + bytes([pad]) * pad)
    start = 256 + len(iv) + len(ct)
    hdr = msgpack.packb({"start": start})
    blob = hdr + b"\x00" * (256 - len(hdr)) + iv + ct + b"-TAIL-"
    assert bsmart.decrypt_file(blob, key) == plain + b"-TAIL-"

check("bsmart decrypt", t_bsmart_decrypt)


def t_bsmart_bad_login():
    with patch.object(bsmart.requests, "get", side_effect=LoginError("Accesso negato")), patch.object(bsmart.requests, "post", side_effect=LoginError("Accesso negato")):
        try:
            bsmart.login({"_site": "bsmart", "email": "test@example.test", "password": "wrong"})
        except LoginError:
            return
        raise AssertionError("Login errato accettato")

check("bsmart login errato", t_bsmart_bad_login)


# 3. zanichelli crypto roundtrip
def t_zani_crypto():
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    k = RSA.generate(1024)
    raw_priv = k.export_key("DER").hex()  # simula base64 senza header? no: usa b64 vera sotto
    raw_priv_b64 = base64.b64encode(k.export_key("DER")).decode()
    secret = b"risorsa-segreta!"
    ct = PKCS1_v1_5.new(k.publickey()).encrypt(secret)
    assert zanichelli._decrypt_key(raw_priv_b64, base64.b64encode(ct).decode()) == secret
    # AES pagina
    enc_key = b"0123456789abcdefXYZ"
    from Crypto.Cipher import AES as _AES
    c = _AES.new(enc_key[:16], _AES.MODE_CBC, enc_key[:16])
    data = c.encrypt(b"0123456789abcdef")  # 16 byte, nessun padding necessario per il test
    assert zanichelli._decrypt_page(enc_key, base64.b64encode(data).decode()) == b"0123456789abcdef"

check("zanichelli RSA+AES", t_zani_crypto)


def t_zani_spine():
    spine_xml = """<response><spine><unit btbid="U1" features="html"/><unit btbid="U2" features="flash"/>
      <unit btbid="U3"/></spine><config><volume><settings><volumetitle>Libro Test</volumetitle>
      </settings></volume></config></response>"""
    root = ET.fromstring(spine_xml)
    units = [u.attrib["btbid"] for u in root.iter("unit")
             if u.attrib.get("btbid") and u.attrib.get("features") != "flash"]
    assert units == ["U1", "U3"], units
    vt = root.find(".//volumetitle")
    assert vt is not None and vt.text == "Libro Test"

check("zanichelli parsing spine", t_zani_spine)


def t_zani_helpers():
    # unpad valido / non valido
    assert zanichelli._unpad(b"ABC" + bytes([2]) * 2) == b"ABC"
    assert zanichelli._unpad(b"ABC\x05\x06") == b"ABC\x05\x06"
    # manifest nei due formati
    m = {"imagesP1svgz": ("a.svgz", "image/svg+xml"), "images/P2.png": ("b.png", "image/png")}
    assert zanichelli._pick_manifest(m, "P1") == ("a.svgz", "image/svg+xml")
    assert zanichelli._pick_manifest(m, "P2") == ("b.png", "image/png")
    assert zanichelli._pick_manifest(m, "PX") is None
    # fragment del reader con token contenente '+'
    bid, tok = zanichelli._grab_params("https://webreader.zanichelli.it/#/reader?bookID=AB12&usertoken=a+b/c=")
    assert bid == "AB12" and tok == "a+b/c=", (bid, tok)

check("zanichelli helpers", t_zani_helpers)


# 4. hub: db sintetico + zip + merge
def t_hub_db():
    tmp = tempfile.mkdtemp()
    dbp = os.path.join(tmp, "publication.db")
    db = sqlite3.connect(dbp)
    db.execute("CREATE TABLE offline_tbl (offline_path TEXT, offline_value TEXT)")
    chapters = {"indexContents": {"chapters": [
        {"chapterId": "c1", "children": ["a", "b"]},
        {"chapterId": "c2", "children": [1, 2]},
    ]}}
    db.execute("INSERT INTO offline_tbl VALUES (?, ?)",
               ("meyoung/publication/123", json.dumps(chapters)))
    db.commit()
    row = db.execute("SELECT offline_value FROM offline_tbl WHERE offline_path=?",
                     ("meyoung/publication/123",)).fetchone()
    db.close()
    chs = json.loads(row[0])["indexContents"]["chapters"]
    targets = [c for c in chs if c.get("children") and all(not isinstance(x, (int, float)) for x in c["children"])]
    assert [c["chapterId"] for c in targets] == ["c1"], targets
    # zip con pdf sintetici e merge
    d = fitz.open()
    d.new_page(width=100, height=100)
    buf = io.BytesIO()
    d.save(buf)
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zh:
        zh.writestr("c1/p1.pdf", buf.getvalue())
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    with zipfile.ZipFile(zbuf) as zh:
        for n in zh.namelist():
            r = PdfReader(io.BytesIO(zh.read(n)))
            for pg in r.pages:
                w.add_page(pg)
    assert len(w.pages) == 1

check("hub db+zip+merge", t_hub_db)


# 5. sanoma: zip pagine + svg->pdf
def t_sanoma_zip():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="red"/></svg>'
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zh:
        zh.writestr("xxx/pages/1/1.svg", svg)
        zh.writestr("xxx/pages/2/2.svg", svg)
        zh.writestr("other/file.txt", b"x")
    import re as _re
    zbuf.seek(0)
    doc = fitz.open()
    with zipfile.ZipFile(zbuf) as zh:
        for name in zh.namelist():
            m = _re.search(r"(?:^|/)pages/(.+)$", name)
            assert (m is not None) == ("pages/" in name), name
            if not m or name.endswith("/"):
                continue
            s = fitz.open(stream=zh.read(name), filetype="svg")
            doc.insert_pdf(fitz.open(stream=s.convert_to_pdf(), filetype="pdf"))
    assert doc.page_count == 2

check("sanoma zip+svg", t_sanoma_zip)


# 6. mylim con rete mockata
class FakeResp:
    def __init__(self, payload=None, content=None, status_code=200):
        self._payload = payload
        self.content = content or b""
        self.status_code = status_code

    @property
    def text(self):
        return self.content.decode("utf-8", "replace")

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise IOError(f"HTTP {self.status_code}")


def t_mylim():
    sommari = [{"opera": {"isbn": "978-1", "nome": "Libro Uno", "autore": "Aut",
                          "copertina": "http://x/y.jpg"}, "tipologia": "b"}]
    buf = io.BytesIO()
    dd = fitz.open()
    dd.new_page(width=50, height=50)
    dd.save(buf)
    with patch("platforms.mylim.requests.post") as post, \
         patch("platforms.mylim.requests.get") as g:
        post.return_value = FakeResp(payload={"token": "TOK"}, content=b'{"token":"TOK"}')
        g.side_effect = [FakeResp(payload=sommari),
                         FakeResp(payload={"url": "http://x/libro.pdf"}),
                         FakeResp(content=buf.getvalue())]
        st = mylim.login({"email": "a@b.it", "password": "x", "token": ""})
        assert st["token"] == "TOK"
        books = mylim.list_books(st)
        assert books == [{"id": "978-1", "title": "Libro Uno — Aut"}], books
        out = mylim.download(st, "978-1", tempfile.mkdtemp(), {}, lambda *a: None)
        assert os.path.exists(out) and os.path.getsize(out) > 100, out

check("mylim mock", t_mylim)


def t_hub():
    # pdf di test
    buf = io.BytesIO()
    dd = fitz.open()
    dd.new_page(width=50, height=50)
    dd.save(buf)
    pdf_bytes = buf.getvalue()
    # db con un capitolo
    tmp = tempfile.mkdtemp()
    dbp = os.path.join(tmp, "p.db")
    db = sqlite3.connect(dbp)
    db.execute("CREATE TABLE offline_tbl (offline_path TEXT, offline_value TEXT)")
    db.execute("INSERT INTO offline_tbl VALUES (?, ?)",
               ("meyoung/publication/7", json.dumps(
                   {"indexContents": {"chapters": [{"chapterId": "c1"}]}})))
    db.execute("INSERT INTO offline_tbl VALUES (?, ?)",
               ("mekids/publication/9", json.dumps(
                   {"indexContents": {"chapters": [{"chapterId": "c1"}]}})))
    db.commit()
    db.close()
    pack = io.BytesIO()
    with zipfile.ZipFile(pack, "w") as zh:
        with open(dbp, "rb") as fh:
            zh.writestr("publication/publication.db", fh.read())
    chap = io.BytesIO()
    with zipfile.ZipFile(chap, "w") as zh:
        zh.writestr("c1/p1.pdf", pdf_bytes)

    import platforms.hub as hubmod
    with patch.object(hubmod.requests, "get") as g, \
         patch.object(hubmod.requests, "post") as post:
        g.side_effect = [
            FakeResp(payload={"result": "OK", "data": {"username": "a@b.it",
                      "sessionId": "S", "hubEncryptedUser": "J"}}),  # loginJsonp
            FakeResp(payload=[{"id": 7, "title": "Volume Sette"}]),  # young
            FakeResp(payload=[{"id": 9, "title": "Kids Nove"}]),  # kids
            FakeResp(payload=[{"id": 7, "title": "Volume Sette"}]),  # young (title lookup)
            FakeResp(payload=[{"id": 9, "title": "Kids Nove"}]),  # kids (title lookup)
            FakeResp(content=pack.getvalue()),  # publication.zip
            FakeResp(content=chap.getvalue()),  # chapter zip
        ]
        post.return_value = FakeResp(payload={"tokenId": "TOK"})
        st = hubmod.login({"_site": None, "email": "a@b.it", "password": "x", "token": ""})
        assert st["token"] == "TOK" and st["sections"] == {}, st
        books = hubmod.list_books(st)
        assert books == [{"id": "7", "title": "Volume Sette"},
                         {"id": "9", "title": "Kids Nove"}], books
        assert st["sections"] == {"7": "young", "9": "kids"}, st["sections"]
        out = hubmod.download(st, "9", tempfile.mkdtemp(), {}, lambda *a: None)
        d = fitz.open(out)
        assert d.page_count == 1, d.page_count

check("hub mock", t_hub)


# 8. GUI si costruisce
def t_gui():
    import app_gui
    assert len(PLATFORMS) == 6
    app = app_gui.App()
    assert len(app.plat_buttons) == 6
    assert "email" in app.auth_vars  # bsmart di default
    app._select_platform("bsmart")
    app.session_state = {"test": True}
    app.books = [{"id": "http://demo/x", "title": "Demo"}]
    app._filter_books()
    assert len(app.book_rows) == 1
    app._pick("http://demo/x")
    assert app.selected_id == "http://demo/x"
    assert str(app.dl_btn.cget("state")) == "normal"
    # regressione: self.state non deve coprire il metodo tkinter (crash CTk mainloop)
    assert callable(app.state), "self.state copre tkinter.Widget.state!"
    app.destroy()

check("gui build", t_gui)


def t_vault():
    import vault
    if sys.platform != "win32":
        data = {}
        with patch.object(vault, "_load_blob", side_effect=lambda: json.dumps(data).encode()), patch.object(vault, "_store_blob", side_effect=lambda raw: data.update(json.loads(raw))):
            vault.set_creds("__test__", "a@b.it", "segreto123")
            assert vault.get_creds("__test__")["password"] == "segreto123"
        return
    vault.set_creds("__test__", "a@b.it", "segreto123")
    got = vault.get_creds("__test__")
    assert got == {"email": "a@b.it", "password": "segreto123"}, got
    vault.del_creds("__test__")
    assert vault.get_creds("__test__") == {}

with tempfile.TemporaryDirectory() as vault_dir, patch("vault._vault_path", return_value=os.path.join(vault_dir, "vault.dat")):
    check("vault roundtrip", t_vault)


def t_context_menu():
    import app_gui
    app = app_gui.App()
    # binding presenti (il recapito tasti e meccanismo Tk standard)
    assert app.bind_all("<Button-3>"), "binding tasto destro mancante"
    assert app.bind_class(app._edit_tag, "<Control-v>"), "binding incolla mancante"
    entry = app.auth_widgets["email"]
    app.clipboard_clear()
    app.clipboard_append("test@incolla.it")
    assert app._edit_op("paste", entry) is True
    assert entry.get() == "test@incolla.it", repr(entry.get())
    entry.select_range(0, "end")
    assert app._edit_op("copy", entry) is True
    entry.delete(0, "end")
    assert app._edit_op("paste", entry) is True
    assert entry.get() == "test@incolla.it", repr(entry.get())
    entry.select_range(0, "end")
    assert app._edit_op("cut", entry) is True
    assert entry.get() == "", repr(entry.get())
    assert app._edit_op("paste", entry) is True
    assert entry.get() == "test@incolla.it", repr(entry.get())
    app.destroy()

with patch("vault.get_creds", return_value={}):
    check("copia/incolla nei campi", t_context_menu)


def t_account_operations():
    import app_gui
    import vault
    import threading
    import time
    saved = {}
    gate = threading.Event()
    started = threading.Event()
    def login(creds):
        started.set()
        gate.wait(5)
        assert creds["password"] == " password "
        return {"account": creds["email"]}
    with patch.object(vault, "get_creds", return_value={}), \
         patch.object(vault, "set_account", side_effect=lambda k, v: saved.update({k: v})), \
         patch.object(vault, "del_creds", side_effect=lambda k: saved.pop(k, None)), \
         patch.object(app_gui.messagebox, "showinfo"), \
         patch.object(bsmart, "login", side_effect=login), \
         patch.object(bsmart, "list_books", return_value=[{"id": "book", "title": "Libro"}]):
        app = app_gui.App()
        try:
            assert not app.remember_var.get()
            app.auth_vars["email"].set("account@example.test")
            app.auth_vars["password"].set(" password ")
            app._save_account()
            assert not saved
            app.remember_var.set(True)
            app._save_account()
            assert saved["bsmart"]["password"] == " password "
            app._load_books_thread()
            assert started.wait(2)
            app._select_platform("sanoma")
            assert app.platform_key == "bsmart"
            app._load_books_thread()
            assert bsmart.login.call_count == 1
            app.auth_vars["email"].set("changed@example.test")
            gate.set()
            deadline = time.monotonic() + 5
            while app.busy and time.monotonic() < deadline:
                app.update()
                time.sleep(0.01)
            assert not app.busy
            assert app.session_state["account"] == "account@example.test"
            app._pick("book")
            app.out_var.set(str(app.local_library.path.parent))
            gate.clear()
            started.clear()
            def download(state, book_id, out_dir, opts, progress):
                started.set()
                gate.wait(5)
                assert book_id == "book" and state["account"] == "account@example.test"
                progress(1, 1, "Finito")
                from pathlib import Path
                file = Path(out_dir) / "test.pdf"
                with fitz.open() as document:
                    document.new_page()
                    document.save(file)
                return str(file)
            with patch.object(bsmart, "download", side_effect=download):
                app._download_thread()
                assert started.wait(2)
                app._select_platform("sanoma")
                app._download_thread()
                assert app.platform_key == "bsmart" and bsmart.download.call_count == 1
                gate.set()
                deadline = time.monotonic() + 5
                while app.busy and time.monotonic() < deadline:
                    app.update()
                    time.sleep(0.01)
                assert not app.busy
                assert app.local_library.available()[0]["title"] == "Libro"
            app._delete_account()
            assert not saved and app.session_state is None
            assert not app.auth_vars["password"].get()
        finally:
            gate.set()
            app.update()
            app.destroy()
    with patch.object(vault.sys, "platform", "linux"), \
         patch.object(vault.shutil, "which", return_value=None), \
         patch("builtins.open") as opened:
        try:
            vault._store_blob(b"secret")
            raise AssertionError("salvataggio senza portachiavi accettato")
        except OSError:
            pass
        opened.assert_not_called()

check("consenso credenziali e isolamento accessi", t_account_operations)

def t_folio_navigation():
    import app_gui
    import vault
    with patch.object(vault, "get_creds", return_value={}), patch.object(app_gui.messagebox, "showinfo"):
        app = app_gui.App()
        try:
            app.session_state = {"account": "bsmart"}
            app.books = [{"id": "one", "title": "Libro disponibile"},
                         {"id": "two", "title": "Libro bloccato", "ok": False}]
            app._filter_books()
            app._pick("one")
            app._pick("two")
            assert app.selected_id == "one"
            assert str(app.book_rows[1][1].cget("state")) == "disabled"
            app.search_var.set("nessun risultato")
            assert not app.book_rows and "0 risultati" in app.book_count.cget("text")
            app._select_platform("sanoma")
            assert app.session_state is None
            app._select_platform("bsmart")
            assert app.session_state["account"] == "bsmart" and app.selected_id == "one"
            app.pages.set("Account e credenziali")
            assert app.page_title.cget("text") == "Account"
            app._select_platform("bsmart")
            app.auth_vars["email"].set("")
            app.auth_vars["password"].set("")
            app.auth_vars["cookie"].set("session-cookie")
            assert app.auth_widgets["cookie"].cget("show") == "•"
            with patch.object(bsmart, "login", return_value={}), patch.object(bsmart, "list_books", return_value=[]):
                app._load_books_thread()
                import time
                deadline = time.monotonic() + 5
                while app.busy and time.monotonic() < deadline:
                    app.update()
                    time.sleep(.01)
                assert not app.busy and bsmart.login.call_count == 1
        finally:
            app.destroy()

check("Folio: navigazione, sessioni e cookie", t_folio_navigation)

def t_real_paste():
    import app_gui
    with patch("vault.get_creds", return_value={}):
        app = app_gui.App()
        try:
            app.pages.set("Account e credenziali")
            app.update()
            entry = app.auth_widgets["email"]._entry
            entry.focus_force()
            app.update()
            app.clipboard_clear()
            app.clipboard_append("una-volta")
            entry.event_generate("<Control-v>")
            app.update()
            assert entry.get() == "una-volta", repr(entry.get())
            entry.selection_range(0, "end")
            entry.event_generate("<Control-v>")
            app.update()
            assert entry.get() == "una-volta", repr(entry.get())
            app.pages.set("Scaricati")
            app.local_search.set("")
            field = next(w for w in app.page_frames["Scaricati"].winfo_children() if isinstance(w, app_gui.ctk.CTkEntry))._entry
            field.focus_force()
            app.update()
            field.event_generate("<Control-v>")
            app.update()
            assert app.local_search.get() == "una-volta"
            app._toggle_log()
            text = app.log._textbox
            text.focus_force()
            text.delete("1.0", "end")
            app.update()
            text.event_generate("<Control-v>")
            app.update()
            assert text.get("1.0", "end-1c") == "una-volta"
        finally:
            app.destroy()


def wait_library(app):
    import time
    deadline = time.monotonic() + 5
    app.update()
    while (getattr(app, "_library_pending", False) or getattr(app, "_library_scanning", False)) and time.monotonic() < deadline:
        app.update()
        time.sleep(.01)
    assert not getattr(app, "_library_pending", False) and not getattr(app, "_library_scanning", False)

def t_local_library():
    from library import Library
    from pathlib import Path
    import app_gui
    with tempfile.TemporaryDirectory() as folder, patch("vault.get_creds", return_value={}):
        root = Path(folder)
        pdf = root / "libro.pdf"
        import pymupdf as fitz
        with fitz.open() as document:
            document.new_page()
            document.save(pdf)
        store = Library(root / "index.json")
        assert store.add(pdf, "Titolo originale", "bsmart", "1")
        assert store.add(pdf, "Titolo originale", "bsmart", "1")
        assert len(store.available()) == 1
        restarted = Library(root / "index.json")
        assert restarted.available()[0]["title"] == "Titolo originale"
        app = app_gui.App()
        try:
            app.local_library = restarted
            app.out_var.set(str(root))
            app.pages.set("Scaricati")
            wait_library(app)
            assert "1 PDF" in app.local_count.cget("text")
            app._select_platform("sanoma")
            app.pages.set("Scaricati")
            wait_library(app)
            assert "1 PDF" in app.local_count.cget("text")
            pdf.unlink()
            app._refresh_downloaded()
            wait_library(app)
            assert "0 PDF" in app.local_count.cget("text")
            assert not Library(root / "index.json").available()
            moved = root / "nuovo.pdf"
            with fitz.open() as document:
                document.new_page()
                document.save(moved)
            app._refresh_downloaded()
            wait_library(app)
            assert "1 PDF" in app.local_count.cget("text")
        finally:
            app.destroy()

check("Ctrl+V reale: una sola incolla e sostituzione selezione", t_real_paste)
check("Biblioteca persistente: file presenti, eliminati e scoperti", t_local_library)

print()
if fails:
    print("FALLITI:", fails)
    sys.exit(1)
print("TUTTI I TEST OK")
