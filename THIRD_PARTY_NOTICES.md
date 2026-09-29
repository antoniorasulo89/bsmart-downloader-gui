# Componenti e attribuzioni

Questa build locale include le dipendenze elencate sotto; i rispettivi testi sono conservati in `THIRD_PARTY_LICENSES/`. Queste licenze appartengono ai singoli componenti e non definiscono automaticamente la licenza del progetto Folio.

PyMuPDF/MuPDF è disponibile sotto AGPL oppure licenza commerciale Artifex: https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright . Una dichiarazione MIT per l’intero eseguibile non descrive correttamente questo insieme di componenti. La scelta della licenza del progetto e la distribuzione pubblica devono rispettare i termini dei componenti; questo intervento locale non pubblica una nuova release né attribuisce al titolare una licenza commerciale.

| Componente | Versione | Licenza dichiarata nel pacchetto |
|---|---|---|
| requests | 2.34.2 | Apache-2.0 |
| pypdf | 6.19.0 | BSD-3-Clause |
| pymupdf | 1.28.2 | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License |
| msgpack | 1.2.3 | Apache-2.0 |
| pycryptodome | 3.23.0 | BSD, Public Domain |
| customtkinter | 6.0.0 | Creative Commons Zero v1.0 Universal |
| filelock | 4.0.6 | MIT |
| urllib3 | 2.8.0 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| charset-normalizer | 3.5.1 | MIT |
| idna | 3.20 | BSD-3-Clause |
| darkdetect | 0.8.0 | BSD-3-Clause |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pyinstaller | 6.22.3 | GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones) |

Riferimenti dei porting:
- bSmart, Sanoma, MyLim e Zanichelli: https://github.com/Leone25 . I moduli indicano il progetto originale nella propria intestazione.
- HUB: https://github.com/vvettoretti/hubscuola-downloader .
- La provenienza completa di eventuali frammenti derivati da scuolabooks-reloaded non è stata verificata; non viene assegnata una licenza per supposizione.
- Python e Tcl/Tk mantengono le proprie licenze originali nei runtime distribuiti dai rispettivi progetti. Font Georgia e Segoe UI sono richiesti al sistema operativo, non redistribuiti come file font.
