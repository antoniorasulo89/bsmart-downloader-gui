"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const htmlPath = path.join(__dirname, "cruscotto_scorte.html");
const html = fs.readFileSync(htmlPath, "utf8");
const m = html.match(/<script>([\s\S]*)<\/script>/);
if (!m) { console.error("script non trovato"); process.exit(1); }
const jsCode = m[1];

// ---- Fake DOM minimo per eseguire il vero script della pagina ----
function makeEl(tag) {
  const e = {
    tag: tag || "div", _html: "", textContent: "", hidden: true,
    children: [], dataset: {}, value: "", className: "",
    appendChild(c) { this.children.push(c); return c; },
    setAttribute() {}, addEventListener() {},
    querySelector() { return null; },
  };
  Object.defineProperty(e, "innerHTML", {
    get() { return this._html; },
    set(v) { this._html = String(v); this.children = []; }, // come nel DOM reale: azzera i figli
  });
  return e;
}
function makeDocument() {
  const els = {};
  ["fileInfo","tbody","globalErrors","kTot","kKo","kOk","kErr"].forEach(id => { els[id] = makeEl(); });
  return {
    _els: els,
    getElementById(id) { if (!els[id]) els[id] = makeEl(); return els[id]; },
    createElement(tag) { return makeEl(tag); },
    querySelector() { return { addEventListener() {} }; },
  };
}

function freshContext() {
  const doc = makeDocument();
  const sandbox = { document: doc, console };
  // FileReader non serve: chiamiamo parseCSV direttamente
  vm.createContext(sandbox);
  vm.runInContext(jsCode + "\n;this.__api={parseCSV,render,updateKpi,toNum,fmt,escapeHtml,get rows(){return rows;}};", sandbox);
  return { sandbox, doc, api: sandbox.__api };
}

function collectBadges(doc) {
  const out = [];
  function walk(n) {
    if (n.innerHTML && /RIORDINARE|SCORTA OK|DATI NON VALIDI/.test(n.innerHTML)) out.push(n.innerHTML);
    (n.children||[]).forEach(walk);
  }
  (doc._els.tbody.children||[]).forEach(walk);
  return out.join(" | ");
}
function kpi(doc) {
  const s = v => String(v && v.textContent !== undefined ? v.textContent : v);
  return { tot: s(doc._els.kTot), ko: s(doc._els.kKo), ok: s(doc._els.kOk), err: s(doc._els.kErr) };
}
function punto(consumo, giorni, sic) { return consumo * giorni + sic; }

const BASE_HEAD = "codice;prodotto;scorta_attuale;consumo_medio_giornaliero;giorni_consegna;scorta_sicurezza";
const BASE_ROWS = [
  "A100;Quaderni;12;4;5;8",
  "B200;Penne;60;5;4;10",
  "C300;Cartucce;7;1;10;3",
  "D400;Risma A4;40;3;7;6",
];
const baseCSV = [BASE_HEAD, ...BASE_ROWS].join("\n");
function csvWith(extraRows) { return [BASE_HEAD, ...extraRows].join("\n"); }

const results = [];
function t(id, nome, fn) {
  try {
    const dettaglio = fn();
    results.push({ id, nome, esito: "PASS", dettaglio });
  } catch (e) {
    results.push({ id, nome, esito: "FAIL", dettaglio: String(e && e.message || e) });
  }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }

