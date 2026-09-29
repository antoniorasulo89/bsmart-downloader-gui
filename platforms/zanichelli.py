"""Zanichelli (rif. Leone25/zanichelli-downloader + scuolabooks-reloaded).

Login email+password → libreria → download automatico sia per libri
BookTab (PDF diretti) sia per libri Kitaboo (pagine cifrate).
"""
import base64
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote, quote

import fitz
import requests
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA

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
    if d.status_code >= 400:
        raise LoginError("Sessione non inizializzata. Riprova.")
    myz = s.cookies.get("myz_token")
    if not myz:
        raise LoginError("Login riuscito ma sessione non ottenuta. Riprova.")
    full_cookie = cookie + "".join(
        f"; {c.name}={c.value}" for c in s.cookies if c.name != "token")
    # inizializza la dashboard (richiesto per accedere alla lista libri)
    u = s.get(f"{CATALOG}/dashboard/user", headers={"myz-token": myz}, timeout=20)
    if u.status_code in (401, 403):
        raise LoginError("Sessione non valida. Riprova il login.")
    return {"cookie": full_cookie, "myz": myz, "token": token}


def _add_licenses(books, licenses):
    for lic in licenses or []:
        vol = (lic.get("volume") or {})
        if not vol.get("ereader_url") or not vol.get("isbn"):
            continue
        books[str(vol["isbn"])] = {
            "title": ((vol.get("opera") or {}).get("title")) or "?",
            "ereader_url": vol["ereader_url"],
        }


def list_books(state):
    myz = state["myz"]
    dbg = state.setdefault("_debug", [])
    books, page = {}, 1
    while True:
        r = requests.get(
            f"{CATALOG}/dashboard/search?sort%5Bfield%5D=year_date&sort%5Bdirection%5D=desc"
            f"&searchString&pageNumber={page}&rows=100",
            headers=_h(myz=myz), timeout=20)
        if r.status_code == 403:
            dbg.append(f"search pagina {page}: HTTP 403 (accesso negato)")
            break
        if not r.ok:
            raise RuntimeError(f"Elenco libri non disponibile (HTTP {r.status_code}).")
        payload = r.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        lic = data.get("licenses") or []
        with_url = sum(1 for l in lic if (l.get("volume") or {}).get("ereader_url"))
        dbg.append(f"search pagina {page}: {len(lic)} licenze, {with_url} con URL lettore; "
                   f"chiavi data={sorted(data.keys())[:8]}")
        _add_licenses(books, lic)
        pages = (data.get("pagination") or {}).get("pages", 0)
        if not pages or pages == page:
            break
        page += 1
    try:
        rl = requests.get(f"{CATALOG}/dashboard/licenses/real", headers=_h(myz=myz), timeout=20)
        if rl.ok:
            real = (rl.json().get("realLicenses") or [])
            dbg.append(f"licenses/real: {len(real)} licenze")
            _add_licenses(books, real)
        else:
            dbg.append(f"licenses/real: HTTP {rl.status_code}")
    except Exception as e:
        dbg.append(f"licenses/real: errore {e}")
    state["by_id"] = books
    return [{"id": k, "title": v["title"]} for k, v in books.items()]


# ---------- risoluzione lettore ----------

def _resolve_reader_url(location, cookie):
    """Segue i redirect fino al lettore reale (booktab o webreader)."""
    try:
        r = requests.get(location, headers={**UA_CHROME, "Referer": "https://my.zanichelli.it/",
                                            "Cookie": cookie},
                         timeout=20, allow_redirects=True)
        for item in r.history:
            loc = item.headers.get("location")
            if loc:
                host = urlparse(loc).hostname or ""
                if host in ("web-booktab.zanichelli.it", "webreader.zanichelli.it"):
                    return loc
        return r.url or location
    except Exception:
        return location


def _parse_qs_nostrict(text):
    """Parse query/fragment senza trasformare '+' in spazio (i token lo usano)."""
    out = {}
    for part in (text or "").split("&"):
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out.setdefault(unquote(k), []).append(unquote(v))
    return out


def _grab_params(url):
    p = urlparse(url)
    frag = p.fragment.lstrip("#")
    if "?" in frag:
        frag = frag.split("?", 1)[1]
    q = _parse_qs_nostrict(p.query)
    f = _parse_qs_nostrict(frag)
    bid = (f.get("bookID") or f.get("bookId") or q.get("bookID") or q.get("bookId") or [None])[0]
    tok = (f.get("usertoken") or f.get("userToken") or q.get("usertoken") or q.get("userToken") or [None])[0]
    return bid, tok


def _extract_token(payload):
    if isinstance(payload, dict):
        for k in ("userToken", "usertoken", "token"):
            if isinstance(payload.get(k), str) and payload[k]:
                return payload[k]
        for v in payload.values():
            t = _extract_token(v)
            if t:
                return t
    elif isinstance(payload, list):
        for v in payload:
            t = _extract_token(v)
            if t:
                return t
    return None


