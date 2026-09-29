# Folio

**La tua biblioteca, offline.**

Identità locale proposta per l’evoluzione di ScaricaLibri. Il nome non implica affiliazioni con gli editori.

## Direzione

Un’app desktop con il carattere di una biblioteca editoriale: calma, leggibile e pratica. La parola Folio richiama la pagina e la raccolta di volumi. Il marchio è un logotipo serif accompagnato da un monogramma F geometrico per l’icona dell’app.

## Sistema visivo

| Ruolo | Colore |
|---|---|
| Carta, fondo principale | `#F4F2ED` |
| Blu inchiostro, barra laterale | `#142B3B` |
| Testo principale | `#182C3C` |
| Azioni e selezioni | `#19645C` |
| Testo secondario | `#586774` |
| Superfici | `#FFFFFF` |
| Bordi | `#D7DDD9` |
| Errori e rimozione account | `#A13E30` |

Georgia per il marchio e i titoli editoriali; Segoe UI per comandi, campi e informazioni. Le alternative di sistema vengono usate dove questi font non sono disponibili. Il verde indica azioni e selezioni; il colore è sempre accompagnato da testo o bordi. Niente emoji o messaggi celebrativi.

## Navigazione

- **Biblioteca**: scegli una piattaforma, collega l’account, cerca un titolo, selezionalo e prepara il download nel pannello laterale.
- **Account e accessi**: configura email e password; token e cookie sono disponibili nella sezione avanzata. L’accesso e il salvataggio sono azioni distinte.
- La piattaforma corrente è sempre visibile. Le sessioni rimangono disponibili quando si passa da una piattaforma all’altra.

## Stati e consenso

La biblioteca distingue account da collegare, caricamento, lista vuota, ricerca senza risultati e titoli non disponibili. Durante le operazioni il cambio di piattaforma e gli avvii duplicati sono bloccati. Al completamento compare il comando per aprire la cartella.

Le credenziali non sono salvate automaticamente. L’utente sceglie esplicitamente il salvataggio nel portachiavi; senza spunta restano in memoria. Salvare senza spunta rimuove la copia persistente. Rimuovere l’account elimina credenziali e sessione. Nessun fallback per nuovi salvataggi in chiaro.

## Tono

Frasi brevi, italiane, orientate al compito: “Collega account”, “Scarica PDF”, “Credenziali disponibili solo per questa sessione”. Gli errori indicano il problema; i dettagli tecnici restano nel registro espandibile.

## Anteprime e distribuzione

Le immagini della biblioteca con titoli sono schermate della GUI reale alimentate con dati dimostrativi, non download effettuati. Il progetto conserva il servizio del portachiavi ScaricaLibri per riconoscere le credenziali precedenti. Le release remote non sono state modificate.

## Biblioteca locale

**Biblioteca** mostra i PDF scaricati che esistono ancora sul dispositivo, indipendentemente dall’account attivo. L’indice sopravvive ai riavvii e viene controllato aprendo la pagina, tornando all’app o premendo **Aggiorna**. I nuovi PDF nella cartella di destinazione vengono riconosciuti; per altri file già scaricati usa **Aggiungi PDF**. Un file spostato o eliminato scompare dalla lista; può essere aggiunto dalla nuova posizione. Ogni titolo offre **Apri PDF** e **Cartella**. **Nuovi download** contiene invece i titoli disponibili sulla piattaforma.