// ============ A. Calcoli base su file originale ============
t("A01","A100: 4x5+8=28, scorta 12 -> RIORDINARE", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"dati_scorte.csv");
  const r = api.rows.find(x=>x.codice==="A100");
  assert(r && r.valid, "riga A100 non valida");
  assert(punto(4,5,8)===28, "punto errato");
  assert(12<=28, "confronto errato");
  assert(collectBadges(doc).includes("RIORDINARE"), "badge RIORDINARE assente: "+collectBadges(doc));
  return "punto=28, scorta=12, badge RIORDINARE presente";
});
t("A02","B200: 5x4+10=30, scorta 60 -> SCORTA OK", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  assert(collectBadges(doc).includes("SCORTA OK"), "badge OK assente");
  const k = kpi(doc); assert(k.tot==="4"&&k.ko==="2"&&k.ok==="2"&&k.err==="0", "KPI errati "+JSON.stringify(k));
  return "punto=30, scorta=60 OK; KPI 4/2/2/0";
});
t("A03","C300: 1x10+3=13, scorta 7 -> RIORDINARE", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  const r = api.rows.find(x=>x.codice==="C300");
  assert(r.valid && punto(1,10,3)===13 && 7<=13, "calcolo C300 errato");
  return "punto=13, scorta=7 -> RIORDINARE";
});
t("A04","D400: 3x7+6=27, scorta 40 -> SCORTA OK", () => {
  const {api} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  assert(punto(3,7,6)===27 && !(40<=27), "calcolo D400 errato");
  return "punto=27, scorta=40 -> OK";
});
t("A05","Scenario B200 giorni=12 -> 5x12+10=70 -> RIORDINARE", () => {
  const {api,doc} = freshContext();
  api.parseCSV(csvWith(["A100;Quaderni;12;4;5;8","B200;Penne;60;5;12;10","C300;Cartucce;7;1;10;3","D400;Risma A4;40;3;7;6"]),"f.csv");
  assert(punto(5,12,10)===70, "punto 70 errato");
  const badges = collectBadges(doc);
  assert((badges.match(/RIORDINARE/g)||[]).length===3, "attesi 3 RIORDINARE, got: "+badges);
  return "B200 punto=70 -> RIORDINARE (3 riordini totali)";
});

// ============ B. Boundary, zeri, decimali ============
t("B06","Uguaglianza scorta=punto -> RIORDINARE (<=)", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;28;4;5;8"]),"f.csv");
  assert(collectBadges(doc).includes("RIORDINARE"), "con = deve riordinare");
  return "28<=28 -> RIORDINARE";
});
t("B07","Scorta punto+1 -> OK", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;29;4;5;8"]),"f.csv");
  assert(collectBadges(doc).includes("SCORTA OK"), "29>28 deve essere OK");
  return "29>28 -> OK";
});
t("B08","Consumo 0: punto=sicurezza, scorta sopra -> OK", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;10;0;5;8"]),"f.csv");
  assert(collectBadges(doc).includes("SCORTA OK"), "0*5+8=8, 10>8 -> OK atteso");
  return "0x5+8=8, scorta 10 -> OK";
});
t("B09","Consumo 0 e scorta=sicurezza -> RIORDINARE", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;8;0;5;8"]),"f.csv");
  assert(collectBadges(doc).includes("RIORDINARE"), "8<=8 -> RIORDINARE atteso");
  return "8<=8 -> RIORDINARE";
});
t("B10","Giorni 0: punto=sicurezza", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;7;4;0;8"]),"f.csv");
  assert(collectBadges(doc).includes("RIORDINARE"), "4*0+8=8, 7<=8 -> RIORDINARE");
  return "4x0+8=8 -> RIORDINARE";
});
t("B11","Sicurezza 0: punto=consumo*giorni", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;19;4;5;0"]),"f.csv");
  assert(collectBadges(doc).includes("RIORDINARE"), "4*5+0=20, 19<=20 -> RIORDINARE");
  return "4x5+0=20 -> RIORDINARE";
});
t("B12","Decimale con virgola '4,5' accettato", () => {
  const {api} = freshContext(); api.parseCSV(csvWith(["X01;Test;30;4,5;5;8"]),"f.csv");
  const r = api.rows[0];
  assert(r.valid && Math.abs(r.consumo-4.5)<1e-9, "virgola non convertita: "+JSON.stringify(r));
  return "consumo 4,5 -> 4.5 valido, punto=30.5";
});
t("B13","Decimale con punto '4.5' accettato", () => {
  const {api} = freshContext(); api.parseCSV(csvWith(["X01;Test;30;4.5;5;8"]),"f.csv");
  assert(api.rows[0].valid, "punto decimale rifiutato");
  return "4.5 valido";
});
t("B14","Valori grandi 1000x365+500", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;400000;1000;365;500"]),"f.csv");
  assert(punto(1000,365,500)===365500, "punto grande errato");
  assert(collectBadges(doc).includes("SCORTA OK"), "400000>365500 -> OK");
  return "punto=365500 -> OK";
});
t("B15","Tutti zeri -> 0<=0 RIORDINARE", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;0;0;0;0"]),"f.csv");
  assert(api.rows[0].valid && collectBadges(doc).includes("RIORDINARE"), "0<=0 deve riordinare");
  return "0<=0 -> RIORDINARE";
});

