/* InfoComm Quiz — app statica, nessun backend. Timer 12' stile INVALSI. */
const LS_KEY = 'infocomm-quiz-v1';
let DATA = null, cur = null, deadline = null, tickId = null;

const $ = id => document.getElementById(id);
const load = () => { try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch { return {}; } };
const save = s => localStorage.setItem(LS_KEY, JSON.stringify(s));

function fmt(ms) {
  ms = Math.max(0, ms);
  const s = Math.ceil(ms / 1000), m = String(Math.floor(s / 60)).padStart(2, '0'), r = String(s % 60).padStart(2, '0');
  return `${m}:${r}`;
}

async function init() {
  const res = await fetch('data/quiz.json');
  DATA = await res.json();
  renderModules();
  $('btn-submit').onclick = () => submit(false);
  $('btn-abort').onclick = abort;
  $('btn-reset').onclick = () => { if (confirm('Cancellare tutti i progressi salvati?')) { localStorage.removeItem(LS_KEY); renderModules(); } };
}

function renderModules() {
  const scores = load();
  const box = $('modules'); box.innerHTML = '';
  DATA.modules.forEach(m => {
    const b = document.createElement('button');
    b.className = 'mod' + (cur && cur.id === m.id ? ' active' : '');
    const sc = scores[m.id];
    const pill = sc ? `<span class="pill ${sc.pass ? 'done-ok' : 'done-ko'}">${sc.score}/${m.questions.length}</span>` : `<span class="pill">${m.questions.length} dom · ${m.minutes}'</span>`;
    b.innerHTML = `<span><strong>${m.title}</strong><br><small>pagg. ${m.book_pages[0]}–${m.book_pages[1]} · ${m.questions.length} domande · ${m.minutes} min</small></span>${pill}`;
    b.onclick = () => startQuiz(m.id);
    box.appendChild(b);
  });
}

function startQuiz(id) {
  const m = DATA.modules.find(x => x.id === id);
  cur = JSON.parse(JSON.stringify(m)); // copia per mescolare senza toccare DATA
  // mescola opzioni delle multiple (e ricalcola answer)
  cur.questions.forEach(q => {
    if (q.type === 'multiple') {
      const order = q.options.map((_, i) => i).sort(() => Math.random() - .5);
      q.options = order.map(i => q.options[i]);
      q.answer = order.indexOf(q.answer);
    }
  });
  deadline = Date.now() + cur.minutes * 60 * 1000;
  $('quiz-home').hidden = true; $('quiz-box').hidden = false;
  $('q-title').textContent = cur.title;
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
        inp.type = 'radio'; inp.name = q.id; inp.value = oi;
        inp.onchange = updateBar;
        lab.appendChild(inp); lab.appendChild(document.createTextNode(opt));
        d.appendChild(lab);
      });
    } else {
      [['Vero', '1'], ['Falso', '0']].forEach(([txt, v]) => {
        const lab = document.createElement('label');
        const inp = document.createElement('input');
        inp.type = 'radio'; inp.name = q.id; inp.value = v;
        inp.onchange = updateBar;
        lab.appendChild(inp); lab.appendChild(document.createTextNode(txt));
        d.appendChild(lab);
      });
    }
    list.appendChild(d);
  });
  updateBar();
}

function answers() {
  const out = {};
  cur.questions.forEach(q => {
    const sel = document.querySelector(`input[name="${q.id}"]:checked`);
    out[q.id] = sel ? sel.value : null;
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
  let score = 0;
  const rows = cur.questions.map((q, i) => {
    let ok = false, given = '—', exp = '';
    if (q.type === 'multiple') {
      given = a[q.id] === null ? '—' : q.options[+a[q.id]];
      exp = q.options[q.answer];
      ok = a[q.id] !== null && +a[q.id] === q.answer;
    } else {
      given = a[q.id] === null ? '—' : (a[q.id] === '1' ? 'Vero' : 'Falso');
      exp = q.answer ? 'Vero' : 'Falso';
      ok = a[q.id] !== null && ((a[q.id] === '1') === q.answer);
    }
    if (ok) score++;
    return `<div class="q"><h3>${i + 1}. ${q.q} — ${ok ? '✅' : '❌'}</h3><div class="sol">Tua risposta: <b>${given}</b> · Corretta: <b>${exp}</b></div><div class="src">Fonte: ${q.source}</div></div>`;
  });
  const pass = score >= (DATA.pass_score || 6);
  const scores = load();
  const prev = scores[cur.id];
  if (!prev || score > prev.score) scores[cur.id] = { score, pass, when: new Date().toISOString() };
  save(scores);
  $('q-result').innerHTML = `<div class="res ${pass ? 'ok' : 'ko'}"><strong>${auto ? 'Tempo scaduto — consegna automatica. ' : ''}Punteggio: ${score}/${cur.questions.length} ${pass ? '· PROMOSSO 🎉' : '· non sufficiente (soglia 6)'}.</strong><br><span class="small">Soluzioni con pagina del libro qui sotto. Puoi ripetere il quiz per migliorare.</span></div>` + rows.join('');
  $('q-list').innerHTML = '';
  $('q-prog').textContent = 'Quiz consegnato.';
  $('q-timer').textContent = '00:00';
  renderModules();
}

function abort() {
  if (!cur) return;
  if (!confirm('Annullare il quiz in corso?')) return;
  clearInterval(tickId); cur = null;
  $('quiz-box').hidden = true; $('quiz-home').hidden = false;
  renderModules();
}

init();
