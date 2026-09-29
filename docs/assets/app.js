/* InfoComm Quiz — app statica, nessun backend. Timer + n.domande configurabili, export risultati. */
const LS_KEY = 'infocomm-quiz-v1';
const H_KEY = 'infocomm-history-v1';
let DATA = null, cur = null, deadline = null, tickId = null;

const $ = id => document.getElementById(id);
const load = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch { return {}; } };
const save = s => localStorage.setItem(LS_KEY, JSON.stringify(s));
const loadH = () => { try { return JSON.parse(localStorage.getItem(H_KEY) || '[]'); } catch { return []; } };
const saveH = h => localStorage.setItem(H_KEY, JSON.stringify(h));
const params = new URLSearchParams(location.search);
const clamp = (v, a, b, d) => { v = parseInt(v, 10); return Number.isFinite(v) ? Math.min(b, Math.max(a, v)) : d; };

function fmt(ms) {
  ms = Math.max(0, ms);
  const s = Math.ceil(ms / 1000), m = String(Math.floor(s / 60)).padStart(2, '0'), r = String(s % 60).padStart(2, '0');
  return `${m}:${r}`;
}

async function init() {
  const res = await fetch('data/quiz.json');
  DATA = await res.json();
  renderModules();
  renderTeacher();
  $('btn-submit').onclick = () => submit(false);
  $('btn-abort').onclick = abort;
  $('btn-reset').onclick = () => { if (confirm('Cancellare tutti i progressi salvati?')) { localStorage.removeItem(LS_KEY); renderModules(); } };
  $('t-link').onclick = genLink;
  $('t-csv').onclick = downloadCSV;
  $('t-clear').onclick = () => { if (confirm('Cancellare tutte le consegne registrate?')) { saveH([]); renderTeacher(); } };
  // Link classe ?mod=a4&min=20&n=8 → avvio diretto con quelle impostazioni
  const pm = params.get('mod');
  if (pm && DATA.modules.some(m => m.id === pm)) {
    startQuiz(pm, { min: params.get('min'), n: params.get('n'), fromLink: true });
  }
}

function renderModules() {
  const scores = load();
  const box = $('modules'); box.innerHTML = '';
  DATA.modules.forEach(m => {
    const b = document.createElement('button');
    b.className = 'mod' + (cur && cur.id === m.id ? ' active' : '');
    const sc = scores[m.id];
    const pill = sc ? `<span class="pill ${sc.pass ? 'done-ok' : 'done-ko'}">${sc.score}/${sc.total}</span>` : `<span class="pill">${m.questions.length} dom · ${m.minutes}'</span>`;
    b.innerHTML = `<span><strong>${m.title}</strong><br><small>pagg. ${m.book_pages[0]}–${m.book_pages[1]} · max ${m.questions.length} domande</small></span>${pill}`;
    b.onclick = () => startQuiz(m.id, {});
    box.appendChild(b);
  });
}

function shuffled(a) { const x = a.slice(); for (let i = x.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[x[i], x[j]] = [x[j], x[i]]; } return x; }