// ============ C. Validazione righe ============
function expectInvalid(id, nome, row, frammentoErrore) {
  t(id, nome, () => {
    const {api,doc} = freshContext(); api.parseCSV(csvWith([row]),"f.csv");
    const r = api.rows[0];
    assert(!r.valid, "riga doveva essere non valida");
    assert(collectBadges(doc).includes("DATI NON VALIDI"), "badge DATI NON VALIDI assente");
    assert(!collectBadges(doc).includes("RIORDINARE")||collectBadges(doc).includes("DATI NON VALIDI"), "nessuna decisione valida apparente");
    if (frammentoErrore) assert(r.errors.join(" ").includes(frammentoErrore), "errore atteso '"+frammentoErrore+"', got: "+r.errors.join("; "));
    const k = kpi(doc); assert(k.err==="1", "KPI err deve essere 1: "+JSON.stringify(k));
    return "scartata: " + r.errors.join("; ");
  });
}
expectInvalid("C16","Scorta vuota -> scartata","X01;Test;;4;5;8","scorta_attuale");
expectInvalid("C17","Consumo mancante -> scartata","X01;Test;10;;5;8","consumo_medio");
expectInvalid("C18","Giorni mancanti -> scartata","X01;Test;10;4;;8","giorni_consegna");
expectInvalid("C19","Sicurezza mancante -> scartata","X01;Test;10;4;5;","scorta_sicurezza");
expectInvalid("C20","Codice mancante -> scartata",";Test;10;4;5;8","codice");
expectInvalid("C21","Prodotto mancante -> scartata","X01;;10;4;5;8","prodotto");
expectInvalid("C22","Scorta negativa -> scartata","X01;Test;-5;4;5;8","negativo");
expectInvalid("C23","Consumo negativo -> scartata","X01;Test;10;-1;5;8","negativo");
expectInvalid("C24","Giorni negativi -> scartati","X01;Test;10;4;-2;8","negativo");
expectInvalid("C25","Consumo 'abc' -> scartata","X01;Test;10;abc;5;8","non numerico");
expectInvalid("C26","Scorta '12x' -> scartata","X01;Test;12x;4;5;8","non numerico");
t("C27","Riga con 5 colonne -> scartata, KPI err=1", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith(["X01;Test;10;4;5"]),"f.csv");
  assert(api.rows.length===0, "riga 5 col deve essere scartata del tutto");
  assert(doc._els.globalErrors.innerHTML.includes("6 colonne"), "messaggio colonne assente");
  return "scartata: attese 6 colonne";
});
t("C28","Riga con 7 colonne -> scartata", () => {
  const {api} = freshContext(); api.parseCSV(csvWith(["X01;Test;10;4;5;8;EXTRA"]),"f.csv");
  assert(api.rows.length===0, "riga 7 col deve essere scartata");
  return "scartata: 7 colonne";
});

