# bSmart Downloader — Interfaccia Grafica

Interfaccia facile per https://github.com/Leone25/bSmart-downloader
Non serve più il terminale: apri il programma, incolli il cookie, scegli il libro, premi Scarica.

## File creati
- `bsmart_gui.py` → il programma con finestra
- `requirements.txt` → librerie necessarie
- `build_exe.bat` → crea il file .exe in un click

## Uso veloce (senza .exe)
1. Installa Python 3.10+ da python.org (spunta "Add python to PATH")
2. Doppio click su `build_exe.bat` OPPURE da terminale:
```
pip install -r requirements.txt
python bsmart_gui.py
```
3. Nel programma:
   - Scegli sito: bSmart o digibook24
   - Incolla il cookie `_bsw_session_v1_production` (pulsante "Come trovo il cookie?" spiega come)
   - Premi "Accedi e carica i miei libri"
   - Seleziona il libro dalla lista (o scrivi l'ID a mano, quello dopo `/books/` nell'URL)
   - Scegli la cartella, premi "SCARICA PDF"

## Creare il file .exe
1. Doppio click su `build_exe.bat`
2. Alla fine trovi `dist\bSmartDownloaderGUI.exe`
3. Puoi copiare solo quel file .exe su qualsiasi PC Windows (non serve Python)

Nota: il primo avvio dell'exe può richiedere qualche secondo.

## Note legali
Come il progetto originale: usa il programma solo per backup personale dei libri che hai acquistato. Verifica la normativa del tuo paese.