function startQuiz(id, opts) {
  const m = DATA.modules.find(x => x.id === id);
  const total = m.questions.length;
  const n = clamp(opts.n ?? params.get('n') ?? total, 1, total, total);
  const min = clamp(opts.min ?? params.get('min') ?? m.minutes, 1, 120, m.minutes);
  cur = { id: m.id, title: m.title, minutes: min, count: n, pass: DATA.pass_score || 6,
          questions: shuffled(m.questions).slice(0, n).map(q => JSON.parse(JSON.stringify(q))) };
  cur.questions.forEach(q => {
    if (q.type === 'multiple') {
      const order = shuffled(q.options.map((_, i) => i));
      q.options = order.map(i => q.options[i]);
      q.answer = order.indexOf(q.answer);
    }
  });
  deadline = Date.now() + min * 60 * 1000;
  $('quiz-home').hidden = true; $('quiz-box').hidden = false;
  $('q-title').textContent = `${cur.title} — ${n} domande in ${min} min${opts.fromLink ? ' (link classe)' : ''}`;
  $('q-result').innerHTML = '';
  $('btn-submit').disabled = false;
  renderQuestions();
  renderModules();
  clearInterval(tickId);
  tickId = setInterval(tick, 250);
  tick();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderQuestions() {
  const list = $('q-list'); list.innerHTML = '';
  cur.questions.forEach((q, i) => {
    const d = document.createElement('div');
    d.className = 'q';
    const h = document.createElement('h3');
    h.textContent = `${i + 1}. ${q.q}`;
    d.appendChild(h);
    if (q.type === 'multiple') {
      q.options.forEach((opt, oi) => {
        const lab = document.createElement('label');
        const inp = document.createElement('input');
        inp.type = 'radio'; inp.name = q.id + '_' + i; inp.value = oi;
        inp.onchange = updateBar;
        lab.appendChild(inp); lab.appendChild(document.createTextNode(opt));
        d.appendChild(lab);
      });
    } else {
      [['Vero', '1'], ['Falso', '0']].forEach(([txt, v]) => {
        const lab = document.createElement('label');
        const inp = document.createElement('input');
        inp.type = 'radio'; inp.name = q.id + '_' + i; inp.value = v;
        inp.onchange = updateBar;
        lab.appendChild(inp); lab.appendChild(document.createTextNode(txt));
        d.appendChild(lab);
      });
    }
    q._field = q.id + '_' + i;
    list.appendChild(d);
  });
  updateBar();
}

function answers() {
  const out = {};
  cur.questions.forEach(q => {
    const sel = document.querySelector(`input[name="${q._field}"]:checked`);
    out[q._field] = sel ? sel.value : null;
  });
  return out;
}

function updateBar() {
  if (!cur) return;
  const a = answers();
  const n = Object.values(a).filter(v => v !== null).length;
  $('q-bar').style.width = (n / cur.questions.length * 100) + '%';
  $('q-prog').textContent = `Risposte ${n}/${cur.questions.length} · consegna automatica allo scadere`;
}

function tick() {
  const left = deadline - Date.now();
  const el = $('q-timer');
  el.textContent = fmt(left);
  el.classList.toggle('warn', left < 120000);
  if (left <= 0) submit(true);
}

function submit(auto) {
  if (!cur) return;
  clearInterval(tickId);
  $('btn-submit').disabled = true;
  const a = answers();
  const name = ($('student-name').value || '').trim();
  let score = 0;
  const rows = cur.questions.map((q, i) => {
    let ok = false, given = '—', exp = '';
    if (q.type === 'multiple') {
      given = a[q._field] === null ? '—' : q.options[+a[q._field]];
      exp = q.options[q.answer];
      ok = a[q._field] !== null && +a[q._field] === q.answer;
    } else {
      given = a[q._field] === null ? '—' : (a[q._field] === '1' ? 'Vero' : 'Falso');
      exp = q.answer ? 'Vero' : 'Falso';
      ok = a[q._field] !== null && ((a[q._field] === '1') === q.answer);
    }
    if (ok) score++;
    return `<div class="q"><h3>${i + 1}. ${q.q} — ${ok ? '✅' : '❌'}</h3><div class="sol">Tua risposta: <b>${given}</b> · Corretta: <b>${exp}</b></div><div class="src">Fonte: ${q.source}</div></div>`;
  });
  const pass = score >= cur.pass;
  const scores = load();
  const prev = scores[cur.id];
  if (!prev || score > prev.score) scores[cur.id] = { score, total: cur.questions.length, pass, when: new Date().toISOString() };
  save(scores);
  // consegna per il docente
  const when = new Date().toLocaleString('it-IT');
  const line = `InfoComm Quiz | ${cur.title} | ${name ? 'Alunno: ' + name + ' | ' : ''}Punteggio: ${score}/${cur.questions.length} (${pass ? 'PROMOSSO' : 'non sufficiente'}) | ${cur.minutes} min, ${cur.questions.length} dom. | ${when}${auto ? ' | consegna automatica' : ''}`;
  const h = loadH();
  h.unshift({ when, module: cur.title, name, score, total: cur.questions.length, min: cur.minutes, pass });
  saveH(h.slice(0, 500));
  const rid = 'exp' + Date.now();
  $('q-result').innerHTML = `<div class="res ${pass ? 'ok' : 'ko'}"><strong>${auto ? 'Tempo scaduto — consegna automatica. ' : ''}Punteggio: ${score}/${cur.questions.length} ${pass ? '· PROMOSSO 🎉' : `· non sufficiente (soglia ${cur.pass})`}.</strong></div>`
    + `<div class="expbox"><strong>📋 Consegna al docente:</strong> copia il testo e invialo (WhatsApp / email / registro).<code id="${rid}">${line.replace(/</g, '&lt;')}</code><div class="row"><button id="${rid}-copy" class="primary">Copia risultato</button></div></div>`
    + rows.join('');
  $(rid + '-copy').onclick = async () => {
    try { await navigator.clipboard.writeText(line); $(rid + '-copy').textContent = 'Copiato ✓'; }
    catch { const r = document.createRange(); r.selectNode($(rid)); getSelection().removeAllRanges(); getSelection().addRange(r); document.execCommand('copy'); }
  };
  $('q-list').innerHTML = '';
  $('q-prog').textContent = 'Quiz consegnato.';
  $('q-timer').textContent = '00:00';
  renderModules();
  renderTeacher();
}

function abort() {
  if (!cur) return;
  if (!confirm('Annullare il quiz in corso?')) return;
  clearInterval(tickId); cur = null;
  $('quiz-box').hidden = true; $('quiz-home').hidden = false;
  renderModules();
}

/* ---- Area docente ---- */
function renderTeacher() {
  const sel = $('t-mod');
  if (!sel.options.length) DATA.modules.forEach(m => { const o = document.createElement('option'); o.value = m.id; o.textContent = m.title; sel.appendChild(o); });
  const h = loadH();
  const box = $('t-history');
  if (!h.length) { box.innerHTML = 'Nessuna consegna ancora.'; return; }
  box.innerHTML = `<table><tr><th>Data</th><th>Quiz</th><th>Alunno</th><th>Punti</th><th>Tempo</th><th>Esito</th></tr>${h.slice(0, 50).map(r =>
    `<tr><td>${r.when}</td><td>${r.module}</td><td>${(r.name || '—').replace(/</g, '&lt;')}</td><td>${r.score}/${r.total}</td><td>${r.min}'</td><td>${r.pass ? '✅' : '❌'}</td></tr>`).join('')}</table>`
    + (h.length > 50 ? `<div class="small">…e altre ${h.length - 50} (vedi CSV).</div>` : '');
}

function genLink() {
  const m = DATA.modules.find(x => x.id === $('t-mod').value);
  const min = clamp($('t-min').value, 1, 120, 12);
  const n = clamp($('t-n').value, 1, m.questions.length, m.questions.length);
  const url = `${location.origin}${location.pathname}?mod=${m.id}&min=${min}&n=${n}`;
  const out = $('t-out');
  out.value = url;
  out.select();
  try { navigator.clipboard.writeText(url); } catch {}
}

function downloadCSV() {
  const h = loadH();
  if (!h.length) { alert('Nessuna consegna da esportare.'); return; }
  const q = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = 'data;quiz;alunno;punteggio;totale;minuti;esito\n' + h.map(r => [r.when, q(r.module), q(r.name), r.score, r.total, r.min, r.pass ? 'promosso' : 'non sufficiente'].join(';')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' }));
  a.download = 'infocomm-consegne.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

init();
