"""Avvio reale del bundle in un profilo isolato, senza account personali."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as folder:
    env = dict(os.environ, FOLIO_SMOKE_HOME=folder, APPDATA=folder, XDG_CONFIG_HOME=folder)
    process = subprocess.run([str(Path(sys.argv[1]).resolve()), '--smoke-test'], env=env, capture_output=True, timeout=45)
    result = Path(folder, 'success.json')
    assert process.returncode == 0 and result.is_file(), 'Il bundle non ha completato la prova GUI.'
    data = json.loads(result.read_text())
    assert data['platforms'] == 6 and data['gui']
    print('Bundle GUI OK:', data['version'])
