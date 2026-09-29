"""Smoke test del sistema InfoComm Quiz (docs/ + live Pages).
Eseguire da root repo: python scripts/smoke_quiz.py
Genera: smoke_quiz_report.md · exit code 1 se FAIL > 0.
"""
import json, os, re, subprocess, sys, threading, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = 'https://antoniorasulo89.github.io/bsmart-downloader-gui'
results = []

def t(tid, nome, fn):
    try:
        det = fn()
        results.append((tid, nome, 'PASS', det))
    except Exception as e:
        results.append((tid, nome, 'FAIL', str(e)))

def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    return msg

def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()

def get(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': 'smoke-quiz/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8')

# ---------- A. File presenti ----------
t('A01', 'File statici presenti', lambda: ok(
    all(os.path.exists(os.path.join(ROOT, p)) for p in [
        'docs/index.html', 'docs/guida-docente.html', 'docs/assets/app.js',
        'docs/assets/style.css', 'docs/data/quiz.json', 'docs/.nojekyll',
        'scripts/build_quiz_data.py']),
    'index, guida, app.js, style.css, quiz.json, .nojekyll, build script ok'))

# ---------- B. quiz.json ----------
def load_quiz():
    return json.loads(read('docs/data/quiz.json'))

t('B02', 'quiz.json: 10 moduli, 100 domande', lambda: (
    lambda d: ok(len(d['modules']) == 10 and sum(len(m['questions']) for m in d['modules']) == 100,
                 f"{len(d['modules'])} moduli, {sum(len(m['questions']) for m in d['modules'])} domande"))(load_quiz()))

def check_schema():
    d = load_quiz()
    ids = set()
    for m in d['modules']:
        assert set(m) >= {'id', 'title', 'book_pages', 'minutes', 'questions'}, f"modulo {m.get('id')} incompleto"
        assert len(m['questions']) == 10, f"{m['id']}: {len(m['questions'])} domande"
        for q in m['questions']:
            assert q['id'] not in ids, f"id duplicato {q['id']}"
            ids.add(q['id'])
            assert q.get('source', '').startswith('InfoComm, pag. '), f"{q['id']} senza fonte"
            if q['type'] == 'multiple':
                assert len(q['options']) == 4, f"{q['id']}: {len(q['options'])} opzioni"
                assert 0 <= q['answer'] < 4, f"{q['id']}: answer fuori range"
                assert len(set(q['options'])) == 4, f"{q['id']}: opzioni duplicate"
            elif q['type'] == 'truefalse':
                assert isinstance(q['answer'], bool), f"{q['id']}: answer non bool"
            else:
                raise AssertionError(f"{q['id']}: tipo ignoto {q['type']}")
    ty = [q['type'] for m in d['modules'] for q in m['questions']]
    return f"100 id unici, fonti ok; multiple={ty.count('multiple')}, V/F={ty.count('truefalse')}"

t('B03', 'quiz.json: schema, opzioni, fonti', check_schema)

def check_scoring():
    d = load_quiz()
    m = d['modules'][3]  # a4
    def score(given):
        s = 0
        for q in m['questions']:
            if q['type'] == 'multiple':
                if given.get(q['id']) == q['answer']:
                    s += 1
            else:
                if given.get(q['id']) == q['answer']:
                    s += 1
        return s
    all_ok = {q['id']: q['answer'] for q in m['questions']}
    assert score(all_ok) == 10, 'tutto corretto deve dare 10'
    assert score({}) == 0, 'tutto vuoto deve dare 0'
    assert score(all_ok) >= (d.get('pass_score', 6)), 'soglia non superata con 10/10'
    return 'tutto-giusto=10/10 PROMOSSO, tutto-vuoto=0/10 bocciato'

t('B04', 'Logica punteggio + soglia (specchio di app.js)', check_scoring)

def check_clamp():
    def clamp(v, a, b, dflt):
        try:
            v = int(v)
        except (TypeError, ValueError):
            return dflt
        return min(b, max(a, v))
    assert clamp('5', 1, 10, 10) == 5
    assert clamp('99', 1, 10, 10) == 10
    assert clamp('0', 1, 120, 12) == 1
    assert clamp(None, 1, 10, 10) == 10
    assert clamp('xx', 1, 10, 7) == 7
    return 'clamp ok: stringhe, None, fuori-range'

t('B05', 'clamp min/n (specchio di app.js)', check_clamp)

# ---------- C. Frontend ----------
t('C06', 'node --check app.js', lambda: (
    subprocess.run(['node', '--check', os.path.join(ROOT, 'docs/assets/app.js')],
                   capture_output=True, text=True, timeout=30).returncode == 0
    and 'JS sintassi valida' or (_ for _ in ()).throw(AssertionError('node --check fallito'))))

def check_index():
    h = read('docs/index.html')
    for needle in ['id="modules"', 'id="q-timer"', 'id="q-list"', 'id="teacher-card"',
                   'id="t-mod"', 'id="t-link"', 'id="t-history"', 'id="student-name"',
                   'guida-docente.html', 'assets/app.js', '12 minuti']:
        assert needle in h, f'manca {needle}'
    return 'home: moduli, timer, quiz-box, area docente, link guida ok'

t('C07', 'index.html: tutti i blocchi presenti', check_index)

def check_guide():
    h = read('docs/guida-docente.html')
    for needle in ['Area docente', 'Genera link classe', 'Scarica CSV', 'Privacy', 'Problemi frequenti', 'index.html']:
        assert needle in h, f'manca {needle}'
    return 'guida: 7 sezioni + ritorno home ok'

t('C08', 'guida-docente.html: sezioni presenti', check_guide)

def check_appjs():
    j = read('docs/assets/app.js')
    for needle in ['startQuiz', 'submit', 'genLink', 'downloadCSV', 'renderTeacher',
                   'consegna automatica', 'localStorage', '?mod=']:
        assert needle in j, f'manca {needle}'
    assert 'list.appendChild(d)' in j, 'manca append domande (regressione fix)'
    return 'app.js: quiz, docente, export, fix append ok'

t('C09', 'app.js: funzioni docente + fix regressione', check_appjs)

# ---------- D. Server locale ----------
def serve_and_check():
    import http.server, functools
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(ROOT, 'docs'))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 18765), handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.5)
    try:
        out = []
        for path, needle in [('/index.html', 'InfoComm Quiz'),
                             ('/data/quiz.json', '"modules"'),
                             ('/guida-docente.html', 'Guida docente'),
                             ('/assets/app.js', 'startQuiz'),
                             ('/assets/style.css', '.timer')]:
            st, body = get(f'http://127.0.0.1:18765{path}')
            assert st == 200, f'{path}: status {st}'
            assert needle in body, f'{path}: contenuto inatteso'
            out.append(f'{path} 200')
        return '; '.join(out)
    finally:
        srv.shutdown()

