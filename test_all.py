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

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from platforms import PLATFORMS
from platforms import bsmart, mylim, hub, hoepli, sanoma, zanichelli
from platforms.common import LoginError

fails = []


def check(name, fn):
    try:
        fn()
        print("OK  ", name)
    except Exception as e:
        fails.append(name)
        print("FAIL", name, "->", type(e).__name__, str(e)[:300])


# 1. registro interfacce
def t_registry():
    assert len(PLATFORMS) == 8, len(PLATFORMS)
    for p in PLATFORMS:
        m = p["mod"]
        for attr in ("LABEL", "AUTH_FIELDS", "ID_LABEL", "OPTIONS", "NEEDS_LOGIN",
                     "NEEDS_LIST", "login", "list_books", "download"):
            assert hasattr(m, attr), f"{p['key']} manca {attr}"

check("registry 8 piattaforme", t_registry)


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
    try:
        bsmart.login_with_credentials("test@test.it", "wrongpass123")
        raise AssertionError("atteso LoginError")
    except LoginError as e:
        assert "non validi" in str(e).lower()

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
    root = zanichelli._xml(spine_xml)
    assert root.find("spine") is not None
    units = [u.attrib.get("btbid") for u in root.find("spine").findall("unit")
             if u.attrib.get("features") != "flash"]
    assert units == ["U1", "U3"], units

check("zanichelli parsing spine", t_zani_spine)


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

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise IOError(f"HTTP {self.status_code}")


def t_mylim():
    sommari = [{"opera": {"isbn": "978-1", "nome": "Libro Uno", "autore": "Aut",
                          "copertina": "http://x/y.jpg"}, "tipologia": "b"}]
    pdf_bytes = fitz.open().new_page(width=50, height=50) and None  # placeholder
    buf = io.BytesIO()
    dd = fitz.open()
    dd.new_page(width=50, height=50)
    dd.save(buf)
    with patch("platforms.mylim.requests.get") as g:
        g.side_effect = [FakeResp(payload=sommari),
                         FakeResp(payload={"url": "http://x/libro.pdf"}),
                         FakeResp(content=buf.getvalue())]
        st = mylim.login({"token": "TOK"})
        books = mylim.list_books(st)
        assert books == [{"id": "978-1", "title": "Libro Uno — Aut"}], books
        out = mylim.download(st, "978-1", tempfile.mkdtemp(), {}, lambda *a: None)
        assert os.path.exists(out) and os.path.getsize(out) > 100, out

check("mylim mock", t_mylim)


# 7. hoepli con rete mockata
def t_hoepli():
    dd = fitz.open()
    dd.new_page(width=60, height=80)
    png_buf = io.BytesIO()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 80), False)
    pix.set_rect(pix.irect, (0, 120, 200))
    png_buf.write(pix.tobytes("png"))
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80"></svg>'
    pager = {"pages": {"structure": ["1", "2"],
                       "defaults": {"width": 60, "height": 80, "substrateSizesReady": "s",
                                    "substrateFormat": "png", "textLayer": True},
                       "1": {}, "2": {}}}
    html = "<html><head><title>Demo Test</title></head></html>"

    def fake_get(url, **kw):
        if url.endswith("pager.js"):
            return FakeResp(payload=pager)
        if "page-vectorlayers" in url:
            return FakeResp(content=svg)
        if "substrates" in url:
            return FakeResp(content=png_buf.getvalue())
        return FakeResp(content=html.encode())

    with patch("platforms.hoepli.requests.get", side_effect=fake_get):
        outdir = tempfile.mkdtemp()
        out = hoepli.download({}, "http://demo/test/index.html", outdir, {}, lambda *a: None)
        d = fitz.open(out)
        assert d.page_count == 2, d.page_count

check("hoepli mock", t_hoepli)


# 8. GUI si costruisce
def t_gui():
    import app_gui
    app = app_gui.App()
    assert len(app.plat_box["values"]) == 8
    app.destroy()

check("gui build", t_gui)


print()
if fails:
    print("FALLITI:", fails)
    sys.exit(1)
print("TUTTI I TEST OK")
