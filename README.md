# ScaricaLibri — downloader multi-piattaforma

Interfaccia grafica unica per scaricare i tuoi libri scolastici come PDF offline.
Porting Python dei downloader di [Leone25](https://github.com/Leone25):

| Piattaforma | Login | Cosa serve |
|---|---|---|
| bSmart / digibook24 | email + password | ID libro (dalla lista) |
| Sanoma | email + password | gedi (dalla lista) |
| Zanichelli (BookTab + Kitaboo) | email + password | ISBN (dalla lista) |
| HUB Young / HUB Kids | token-session manuale | Volume ID dall'URL |
| MyLim (Loescher) | token JWT manuale | ISBN (dalla lista) |
| Hoepli demo | nessuno | URL della demo |

## ⬇️ Scarica (Windows, niente Python)

**[Scarica ScaricaLibri.exe](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/ScaricaLibri.exe)**

Doppio click e via: scegli la piattaforma, accedi, scegli il libro, premi SCARICA.

## Come ottenere token manuali

- **HUB Young/Kids**: apri il libro nel lettore web, F12 → Rete, ricarica,
  clicca la richiesta con il Volume ID, copia `token-session`.
  Il Volume ID è il numero dopo `/viewer/` nell'URL.
- **MyLim**: su mylim.loescher.it fai login, F12 → Applicazione →
  Archiviazione locale → copia `token`.
- **bSmart con Google/Microsoft**: F12 → Cookie → `_bsw_session_v1_production`
  (campo facoltativo nella schermata bSmart).

## Avvio da sorgente

```bat
pip install -r requirements.txt
python app_gui.py
```

## Creare l'exe da soli

Doppio click su `build_exe.bat` → `dist\ScaricaLibri.exe`.

## Test

```bat
python test_all.py
```

## Nota legale

Solo backup personale di libri acquistati. Verifica la normativa del tuo paese.
Logica originale di [Leone25](https://github.com/Leone25) (licenza MIT).
