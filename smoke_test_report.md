# Smoke test — ScortaLab (cruscotto_scorte.html)

Data: 2026-09-29T14:21:08.952Z · File testato: cruscotto_scorte.html (vero \<script\> eseguito in Node con fake DOM) · Casi: 44 · PASS: 44 · FAIL: 0

Regola: punto = consumo × giorni + sicurezza; riordina se scorta ≤ punto.

| ID | Caso | Esito | Dettaglio |
|---|---|---|---|
| A01 | A100: 4x5+8=28, scorta 12 -> RIORDINARE | PASS | punto=28, scorta=12, badge RIORDINARE presente |
| A02 | B200: 5x4+10=30, scorta 60 -> SCORTA OK | PASS | punto=30, scorta=60 OK; KPI 4/2/2/0 |
| A03 | C300: 1x10+3=13, scorta 7 -> RIORDINARE | PASS | punto=13, scorta=7 -> RIORDINARE |
| A04 | D400: 3x7+6=27, scorta 40 -> SCORTA OK | PASS | punto=27, scorta=40 -> OK |
| A05 | Scenario B200 giorni=12 -> 5x12+10=70 -> RIORDINARE | PASS | B200 punto=70 -> RIORDINARE (3 riordini totali) |
| B06 | Uguaglianza scorta=punto -> RIORDINARE (<=) | PASS | 28<=28 -> RIORDINARE |
| B07 | Scorta punto+1 -> OK | PASS | 29>28 -> OK |
| B08 | Consumo 0: punto=sicurezza, scorta sopra -> OK | PASS | 0x5+8=8, scorta 10 -> OK |
| B09 | Consumo 0 e scorta=sicurezza -> RIORDINARE | PASS | 8<=8 -> RIORDINARE |
| B10 | Giorni 0: punto=sicurezza | PASS | 4x0+8=8 -> RIORDINARE |
| B11 | Sicurezza 0: punto=consumo*giorni | PASS | 4x5+0=20 -> RIORDINARE |
| B12 | Decimale con virgola '4,5' accettato | PASS | consumo 4,5 -> 4.5 valido, punto=30.5 |
| B13 | Decimale con punto '4.5' accettato | PASS | 4.5 valido |
| B14 | Valori grandi 1000x365+500 | PASS | punto=365500 -> OK |
| B15 | Tutti zeri -> 0<=0 RIORDINARE | PASS | 0<=0 -> RIORDINARE |
| C16 | Scorta vuota -> scartata | PASS | scartata: scorta_attuale: campo mancante |
| C17 | Consumo mancante -> scartata | PASS | scartata: consumo_medio_giornaliero: campo mancante |
| C18 | Giorni mancanti -> scartata | PASS | scartata: giorni_consegna: campo mancante |
| C19 | Sicurezza mancante -> scartata | PASS | scartata: scorta_sicurezza: campo mancante |
| C20 | Codice mancante -> scartata | PASS | scartata: codice mancante |
| C21 | Prodotto mancante -> scartata | PASS | scartata: prodotto mancante |
| C22 | Scorta negativa -> scartata | PASS | scartata: scorta_attuale: valore negativo (-5) non ammesso |
| C23 | Consumo negativo -> scartata | PASS | scartata: consumo_medio_giornaliero: valore negativo (-1) non ammesso |
| C24 | Giorni negativi -> scartati | PASS | scartata: giorni_consegna: valore negativo (-2) non ammesso |
| C25 | Consumo 'abc' -> scartata | PASS | scartata: consumo_medio_giornaliero: valore non numerico "abc" |
| C26 | Scorta '12x' -> scartata | PASS | scartata: scorta_attuale: valore non numerico "12x" |
| C27 | Riga con 5 colonne -> scartata, KPI err=1 | PASS | scartata: attese 6 colonne |
| C28 | Riga con 7 colonne -> scartata | PASS | scartata: 7 colonne |
| D29 | Separatore virgola -> errore globale, nessuna decisione | PASS | rifiutato: usare ; |
| D30 | Intestazione errata -> nessuna decisione | PASS | intestazione rifiutata |
| D31 | Intestazione MAIUSCOLA accettata (case-insensitive) | PASS | 4 righe valide |
| D32 | File vuoto -> messaggio, nessun crash | PASS | File vuoto gestito |
| D33 | Solo intestazione -> 0 righe, KPI zero | PASS | 0 righe, KPI 0/0/0/0 |
| D34 | Righe vuote ignorate | PASS | 2 righe valide, vuote ignorate |
| D35 | BOM iniziale gestito | PASS | BOM ok, 4 valide |
| D36 | Spazi ' 12 ' accettati | PASS | trim ok |
| E37 | Simulazione: B200 scorta 60->20 -> RIORDINARE | PASS | B200 20<=30 -> RIORDINARE |
| E38 | Simulazione: B200 giorni 4->12 -> RIORDINARE | PASS | 5x12+10=70 -> RIORDINARE |
| E39 | Simulazione scorta negativa -> DATI NON VALIDI | PASS | sim -3 -> DATI NON VALIDI, nessuna decisione valida |
| E40 | Simulazione giorni vuoti -> DATI NON VALIDI | PASS | giorni '' -> DATI NON VALIDI |
| E41 | Simulazione NaN -> DATI NON VALIDI | PASS | NaN -> DATI NON VALIDI |
| E42 | Ripristino dopo modifica -> torna OK | PASS | ripristino ok, KPI 2/2 |
| E43 | KPI base: 4 validi, 2 ko, 2 ok, 0 err | PASS | {"tot":"4","ko":"2","ok":"2","err":"0"} |
| E44 | KPI con 1 riga scartata: err=1 | PASS | 4 validi + 1 scartata, box errori visibile |

## Note

- Validazione: campi mancanti, negativi e non numerici producono badge DATI NON VALIDI e nessuna decisione valida apparente; la riga è conteggiata in Righe scartate.
- Simulazione (scorta/giorni editabili) con valore negativo, vuoto o NaN produce DATI NON VALIDI.
- Offline: nessun riferimento esterno nel file (verifica findstr: nessun http/src/href/fetch/@import).
