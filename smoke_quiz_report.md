# Smoke test — InfoComm Quiz

Data: 2026-09-29T15:58:42Z · Casi: 12 · PASS: 11 · FAIL: 1

| ID | Caso | Esito | Dettaglio |
|---|---|---|---|
| A01 | File statici presenti | PASS | index, guida, app.js, style.css, quiz.json, .nojekyll, build script ok |
| B02 | quiz.json: 10 moduli, 400 domande | PASS | 10 moduli, 400 domande |
| B03 | quiz.json: schema, opzioni, fonti | PASS | 400 id unici, fonti ok; multiple=286, V/F=114 |
| B04 | Logica punteggio + soglia (specchio di app.js) | PASS | tutto-giusto=40/40 PROMOSSO, tutto-vuoto=0 bocciato |
| B05 | clamp min/n (specchio di app.js) | PASS | clamp ok: stringhe, None, fuori-range |
| C06 | node --check app.js | PASS | JS sintassi valida |
| C07 | index.html: tutti i blocchi presenti | PASS | home: solo quiz studente, area docente assente ok |
| C08 | guida-docente.html: sezioni presenti | PASS | guida: 7 sezioni + ritorno home ok |
| C09 | app.js: solo studente + fix regressione | PASS | app.js: solo studente, fix append ok |
| C09b | docente.js: pagina riservata completa | PASS | docente.js: link classe, registro, CSV ok |
| D10 | Server locale: 7 asset 200 + contenuto | PASS | /index.html 200; /data/quiz.json 200; /guida-docente.html 200; /docente.html 200; /assets/app.js 200; /assets/docente.js 200; /assets/style.css 200 |
| E11 | GitHub Pages live: home, guida, quiz.json | FAIL | HTTP Error 404: Not Found |

## FAIL da correggere

- E11: GitHub Pages live: home, guida, quiz.json: HTTP Error 404: Not Found
