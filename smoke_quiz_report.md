# Smoke test — InfoComm Quiz

Data: 2026-09-29T15:45:03Z · Casi: 11 · PASS: 11 · FAIL: 0

| ID | Caso | Esito | Dettaglio |
|---|---|---|---|
| A01 | File statici presenti | PASS | index, guida, app.js, style.css, quiz.json, .nojekyll, build script ok |
| B02 | quiz.json: 10 moduli, 100 domande | PASS | 10 moduli, 100 domande |
| B03 | quiz.json: schema, opzioni, fonti | PASS | 100 id unici, fonti ok; multiple=70, V/F=30 |
| B04 | Logica punteggio + soglia (specchio di app.js) | PASS | tutto-giusto=10/10 PROMOSSO, tutto-vuoto=0/10 bocciato |
| B05 | clamp min/n (specchio di app.js) | PASS | clamp ok: stringhe, None, fuori-range |
| C06 | node --check app.js | PASS | JS sintassi valida |
| C07 | index.html: tutti i blocchi presenti | PASS | home: moduli, timer, quiz-box, area docente, link guida ok |
| C08 | guida-docente.html: sezioni presenti | PASS | guida: 7 sezioni + ritorno home ok |
| C09 | app.js: funzioni docente + fix regressione | PASS | app.js: quiz, docente, export, fix append ok |
| D10 | Server locale: 5 asset 200 + contenuto | PASS | /index.html 200; /data/quiz.json 200; /guida-docente.html 200; /assets/app.js 200; /assets/style.css 200 |
| E11 | GitHub Pages live: home, guida, quiz.json | PASS | live: / 200; /guida-docente.html 200; /data/quiz.json 200 |
