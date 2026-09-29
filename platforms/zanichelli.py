"""Zanichelli (porting di Leone25/zanichelli-downloader).

Login email+password → libreria → download automatico sia per libri
BookTab (PDF diretti) sia per libri Kitaboo (pagine cifrate).
"""
import base64
import os
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import fitz
import requests
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

from .common import LoginError, sanitize, UA_CHROME

LABEL = "Zanichelli"
AUTH_FIELDS = [("email", "Email (username)", False, True),
               ("password", "Password", True, True)]
AUTH_HELP = "Accedi con email e password del tuo account Zanichelli."
ID_LABEL = "ISBN"
ID_HELP = "Codice ISBN del volume, oppure selezionalo dalla lista."
OPTIONS = []
CATALOG = "https://api-catalogo.zanichelli.it/v3"
READER = "https://webreader.zanichelli.it"
MICRO = "https://microservices.kitaboo.eu/v1/zanichelli"
DISTRIB = "https://zanichelliservices.kitaboo.eu/DistributionServices/services/api/reader/distribution"
BOOKTAB = "https://web-booktab.zanichelli.it/api"

NEEDS_LOGIN = True
NEEDS_LIST = True


def _h(cookie=None, myz=None, extra=None):
    h = dict(UA_CHROME)
    if cookie:
        h["Cookie"] = cookie
    if myz:
        h["myz-token"] = myz
    if extra:
        h.update(extra)
    return h


# ---------- login + libreria ----------

def login(creds):
    email, password = creds["email"].strip(), creds["password"]
    r = requests.post(
        "https://idp.zanichelli.it/v4/login/",
        headers={**UA_CHROME, "content-type": "application/x-www-form-urlencoded"},
        data=f"username={requests.utils.quote(email)}&password={requests.utils.quote(password)}",
        timeout=20,
    )
    if r.status_code == 401:
        raise LoginError("Email e/o password non corretti.")
    if not r.ok:
        raise LoginError(f"Login non riuscito (HTTP {r.status_code}).")
    token = r.json().get("token")
    if not token:
        raise LoginError("Email e/o password non corretti.")
    cookie = f"token={token}"
    s = requests.Session()
    s.headers.update(UA_CHROME)
    d = s.get("https://my.zanichelli.it/?loginMode=myZanichelli",
              headers={"Cookie": cookie}, timeout=20)
    d.raise_for_status()
    myz = s.cookies.get("myz_token")
    if not myz:
        raise LoginError("Login riuscito ma sessione non ottenuta. Riprova.")
    full_cookie = cookie + "".join(
        f"; {c.name}={c.value}" for c in s.cookies if c.name != "token")
    return {"cookie": full_cookie, "myz": myz}


def _add_licenses(books, licenses):
    for lic in licenses or []:
        vol = (lic.get("volume") or {})
        if not vol.get("ereader_url"):
            continue
        books[str(vol.get("isbn"))] = {
            "title": ((vol.get("opera") or {}).get("title")) or "?",
            "ereader_url": vol["ereader_url"],
        }


def list_books(state):
    myz = state["myz"]
    books, page = {}, 1
    while True:
        r = requests.get(
            f"{CATALOG}/dashboard/search?sort%5Bfield%5D=year_date&sort%5Bdirection%5D=desc"
            f"&searchString&pageNumber={page}&rows=100",
            headers=_h(myz=myz), timeout=20)
        if r.status_code == 403:
            break
        if not r.ok:
            raise RuntimeError(f"Elenco libri non disponibile (HTTP {r.status_code}).")
        data = r.json().get("data", {})
        _add_licenses(books, data.get("licenses"))
        pages = (data.get("pagination") or {}).get("pages", 0)
        if not pages or pages == page:
            break
        page += 1
    try:
        rl = requests.get(f"{CATALOG}/dashboard/licenses/real", headers=_h(myz=myz), timeout=20)
        if rl.ok:
            _add_licenses(books, rl.json().get("realLicenses"))
    except Exception:
        pass
    state["by_id"] = books
    return [{"id": k, "title": v["title"]} for k, v in books.items()]


# ---------- BookTab ----------

def _xml(text):
    return ET.fromstring(text)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _fetch_spine(isbn, cookie):
    for name in ("spine.xml", "volume.xml"):
        r = requests.get(f"{BOOKTAB}/v1/resources_web/{isbn}/{name}",
                         headers=_h(cookie), timeout=20)
        if r.status_code == 404:
            continue
        if not r.ok:
            raise RuntimeError(f"Struttura libro non disponibile (HTTP {r.status_code}).")
        return _xml(r.text)
    raise RuntimeError("Libro non scaricabile (spine.xml mancante).")