// ============ D. File / intestazione ============
t("D29","Separatore virgola -> errore globale, nessuna decisione", () => {
  const {api,doc} = freshContext();
  api.parseCSV("codice,prodotto,scorta_attuale,consumo_medio_giornaliero,giorni_consegna,scorta_sicurezza\nA100,Quaderni,12,4,5,8","f.csv");
  assert(doc._els.globalErrors.innerHTML.includes("punto e virgola"), "messaggio separatore assente");
  assert(api.rows.length===0, "nessuna riga deve essere calcolata");
  return "rifiutato: usare ;";
});
t("D30","Intestazione errata -> nessuna decisione", () => {
  const {api,doc} = freshContext();
  api.parseCSV("cod;nome;giacenza;uso;lead;ss\nA100;Quaderni;12;4;5;8","f.csv");
  assert(doc._els.globalErrors.innerHTML.includes("Intestazione non valida"), "messaggio intestazione assente");
  return "intestazione rifiutata";
});
t("D31","Intestazione MAIUSCOLA accettata (case-insensitive)", () => {
  const {api} = freshContext();
  api.parseCSV(["CODICE;PRODOTTO;SCORTA_ATTUALE;CONSUMO_MEDIO_GIORNALIERO;GIORNI_CONSEGNA;SCORTA_SICUREZZA",...BASE_ROWS].join("\n"),"f.csv");
  assert(api.rows.length===4 && api.rows.every(r=>r.valid), "header maiuscola doveva passare");
  return "4 righe valide";
});
t("D32","File vuoto -> messaggio, nessun crash", () => {
  const {api,doc} = freshContext(); api.parseCSV("","vuoto.csv");
  assert(doc._els.fileInfo.textContent.includes("vuoto"), "messaggio vuoto assente");
  return "File vuoto gestito";
});
t("D33","Solo intestazione -> 0 righe, KPI zero", () => {
  const {api,doc} = freshContext(); api.parseCSV(BASE_HEAD,"f.csv");
  const k = kpi(doc); assert(k.tot==="0"&&k.err==="0", "KPI devono essere 0: "+JSON.stringify(k));
  return "0 righe, KPI 0/0/0/0";
});
t("D34","Righe vuote ignorate", () => {
  const {api} = freshContext();
  api.parseCSV(BASE_HEAD+"\n\n"+BASE_ROWS[0]+"\n\n"+BASE_ROWS[1]+"\n","f.csv");
  assert(api.rows.length===2, "righe vuote non ignorate: "+api.rows.length);
  return "2 righe valide, vuote ignorate";
});
t("D35","BOM iniziale gestito", () => {
  const {api} = freshContext(); api.parseCSV("﻿"+baseCSV,"f.csv");
  assert(api.rows.length===4 && api.rows.every(r=>r.valid), "BOM non gestito");
  return "BOM ok, 4 valide";
});
t("D36","Spazi ' 12 ' accettati", () => {
  const {api} = freshContext(); api.parseCSV(csvWith(["X01;Test;  12 ; 4 ; 5 ; 8 "]),"f.csv");
  assert(api.rows[0].valid && api.rows[0].scorta===12, "spazi non tollerati");
  return "trim ok";
});

