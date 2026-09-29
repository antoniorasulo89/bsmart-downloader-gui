"""Hoepli demo viewer (porting di Leone25/hoepli-demo-downloader).

Niente login: basta l'URL del libro demo. Le pagine vengono composte
(sfondo + livello testo SVG) direttamente in PDF con PyMuPDF,
senza bisogno del browser.
"""
import os
import re

import fitz
import requests

from .common import sanitize, UA_SIMPLE

LABEL = "Hoepli (demo pubbliche)"
AUTH_FIELDS = []
AUTH_HELP = "Nessun login: incolla l'URL della demo Hoepli."
ID_LABEL = "URL demo"
ID_HELP = "L'URL completo della demo (es. …/index.html)."
OPTIONS = []

NEEDS_LOGIN = False
NEEDS_LIST = False


def login(creds):
    return {}


def list_books(state):
    return []


def _pad(n):
    return ("000" + str(n))[-4:]


def download(state, book_url, out_dir, options, progress):
    url = (book_url or "").strip()
    if not url.startswith("http"):
        raise RuntimeError("Incolla l'URL completo della demo.")
    progress(0, 1, "Leggo la demo…")
    page = requests.get(url, headers=UA_SIMPLE, timeout=20).text
    m = re.search(r"<title>([^<]+)</title>", page)
    title = (m.group(1).strip() if m else "hoepli-demo")

    u = requests.utils.urlparse(url)
    path = re.sub(r"/(\d+/)?index\.html$", "", u.path)
    base = f"{u.scheme}://{u.netloc}{path}"
    pager = requests.get(base + "/files/assets/pager.js", headers=UA_SIMPLE, timeout=20).json()

    structure = pager["pages"]["structure"]
    defaults = pager["pages"].get("defaults", {})

    doc = fitz.open()
    for i, name in enumerate(structure):
        progress(i, len(structure), f"Pagina {i + 1}/{len(structure)}…")
        pg = dict(defaults)
        pg.update(pager["pages"].get(str(name), pager["pages"].get(name, {})))
        w, h = float(pg["width"]), float(pg["height"])
        page_pdf = doc.new_page(width=w, height=h)
        sub = requests.get(
            f"{base}/files/assets/common/page-html5-substrates/page{_pad(name)}_{pg['substrateSizesReady']}.{pg['substrateFormat']}",
            headers=UA_SIMPLE, timeout=30,
        )
        sub.raise_for_status()
        page_pdf.insert_image(fitz.Rect(0, 0, w, h), stream=sub.content)
        if pg.get("textLayer"):
            svg = requests.get(
                f"{base}/files/assets/common/page-vectorlayers/{_pad(name)}.svg",
                headers=UA_SIMPLE, timeout=30,
            )
            if svg.status_code == 200 and svg.content:
                try:
                    overlay = fitz.open(stream=svg.content, filetype="svg")
                    page_pdf.show_pdf_page(fitz.Rect(0, 0, w, h),
                                           overlay, 0, overlay_rect=overlay[0].rect)
                    overlay.close()
                except Exception:
                    pass  # pagina comunque salvata con lo sfondo

    progress(1, 1, "Salvo il PDF…")
    out = os.path.join(out_dir, sanitize(title) + ".pdf")
    doc.save(out)
    doc.close()
    progress(1, 1, "PDF salvato!")
    return out
