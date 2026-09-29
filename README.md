# 📚 ScaricaLibri — downloader multi-piattaforma

Interfaccia facile in **3 passi** per scaricare i tuoi libri scolastici come PDF offline.
Scegli la piattaforma, accedi, tocca il libro, premi SCARICA. Facile quasi come un gioco. 🎮

Porting Python dei downloader di [Leone25](https://github.com/Leone25).

| Piattaforma | Login | Cosa serve |
|---|---|---|
| bSmart / digibook24 | email + password | toccare il libro nella lista |
| Sanoma | email + password | toccare il libro nella lista |
| Zanichelli (BookTab + Kitaboo) | email + password | toccare il libro nella lista |
| HUB Scuola (Young + Kids) | email + password | toccare il libro nella lista |
| MyLim (Loescher) | email + password | toccare il libro nella lista |
| Hoepli demo | nessuno | URL della demo |

## ⬇️ Scarica (niente Python, niente terminale)

| Sistema | Download |
|---|---|
| 🪟 Windows | **[ScaricaLibri-Windows.exe](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/ScaricaLibri-Windows.exe)** |
| 🐧 Linux | **[ScaricaLibri-Linux](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/ScaricaLibri-Linux)** (poi `chmod +x ScaricaLibri-Linux`) |
| 🍎 macOS | **[ScaricaLibri-macOS](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/ScaricaLibri-macOS)** |

Doppio click e via. Spunta **🔑 Ricordami** per non ridigitare più le credenziali
(salvate cifrate: DPAPI su Windows, Keychain su macOS, Secret Service su Linux).

## Come ottenere token manuali (solo se il login con credenziali non va)

- **HUB Scuola**: apri il libro nel lettore web, F12 → Rete, ricarica,
  clicca la richiesta con il Volume ID, copia `token-session`.
- **MyLim**: su mylim.loescher.it fai login, F12 → Applicazione →
  Archiviazione locale → copia `token`.
- **bSmart con Google/Microsoft**: F12 → Cookie → `_bsw_session_v1_production`
  (campo facoltativo nella schermata bSmart).

## Avvio da sorgente

```bash
pip install -r requirements.txt
python app_gui.py
```

## Creare l'eseguibile da soli

- Windows: doppio click su `build_exe.bat`
- Linux/macOS: `pip install -r requirements.txt` poi il comando `pyinstaller …`
  riportato in `.github/workflows/build.yml`
- In automatico: ogni tag `v*` pushato su GitHub compila i 3 sistemi e allega
  i file alla release.

## Test

```bash
python test_all.py
```

## Nota legale

Solo backup personale di libri acquistati. Verifica la normativa del tuo paese.
Logica originale di [Leone25](https://github.com/Leone25) (licenza MIT).