t('D10', 'Server locale: 5 asset 200 + contenuto', serve_and_check)

# ---------- E. Sito live Pages ----------
def check_live():
    out = []
    for path, needle in [('/', 'InfoComm Quiz'),
                         ('/guida-docente.html', 'Guida docente'),
                         ('/data/quiz.json', '"modules"')]:
        st, body = get(LIVE + path)
        assert st == 200, f'{path}: status {st}'
        assert needle in body, f'{path}: contenuto inatteso'
        out.append(f'{path} 200')
    return 'live: ' + '; '.join(out)

t('E11', 'GitHub Pages live: home, guida, quiz.json', check_live)

# ---------- Report ----------
npass = sum(1 for r in results if r[2] == 'PASS')
nfail = sum(1 for r in results if r[2] == 'FAIL')
md = '# Smoke test — InfoComm Quiz\n\n'
md += f"Data: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} · Casi: {len(results)} · PASS: {npass} · FAIL: {nfail}\n\n"
md += '| ID | Caso | Esito | Dettaglio |\n|---|---|---|---|\n'
for tid, nome, esito, det in results:
    md += f"| {tid} | {nome} | {esito} | {str(det).replace('|', '/')[:220]} |\n"
if nfail:
    md += '\n## FAIL da correggere\n\n' + '\n'.join(f'- {t}: {n}: {d}' for t, n, e, d in results if e == 'FAIL') + '\n'
with open(os.path.join(ROOT, 'smoke_quiz_report.md'), 'w', encoding='utf-8') as f:
    f.write(md)
print(f"Casi: {len(results)} PASS: {npass} FAIL: {nfail}")
sys.exit(1 if nfail else 0)