def _download_booktab(book, cookie, progress):
    isbn = book["isbn"]
    sess = requests.post(f"{BOOKTAB}/v1/sessions_web", headers=_h(cookie), timeout=20)
    if not sess.ok:
        raise RuntimeError("Sessione BookTab non creata.")
    cookie = f"{cookie}; booktab_token={sess.json()['session']}"
    spine = _fetch_spine(isbn, cookie)

    if spine.find("spine") is not None:
        title_el = spine.find("spine")
        title = "libro"
        units = [u.attrib.get("btbid") for u in spine.find("spine").findall("unit")
                 if u.attrib.get("features") != "flash"]
        # titolo dal config del volume se presente
        cfg = spine.find("config")
        if cfg is not None:
            vt = cfg.find("./volume/settings/volumetitle")
            if vt is not None and vt.text:
                title = vt.text.strip()
    else:
        vol = spine.find("./config/volume")
        st = vol.find("./settings/volumetitle") if vol is not None else None
        title = (st.text.strip() if st is not None and st.text else "libro")
        units = []
        for u in (vol.findall("./units/unit") if vol is not None else []):
            if u.attrib.get("features") != "flash" and u.attrib.get("btbid"):
                units.append(u.attrib["btbid"])
    units = [u for u in units if u]
    if not units:
        raise RuntimeError("Nessuna unità scaricabile trovata.")

    from pypdf import PdfWriter
    writer = PdfWriter()
    xps_dir = None
    i = 0
    while i < len(units):
        unit = units[i]
        progress(i, len(units), f"Scarico unità {i + 1}/{len(units)}…")
        cfg_r = requests.get(f"{BOOKTAB}/v1/resources_web/{isbn}/{unit}/config.xml",
                             headers=_h(cookie), timeout=20)
        if cfg_r.status_code != 200:
            i += 1
            continue
        cfg = _xml(cfg_r.text)
        content = cfg.findtext("./unit/content") or cfg.findtext("unit/content") or ""
        pdf_url = content
        fm = cfg.find("unit/filesMap") if cfg.find("unit/filesMap") is not None else cfg.find("filesMap")
        if fm is not None:
            for e in fm.findall("entry"):
                if e.attrib.get("key") == content + ".pdf":
                    pdf_url = (e.text or "").strip()
        if xps_dir is not None:
            xr = requests.get(f"{BOOKTAB}/v1/resources_web/{isbn}/{unit}/{content}.xod",
                              headers=_h(cookie), timeout=60)
            if not xr.ok:
                raise RuntimeError(f"Unità {i + 1} non scaricabile (HTTP {xr.status_code}).")
            with open(os.path.join(xps_dir, f"{i}_{unit}.xps"), "wb") as fh:
                fh.write(xr.content)
            i += 1
            continue
        pr = requests.get(f"{BOOKTAB}/v1/resources_web/{isbn}/{unit}/{pdf_url}.pdf",
                          headers=_h(cookie), timeout=60)
        if pr.status_code == 404:  # formato XPS: ricomincia salvando i singoli file
            xps_dir = os.path.join("xps_" + sanitize(title))
            os.makedirs(xps_dir, exist_ok=True)
            i = 0
            progress(0, len(units), "Formato XPS: scarico le singole unità…")
            continue
        if not pr.ok:
            raise RuntimeError(f"Unità {i + 1} non scaricabile (HTTP {pr.status_code}).")
        import io as _io
        from pypdf import PdfReader as _R
        for pg in _R(_io.BytesIO(pr.content)).pages:
            writer.add_page(pg)
        i += 1

    if xps_dir is not None:
        raise RuntimeError(
            f"Questo libro usa il formato XPS: file salvati in '{xps_dir}'. "
            "Convertili in PDF (es. xpstopdf.com) e uniscili (es. ilovepdf.com).")
    return writer, title


# ---------- Kitaboo ----------

def _decrypt_key(raw_private, enc_key_b64):
    pem = "-----BEGIN RSA PRIVATE KEY-----\n" + "\n".join(
        raw_private[i:i + 64] for i in range(0, len(raw_private), 64)
    ) + "\n-----END RSA PRIVATE KEY-----"
    key = RSA.import_key(pem)
    cipher = PKCS1_v1_5.new(key)
    return cipher.decrypt(base64.b64decode(enc_key_b64), None)


def _decrypt_page(enc_key: bytes, data_b64: str) -> bytes:
    k = enc_key[:16]
    cipher = AES.new(k, AES.MODE_CBC, k)
    return cipher.decrypt(base64.b64decode(data_b64))


