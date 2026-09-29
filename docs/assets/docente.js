/* Area docente — pagina riservata. Genera link classe + registro consegne. */
const H_KEY = 'infocomm-history-v1';
const $ = id => document.getElementById(id);
const loadH = () => { try { return JSON.parse(localStorage.getItem(H_KEY) || '[]'); } catch { return []; } };
const saveH = h => localStorage.setItem(H_KEY, JSON.stringify(h));
const clamp = (v, a, b, d) => { v = parseInt(v, 10); return Number.isFinite(v) ? Math.min(b, Math.max(a, v)) : d; };
let DATA = null;

async function init() {
  try {
    const res = await fetch('data/quiz.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    DATA = await res.json();
  } catch (e) {
    $('t-hint').textContent = '⚠ Dati non caricati. Controlla la connessione e ricarica (Ctrl+F5).';
    $('t-history').textContent = 'Dati non caricati.';
    return;
  }
  const sel = $('t-mod');
  DATA.modules.forEach(m => { const o = document.createElement('option'); o.value = m.id; o.textContent = `${m.title} (banca: ${m.questions.length})`; sel.appendChild(o); });
  const syncMax = () => {
    const m = DATA.modules.find(x => x.id === sel.value);
    $('t-n').max = m.questions.length;
    $('t-n').value = clamp($('t-n').value, 1, m.questions.length, Math.min(10, m.questions.length));
    $('t-hint').textContent = `${m.title}: banca dati di ${m.questions.length} domande — il quiz ne pescherà a caso quante ne imposti.`;
  };
  sel.onchange = syncMax;
  syncMax();
  $('t-link').onclick = genLink;
  $('t-csv').onclick = downloadCSV;
  $('t-clear').onclick = () => { if (confirm('Cancellare tutte le consegne registrate?')) { saveH([]); renderHistory(); } };
  renderHistory();
}

function genLink() {
  const m = DATA.modules.find(x => x.id === $('t-mod').value);
  const min = clamp($('t-min').value, 1, 120, 12);
  const n = clamp($('t-n').value, 1, m.questions.length, m.questions.length);
  const url = `${location.origin}${location.pathname.replace(/docente\.html$/, 'index.html')}?mod=${m.id}&min=${min}&n=${n}`;
  const out = $('t-out');
  out.value = url;
  out.select();
  try { navigator.clipboard.writeText(url); $('t-link').textContent = 'Link copiato ✓'; setTimeout(() => $('t-link').textContent = 'Genera link classe', 2000); } catch {}
}

function renderHistory() {
  const h = loadH();
  const box = $('t-history');
  if (!h.length) { box.innerHTML = 'Nessuna consegna ancora.'; return; }
  box.innerHTML = `<table><tr><th>Data</th><th>Quiz</th><th>Alunno</th><th>Punti</th><th>Tempo</th><th>Esito</th></tr>${h.slice(0, 100).map(r =>
    `<tr><td>${r.when}</td><td>${r.module}</td><td>${(r.name || '—').replace(/</g, '&lt;')}</td><td>${r.score}/${r.total}</td><td>${r.min}'</td><td>${r.pass ? '✅' : '❌'}</td></tr>`).join('')}</table>`;
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
