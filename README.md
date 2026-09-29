# bSmart Downloader GUI

Interfaccia grafica facile per scaricare i tuoi libri bSmart / digibook24 come PDF offline.
Basata su [Leone25/bSmart-downloader](https://github.com/Leone25/bSmart-downloader).

## ⬇️ Scarica (Windows, niente Python)

**[Scarica bSmartDownloaderGUI.exe](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/bSmartDownloaderGUI.exe)**

Doppio click e via: inserisci email + password bSmart, scegli il libro, premi SCARICA PDF.

## Uso

1. Apri `bSmartDownloaderGUI.exe`
2. Scegli il sito (bSmart o digibook24)
3. Inserisci email e password del tuo account bSmart → **ACCEDI E CARICA I MIEI LIBRI**
4. Seleziona il libro dalla lista (o scrivi l'ID a mano)
5. Scegli la cartella → **SCARICA PDF**

> **Login con Google / Microsoft / account editore?**
> Usa il riquadro "Avanzato" con il cookie manuale `_bsw_session_v1_production`
> (F12 → Archiviazione/Applicazione → Cookie → `my.bsmart.it`).

## Avvio da sorgente

```bat
pip install -r requirements.txt
python bsmart_gui.py
```

## Creare l'exe da soli

Doppio click su `build_exe.bat` → trovi `dist\bSmartDownloaderGUI.exe`.

## Nota legale

Usa il programma solo per backup personale dei libri che hai acquistato.
Verifica la normativa del tuo paese. Crediti per la logica originale a
[Leone25](https://github.com/Leone25/bSmart-downloader) (licenza MIT).