def _download_kitaboo(location, progress):
    ru = requests.utils.urlparse(location)
    import urllib.parse as _up
    frag = _up.parse_qs(ru.fragment.split("?", 1)[-1] if "?" in ru.fragment else ru.fragment)
    # l'hash è del tipo #/reader?bookID=..&usertoken=..
    params = {}
    for part in ru.fragment.split("?")[-1].split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = _up.unquote(v)
    book_id, usertoken = params.get("bookID"), params.get("usertoken")
    if not book_id or not usertoken:
        raise RuntimeError("Link lettore non valido.")

    ex = requests.get(
        f"{MICRO}/user/123/pc/validateUserToken?usertoken={requests.utils.quote(usertoken)}",
        headers=UA_CHROME, timeout=20).json()
    usertoken = ex.get("userToken")
    if not usertoken:
        raise RuntimeError("Lettore non valido: riapri il libro e riprova.")

    det = requests.get(f"{DISTRIB}/123/pc/book/details?bookID={book_id}",
                       headers={**UA_CHROME, "usertoken": usertoken}, timeout=20).json()
    book = det["bookList"][0]["book"]

    db = requests.get(
        f"{READER}/downloadapi/auth/contentserver/book/123234234/HTML5/{book_id}/downloadBook?state=online",
        headers={**UA_CHROME, "Referer": READER + "/", "usertoken": usertoken}, timeout=20)
    if not db.ok:
        raise RuntimeError("Accesso al contenuto negato.")
    dj = db.json()
    setc = "; ".join(c.split(";")[0] for c in
                     db.headers.get("set-cookie", "").split(", ") if "=" in c)
    reader = {"ebookID": dj.get("ebookID") or dj.get("ebookId") or book.get("ebookID"),
              "cookie": setc, "jwt": dj["jwtToken"], "priv": dj["privateKey"]}

    def rh(extra=None):
        h = {**UA_CHROME, "Referer": READER + "/"}
        if reader["cookie"]:
            h["Cookie"] = reader["cookie"]
        if extra:
            h.update(extra)
        return h

    def ops(f):
        return f"{READER}/{reader['ebookID']}/html5/{reader['ebookID']}/OPS/{f}"

    if book.get("assetType") == "EPUB":
        raise RuntimeError("Libro di tipo EPUB liquido: non supportato in questa versione.")

    progress(0, 1, "Decifro la chiave del libro…")
    enc_key_txt = requests.get(ops("enc_resource.key"),
                               headers=rh({"authorization": reader["jwt"]}), timeout=20).text
    enc_key = _decrypt_key(reader["priv"], enc_key_txt.strip())
    if not enc_key:
        raise RuntimeError("Chiave di cifratura non decifrata.")

    opf = requests.get(ops("content.opf"), headers=rh(), timeout=20).text
    root = _xml(opf)
    ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
    t = root.find("opf:metadata/dc:title", ns)
    title = (t.text.strip() if t is not None and t.text else "zanichelli")
    items = {}
    for it in root.findall("opf:manifest/opf:item", ns):
        mt = it.attrib.get("media-type", "")
        if mt in ("image/svg+xml", "image/png", "image/jpeg"):
            items[it.attrib["id"]] = (it.attrib["href"], mt)
    spine = root.findall("opf:spine/opf:itemref", ns)

    doc = fitz.open()
    for i, ref in enumerate(spine):
        progress(i, len(spine), f"Pagina {i + 1}/{len(spine)}…")
        idx = ref.attrib["idref"]
        got = False
        for suffix in ("svgz", "png", "jpg"):
            key = f"images{idx}{suffix}"
            if key in items:
                href, mt = items[key]
                enc = requests.get(ops(href), headers=rh(), timeout=30).text
                raw = _decrypt_page(enc_key, enc)
                if mt == "image/svg+xml":
                    svg = fitz.open(stream=raw, filetype="svg")
                    doc.insert_pdf(fitz.open(stream=svg.convert_to_pdf(), filetype="pdf"))
                    svg.close()
                else:
                    img = fitz.open(stream=raw, filetype="png" if mt.endswith("png") else "jpeg")
                    r0 = img[0].rect
                    pg = doc.new_page(width=r0.width, height=r0.height)
                    pg.insert_image(r0, stream=raw)
                    img.close()
                got = True
                break
        if not got:
            continue
    return doc, title


# ---------- interfaccia standard ----------

def download(state, book_id, out_dir, options, progress):
    isbn = book_id.strip()
    book = (state.get("by_id") or {}).get(isbn)
    if book is None:
        for _b in list_books(state):
            pass
        book = (state.get("by_id") or {}).get(isbn)
    if book is None:
        raise RuntimeError("Libro non trovato nella tua libreria.")
    cookie = state["cookie"]

    progress(0, 1, "Riconosco il lettore…")
    r = requests.get(book["ereader_url"], headers=_h(cookie), timeout=20, allow_redirects=False)
    location = r.headers.get("location")
    if not location:
        raise RuntimeError("Lettore non disponibile: il libro potrebbe non essere scaricabile.")
    host = urlparse(location).hostname or ""

    if host == "web-booktab.zanichelli.it":
        progress(0, 1, "Libro BookTab…")
        from pypdf import PdfWriter
        writer, title = _download_booktab({"isbn": isbn}, cookie, progress)
        out = os.path.join(out_dir, sanitize(title) + ".pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
    else:
        progress(0, 1, "Libro Kitaboo…")
        doc, title = _download_kitaboo(location, progress)
        out = os.path.join(out_dir, sanitize(title) + ".pdf")
        doc.save(out)
        doc.close()
    progress(1, 1, "PDF salvato!")
    return out