def _validate_kitaboo_token(usertoken):
    raw = usertoken.strip().strip("\"'")
    variants = [raw, raw.replace(" ", "+"), unquote(raw),
                unquote(raw).replace(" ", "+"),
                unquote(unquote(raw)), unquote(unquote(raw)).replace(" ", "+")]
    seen, last = set(), None
    for v in variants:
        if not v or v in seen:
            continue
        seen.add(v)
        try:
            r = requests.get(
                f"{MICRO}/user/123/pc/validateUserToken?usertoken={quote(v, safe='')}",
                headers=UA_CHROME, timeout=20)
            r.raise_for_status()
            last = r.json()
            t = _extract_token(last)
            if t:
                return t
        except Exception:
            continue
    raise RuntimeError("Token lettore non accettato. Riapri il libro e riprova.")


def _extract_kitaboo_params(reader_url, cookie):
    cands = []
    bid, tok = _grab_params(reader_url)
    cands.append((bid, tok))
    try:
        r = requests.get(reader_url, headers={**UA_CHROME, "Referer": READER + "/",
                                              "Cookie": cookie},
                         timeout=20, allow_redirects=True)
        cands.append(_grab_params(r.url))
        for item in r.history:
            loc = item.headers.get("location")
            if loc:
                cands.append(_grab_params(loc))
        html = r.text
        hb = re.search(r'"?bookID"?\s*[:=]\s*"?([A-Za-z0-9_-]+)', html)
        ht = re.search(r'"?usertoken"?\s*[:=]\s*"?([^&"\'\s<]+)', html, re.I)
        if not ht:
            ht = re.search(r'"?userToken"?\s*[:=]\s*"?([^&"\'\s<]+)', html)
        cands.append((hb.group(1) if hb else None, ht.group(1) if ht else None))
    except Exception:
        pass
    for bid, tok in cands:
        if bid and tok:
            return bid, tok
    raise RuntimeError("Parametri del lettore non trovati. Riapri il libro e riprova.")


# ---------- crypto ----------

def _decrypt_key(raw_private, enc_key_b64):
    pem = ("-----BEGIN RSA PRIVATE KEY-----\n"
           + "\n".join(raw_private[i:i + 64] for i in range(0, len(raw_private), 64))
           + "\n-----END RSA PRIVATE KEY-----")
    key = RSA.import_key(pem)
    return PKCS1_v1_5.new(key).decrypt(base64.b64decode(enc_key_b64), None)


def _unpad(data):
    pad = data[-1]
    if 1 <= pad <= 16 and data.endswith(bytes([pad]) * pad):
        return data[:-pad]
    return data


def _decrypt_page(enc_key: bytes, data_b64: str) -> bytes:
    k = enc_key[:16]
    return _unpad(AES.new(k, AES.MODE_CBC, k).decrypt(base64.b64decode(data_b64)))


def _pick_manifest(manifest, idref):
    """Trova l'href della pagina nei vari formati usati dal reader."""
    for sfx in ("svgz", "svg", "png", "jpg", "jpeg"):
        for cand in (f"images/{idref}.{sfx}", f"images{idref}{sfx}"):
            if cand in manifest:
                return manifest[cand]
    return None


# ---------- BookTab ----------

def _download_booktab(isbn, cookie, progress):
    s = requests.post(f"{BOOKTAB}/v1/sessions_web", headers=_h(cookie), timeout=20)
    if not s.ok:
        raise RuntimeError("Sessione BookTab non creata.")
    cookie = f"{cookie}; booktab_token={s.json()['session']}"

    root = None
    for name in ("spine.xml", "volume.xml"):
        r = requests.get(f"{BOOKTAB}/v1/resources_web/{isbn}/{name}", headers=_h(cookie), timeout=20)
        if r.status_code == 404:
            continue
        if not r.ok:
            raise RuntimeError(f"Struttura libro non disponibile (HTTP {r.status_code}).")
        root = ET.fromstring(r.text)
        break
    if root is None:
        raise RuntimeError("Libro non scaricabile (indice mancante).")

    vt = root.find(".//volumetitle")
    title = (vt.text.strip() if vt is not None and vt.text else "libro")
    units = [u.attrib["btbid"] for u in root.iter("unit")
             if u.attrib.get("btbid") and u.attrib.get("features") != "flash"]
    if not units:
        raise RuntimeError("Nessuna unità scaricabile trovata.")

    from pypdf import PdfReader, PdfWriter
    import io as _io
    writer, count = PdfWriter(), 0
    for i, unit in enumerate(units):
        progress(i, len(units), f"Scarico unità {i + 1}/{len(units)}…")
        cfg_r = requests.get(f"{BOOKTAB}/v1/resources_web/{isbn}/{unit}/config.xml",
                             headers=_h(cookie), timeout=20)
        if cfg_r.status_code != 200:
            continue
        cfg = ET.fromstring(cfg_r.text)
        content = (cfg.findtext(".//content") or "").strip()
        if not content:
            continue
        pdf_key = content
        for e in cfg.iter("entry"):
            if e.attrib.get("key") == content + ".pdf" and (e.text or "").strip():
                pdf_key = e.text.strip()
        pr = requests.get(f"{BOOKTAB}/v1/resources_web/{isbn}/{unit}/{pdf_key}.pdf",
                          headers=_h(cookie), timeout=120)
        if pr.status_code == 404:
            raise RuntimeError(
                "Questo libro usa il formato XPS: non scaricabile in automatico. "
                "Prova un altro volume.")
        if not pr.ok:
            raise RuntimeError(f"Unità {i + 1} non scaricabile (HTTP {pr.status_code}).")
        for pg in PdfReader(_io.BytesIO(pr.content)).pages:
            writer.add_page(pg)
            count += 1
    if count == 0:
        raise RuntimeError("Nessuna pagina scaricata.")
    return writer, title