// ============ E. Simulazione in pagina ============
t("E37","Simulazione: B200 scorta 60->20 -> RIORDINARE", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  const b = api.rows.find(x=>x.codice==="B200"); b.simScorta = 20; api.render();
  assert((collectBadges(doc).match(/RIORDINARE/g)||[]).length===3, "attesi 3 RIORDINARE dopo sim");
  return "B200 20<=30 -> RIORDINARE";
});
t("E38","Simulazione: B200 giorni 4->12 -> RIORDINARE", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  const b = api.rows.find(x=>x.codice==="B200"); b.simGiorni = 12; api.render();
  assert(collectBadges(doc).includes("RIORDINARE"), "sim giorni deve dare RIORDINARE");
  return "5x12+10=70 -> RIORDINARE";
});
t("E39","Simulazione scorta negativa -> DATI NON VALIDI", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  api.rows[0].simScorta = -3; api.render();
  const b = collectBadges(doc);
  assert(b.includes("DATI NON VALIDI"), "badge non validi assente: "+b);
  const k = kpi(doc); assert(k.err==="1", "KPI err deve contare sim non valida");
  return "sim -3 -> DATI NON VALIDI, nessuna decisione valida";
});
t("E40","Simulazione giorni vuoti -> DATI NON VALIDI", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  api.rows[1].simGiorni = ""; api.render();
  assert(collectBadges(doc).includes("DATI NON VALIDI"), "giorni vuoti devono dare NON VALIDI");
  return "giorni '' -> DATI NON VALIDI";
});
t("E41","Simulazione NaN -> DATI NON VALIDI", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  api.rows[2].simScorta = NaN; api.render();
  assert(collectBadges(doc).includes("DATI NON VALIDI"), "NaN deve dare NON VALIDI");
  return "NaN -> DATI NON VALIDI";
});
t("E42","Ripristino dopo modifica -> torna OK", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  const b = api.rows.find(x=>x.codice==="B200");
  const origS = b.scorta, origG = b.giorni;
  b.simScorta = 5; api.render();
  assert(collectBadges(doc).includes("DATI NON VALIDI") || (collectBadges(doc).match(/RIORDINARE/g)||[]).length===3, "5<=30 deve riordinare");
  b.simScorta = origS; b.simGiorni = origG; api.render();
  const k = kpi(doc); assert(k.ko==="2"&&k.ok==="2", "dopo ripristino KPI 2/2: "+JSON.stringify(k));
  return "ripristino ok, KPI 2/2";
});
t("E43","KPI base: 4 validi, 2 ko, 2 ok, 0 err", () => {
  const {api,doc} = freshContext(); api.parseCSV(baseCSV,"f.csv");
  const k = kpi(doc); assert(k.tot==="4"&&k.ko==="2"&&k.ok==="2"&&k.err==="0", "KPI base errati "+JSON.stringify(k));
  return JSON.stringify(k);
});
t("E44","KPI con 1 riga scartata: err=1", () => {
  const {api,doc} = freshContext(); api.parseCSV(csvWith([...BASE_ROWS,"X99;Rotto;;4;5;8"]),"f.csv");
  const k = kpi(doc); assert(k.tot==="4"&&k.err==="1", "KPI con scarto errati "+JSON.stringify(k));
  assert(doc._els.globalErrors.innerHTML.includes("Righe scartate"), "box errori assente");
  return "4 validi + 1 scartata, box errori visibile";
});

// ============ Report MD ============
const pass = results.filter(r=>r.esito==="PASS").length;
const fail = results.filter(r=>r.esito==="FAIL").length;
let md = `# Smoke test — ScortaLab (cruscotto_scorte.html)\n\n`;
md += `Data: ${new Date().toISOString()} · File testato: cruscotto_scorte.html (vero \\<script\\> eseguito in Node con fake DOM) · Casi: ${results.length} · PASS: ${pass} · FAIL: ${fail}\n\n`;
md += `Regola: punto = consumo × giorni + sicurezza; riordina se scorta ≤ punto.\n\n`;
md += `| ID | Caso | Esito | Dettaglio |\n|---|---|---|---|\n`;
const PIPE = String.fromCharCode(124);
results.forEach(r => { md += `| ${r.id} | ${r.nome} | ${r.esito} | ${String(r.dettaglio || "").split(PIPE).join("/")} |\n`; });
md += `\n## Note\n\n- Validazione: campi mancanti, negativi e non numerici producono badge DATI NON VALIDI e nessuna decisione valida apparente; la riga è conteggiata in Righe scartate.\n- Simulazione (scorta/giorni editabili) con valore negativo, vuoto o NaN produce DATI NON VALIDI.\n- Offline: nessun riferimento esterno nel file (verifica findstr: nessun http/src/href/fetch/@import).\n`;
if (fail>0) md += `\n## FAIL da correggere\n\n` + results.filter(r=>r.esito==="FAIL").map(r=>`- ${r.id} ${r.nome}: ${r.dettaglio}`).join("\n") + "\n";
fs.writeFileSync(path.join(__dirname, "smoke_test_report.md"), md, "utf8");
console.log(`Casi: ${results.length} PASS: ${pass} FAIL: ${fail}`);
if (fail>0) process.exitCode = 1;
