# Folio — La tua biblioteca, offline.

App desktop per raccogliere i tuoi libri scolastici in PDF. Scegli la piattaforma nella barra laterale, collega l’account e prepara il download dalla biblioteca. Evoluzione di ScaricaLibri.

Porting Python dei downloader di [Leone25](https://github.com/Leone25).

| Piattaforma | Login | Cosa serve |
|---|---|---|
| bSmart / digibook24 | email + password | selezionare il libro nella biblioteca |
| Sanoma | email + password | selezionare il libro nella biblioteca |
| Zanichelli (BookTab + Kitaboo) | email + password | selezionare il libro nella biblioteca |
| HUB Scuola (Young + Kids) | email + password | selezionare il libro nella biblioteca |
| MyLim (Loescher) | email + password | selezionare il libro nella biblioteca |

## Release pubblicate

Le release esistenti usano ancora il nome ScaricaLibri. La nuova interfaccia Folio è nel codice locale; questi link puntano alle release già pubblicate.

| Sistema | Download |
|---|---|
| 🪟 Windows | **[ScaricaLibri-Windows.exe](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/ScaricaLibri-Windows.exe)** |
| 🐧 Linux | **[ScaricaLibri-Linux](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/ScaricaLibri-Linux)** (poi `chmod +x ScaricaLibri-Linux`) |
| 🍎 macOS | **[ScaricaLibri-macOS](https://github.com/antoniorasulo89/bsmart-downloader-gui/releases/latest/download/ScaricaLibri-macOS)** |

Apri **Account e accessi** per configurare ogni piattaforma, poi premi **Collega e carica biblioteca**.
Il salvataggio è disattivato inizialmente: i dati restano solo in memoria.
Per conservarli, seleziona **Conserva le credenziali su questo dispositivo** e premi **Salva preferenze**.
Deselezionando l’opzione e salvando, rimuovi la copia persistente e mantieni i dati per la sessione.
Il portachiavi usa DPAPI su Windows, Keychain su macOS e Secret Service su Linux; senza un backend sicuro il salvataggio viene rifiutato.
**Rimuovi account e credenziali** rimuove i dati salvati e chiude la sessione. Le credenziali già salvate nel portachiavi sono riconosciute.
Durante accessi e download, il cambio di piattaforma e le operazioni duplicate sono bloccati.

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
- Linux/macOS: `pip install -r requirements-build.txt` poi il comando `pyinstaller …`
  riportato in `.github/workflows/build.yml`
- In automatico: ogni tag `v*` pushato su GitHub compila i 3 sistemi e allega
  i file alla release.

## Test

```bash
python test_all.py
python test_security.py
```

## Nota legale

Solo backup personale di libri acquistati. Verifica la normativa del tuo paese.
Attribuzioni e licenze dei componenti in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). La licenza MIT dei porting originali non equivale alla licenza dell’intero bundle, che include PyMuPDF/MuPDF.

## Identità visiva

Vedi [BRAND.md](BRAND.md) per il sistema visivo e i flussi della nuova interfaccia.

Le prossime build usano il nome **Folio** (`Folio-Windows.exe`, `Folio-Linux`, `Folio-macOS`); il servizio del portachiavi mantiene il nome precedente per compatibilità.

## Biblioteca locale

**Biblioteca** mostra i PDF scaricati che esistono ancora sul dispositivo, indipendentemente dall’account attivo. L’indice sopravvive ai riavvii e viene controllato aprendo la pagina, tornando all’app o premendo **Aggiorna**. I nuovi PDF nella cartella di destinazione vengono riconosciuti; per altri file già scaricati usa **Aggiungi PDF**. Un file spostato o eliminato scompare dalla lista; può essere aggiunto dalla nuova posizione. Ogni titolo offre **Apri PDF** e **Cartella**. **Nuovi download** contiene invece i titoli disponibili sulla piattaforma.


## Affidabilità e sicurezza (3.1.0.dev1)

- Nuovi account: conservazione soltanto con scelta esplicita. Account già conservati: checkbox coerente con il portachiavi. Errori di lettura/cifratura non cancellano l’archivio precedente; scritture atomiche e aggiornamenti protetti tra istanze.
- Windows DPAPI, macOS Keychain aggiornato senza cancellazione preventiva, Linux Secret Service. Il vecchio archivio Linux in chiaro viene segnalato nella pagina Account e può essere rimosso con un’azione esplicita; non viene riscritto in chiaro.
- Download incompleti, ZIP con percorsi non sicuri e risposte HTML al posto dei PDF vengono rifiutati. I PDF sono validati prima della pubblicazione. Download ripetuti ricevono un nome distinto; allegati pubblicati in una cartella nuova.
- SVG: normalizzazione JPEG incorporati, controllo delle immagini e supporto SVG compressi. Risorse mancanti interrompono la conversione.
- Annullamento e chiusura controllata; letture HTTP limitate, timeout, deadline di 15 minuti e tre tentativi per GET transitori. POST di accesso non ritentati automaticamente. La cancellazione durante una richiesta può attendere il timeout di rete.
- Biblioteca verificata in background, ricerca con breve ritardo e massimo 100 risultati mostrati per ricerca. Un indice corrotto viene conservato in una copia prima della ricostruzione.
- digibook24 usa il cookie dell’accesso editore nel browser; le sue password non vengono inviate al login bSmart.
- Dipendenze con versioni fissate e build isolata. `requirements-build.txt` include gli strumenti di compilazione e controllo. La CI esegue test e prova del bundle prima dell’upload; le build Linux/macOS devono ancora essere eseguite sui rispettivi runner.

La nuova build è locale di sviluppo, non una release pubblicata.