# ---------- Kitaboo ----------

def _download_kitaboo(location, cookie, progress):
    book_id, usertoken = _extract_kitaboo_params(location, cookie)
    progress(0, 1, "Validazione lettore…")
    usertoken = _validate_kitaboo_token(usertoken)

    det = requests.get(f"{DISTRIB}/123/pc/book/details?bookID={book_id}",
                       headers={**UA_CHROME, "usertoken": usertoken}, timeout=20).json()
    book = det["bookList"][0]["book"]

    db = requests.get(
        f"{READER}/downloadapi/auth/contentserver/book/123234234/HTML5/{book_id}/downloadBook?state=online",
        headers={**UA_CHROME, "Referer": READER + "/", "usertoken": usertoken}, timeout=30)
    if not db.ok:
        raise RuntimeError("Accesso al contenuto negato.")
    dj = db.json()
    setc = "; ".join(c.split(";")[0] for c in db.headers.get("set-cookie", "").split(", ") if "=" in c)
    ebook_id = dj.get("ebookID") or dj.get("ebookId") or book.get("ebookID")
    jwt, priv = dj["jwtToken"], dj["privateKey"]

    def rh(extra=None):
        h = {**UA_CHROME, "Referer": READER + "/"}
        if setc:
            h["Cookie"] = setc
        if extra:
            h.update(extra)
        return h

    def ops(f):
        return f"{READER}/{ebook_id}/html5/{ebook_id}/OPS/{f}"

    if book.get("assetType") == "EPUB":
        raise RuntimeError("Libro EPUB liquido: non supportato in questa versione.")

    progress(0, 1, "Decifro la chiave del libro…")
    enc_txt = requests.get(ops("enc_resource.key"), headers=rh({"authorization": jwt}), timeout=20).text
    enc_key = _decrypt_key(priv, enc_txt.strip())
    if not enc_key:
        raise RuntimeError("Chiave di cifratura non decifrata.")

    root = ET.fromstring(requests.get(ops("content.opf"), headers=rh(), timeout=20).text)
    ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
    t = root.find("opf:metadata/dc:title", ns)
    title = (t.text.strip() if t is not None and t.text else "zanichelli")
    manifest = {}
    for it in root.findall("opf:manifest/opf:item", ns):
        if it.attrib.get("media-type") in ("image/svg+xml", "image/png", "image/jpeg"):
            manifest[it.attrib["id"]] = (it.attrib["href"], it.attrib["media-type"])
    spine = root.findall("opf:spine/opf:itemref", ns)
    if not spine:
        raise RuntimeError("Indice pagine vuoto.")

    doc, done = fitz.open(), 0
    for i, ref in enumerate(spine):
        progress(i, len(spine), f"Pagina {i + 1}/{len(spine)}…")
        picked = _pick_manifest(manifest, ref.attrib["idref"])
        if not picked:
            continue
        href, mt = picked
        try:
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
            done += 1
        except Exception:
            continue
    if done == 0:
        raise RuntimeError("Nessuna pagina decifrata (formato inatteso?).")
    return doc, title


# ---------- interfaccia standard ----------

def download(state, book_id, out_dir, options, progress):
    isbn = book_id.strip()
    book = (state.get("by_id") or {}).get(isbn)
    if book is None:
        list_books(state)
        book = (state.get("by_id") or {}).get(isbn)
    if book is None:
        raise RuntimeError("Libro non trovato nella tua libreria.")
    cookie = state["cookie"]

    progress(0, 1, "Riconosco il lettore…")
    r = requests.get(book["ereader_url"], headers=_h(cookie), timeout=20, allow_redirects=False)
    location = r.headers.get("location")
    if not location:
        raise RuntimeError("Lettore non disponibile: il libro potrebbe non essere scaricabile.")
    final = _resolve_reader_url(location, cookie)
    host = urlparse(final).hostname or ""

    if "booktab" in host:
        progress(0, 1, "Libro BookTab…")
        writer, title = _download_booktab(isbn, cookie, progress)
        out = os.path.join(out_dir, sanitize(title) + ".pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
    elif "webreader" in host:
        progress(0, 1, "Libro Kitaboo…")
        doc, title = _download_kitaboo(final, cookie, progress)
        out = os.path.join(out_dir, sanitize(title) + ".pdf")
        doc.save(out)
        doc.close()
    else:
        raise RuntimeError(f"Lettore non riconosciuto ({host}).")
    progress(1, 1, "PDF salvato!")
    return out
