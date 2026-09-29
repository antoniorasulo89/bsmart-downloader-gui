"""Utilità condivise dai moduli delle piattaforme."""
import re
from . import network as requests

UA_SIMPLE = {"User-Agent": "Mozilla/5.0"}
UA_CHROME = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}


class LoginError(RuntimeError):
    """Credenziali errate o login non riuscito."""


def sanitize(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip().rstrip(". ")[:150] or "libro"


def new_session(ua=UA_SIMPLE):
    s = requests.Session()
    s.headers.update(ua)
    return s


# I dettagli di trasporto possono contenere password e token nelle URL.
def safe_error(error, secrets=()):
    if isinstance(error, requests.RequestException):
        return "Connessione non riuscita. Verifica la rete e riprova."
    if not isinstance(error, (RuntimeError, OSError)):
        return "Operazione non riuscita: risposta o contenuto inatteso."
    text = str(error)
    for secret in sorted((s for s in secrets if isinstance(s, str) and s), key=len, reverse=True):
        text = text.replace(secret, "[riservato]")
    text = re.sub(r"https?://[^\s<>]+", "[indirizzo riservato]", text)
    text = re.sub(r"(?i)(password|token|cookie|authorization|sessionid|username)([=:]\s*)[^\s&,;]+", r"\1\2[riservato]", text)
    return text[:400] or "Operazione non riuscita."


def valid_pdf(path):
    import pymupdf as fitz
    try:
        with fitz.open(path) as doc:
            return doc.is_pdf and not doc.needs_pass and len(doc) > 0
    except Exception:
        return False


def save_pdf(document, folder, name):
    """Valida prima della pubblicazione e non sovrascrive PDF esistenti."""
    from .network import check
    check()
    import os
    import tempfile
    from pathlib import Path
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = sanitize(name).rstrip('. ')
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', stem):
        stem = '_' + stem
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, suffix='.pdf', delete=False) as f:
            temporary = f.name
            if isinstance(document, bytes):
                f.write(document)
            elif hasattr(document, 'tobytes'):
                f.write(document.tobytes())
            else:
                document.write(f)
            f.flush()
            os.fsync(f.fileno())
        if not valid_pdf(temporary):
            raise RuntimeError('Il contenuto ricevuto non è un PDF valido. Nessun file salvato.')
        for i in range(1, 10000):
            target = folder / (stem + (f' ({i})' if i > 1 else '') + '.pdf')
            try:
                check()
                if os.name == "nt":
                    os.rename(temporary, target)
                    temporary = None
                else:
                    os.link(temporary, target)
                return str(target)
            except FileExistsError:
                continue
        raise RuntimeError('Troppi file con lo stesso nome nella cartella.')
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def checked_zip(archive):
    from pathlib import PurePosixPath
    total = 0
    if len(archive.infolist()) > 20000:
        raise RuntimeError('Archivio troppo grande.')
    for item in archive.infolist():
        name = item.filename.replace('\\', '/')
        parts = PurePosixPath(name).parts
        total += item.file_size
        if (name.startswith('/') or '..' in parts or ':' in name
                or (item.external_attr >> 16) & 0o170000 == 0o120000
                or item.file_size > 512 * 1024**2 or total > 2 * 1024**3):
            raise RuntimeError('Archivio non sicuro o troppo grande. Estrazione annullata.')
    return archive


def svg_pdf(raw, base=None):
    """Normalizza JPEG incorporati ed evita immagini ignorate dal convertitore."""
    import base64
    import gzip
    import mimetypes
    import xml.etree.ElementTree as ET
    from pathlib import Path
    import pymupdf as fitz
    if raw.startswith(b'\x1f\x8b'):
        raw = gzip.decompress(raw)
    raw = re.sub(br'data:image/jpg;', b'data:image/jpeg;', raw, flags=re.I)
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    root = ET.fromstring(raw)
    for element in root.iter():
        if element.tag.split('}')[-1] != 'image':
            continue
        key = next((k for k in element.attrib if k.split('}')[-1] == 'href'), None)
        if not key:
            raise RuntimeError('Pagina SVG con immagine senza risorsa.')
        href = element.attrib[key]
        if not href.startswith('data:'):
            if base is None or '://' in href:
                raise RuntimeError('Pagina SVG con immagine esterna non disponibile.')
            image = (Path(base) / href).resolve()
            if not image.is_relative_to(Path(base).resolve()) or not image.is_file():
                raise RuntimeError('Immagine della pagina mancante o non sicura.')
            href = 'data:' + (mimetypes.guess_type(image)[0] or 'image/png') + ';base64,' + base64.b64encode(image.read_bytes()).decode()
            element.attrib[key] = href
        try:
            header, payload = href.split(',', 1)
            if ';base64' not in header:
                raise ValueError()
            decoded = base64.b64decode(payload, validate=True)
            with fitz.open(stream=decoded) as image:
                if not len(image):
                    raise ValueError()
        except Exception:
            raise RuntimeError('Immagine incorporata non valida: conversione annullata.') from None
    with fitz.open(stream=ET.tostring(root), filetype='svg') as svg:
        return svg.convert_to_pdf()


def response_json(response):
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Il servizio ha restituito una risposta non valida.") from None
    if not isinstance(data, (dict, list)):
        raise RuntimeError("Il servizio ha restituito dati inattesi.")
    return data


def secret_values(state):
    values = []
    if isinstance(state, dict):
        for key, value in state.items():
            if isinstance(value, dict):
                values.extend(secret_values(value))
            elif isinstance(value, str) and any(word in key.lower() for word in ('token','password','cookie','session','jwt','privatekey','email')):
                values.append(value)
    return values
