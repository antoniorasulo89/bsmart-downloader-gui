"""Pacchetti nativi compilati e verificati dal runner GitHub."""
import argparse
import hashlib
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser=argparse.ArgumentParser()
parser.add_argument('target', choices=['Windows','macOS','Linux'])
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--name','Folio','--collect-all','customtkinter',
    *(['--windowed'] if args.target=='macOS' else ['--onefile','--windowed']),
    *(['--icon','assets/folio.ico','--version-file','assets/folio-version.txt'] if args.target=='Windows' else []),
    'app_gui.py'],cwd=root,check=True)
binary=root/'dist'/('Folio.exe' if args.target=='Windows' else 'Folio.app/Contents/MacOS/Folio' if args.target=='macOS' else 'Folio')
smoke=[sys.executable,'test_executable.py',str(binary)]
if args.target=='Linux':smoke=['xvfb-run','-a',*smoke]
subprocess.run(smoke,cwd=root,check=True)
package=root/'packages';package.mkdir(exist_ok=True)
temporary=package/f'Folio-{args.target}'
temporary.mkdir(exist_ok=True)
if args.target=='macOS':shutil.copytree(root/'dist/Folio.app',temporary/'Folio.app',dirs_exist_ok=True)
else:shutil.copy2(binary,temporary/binary.name)
for name in ['README.md','THIRD_PARTY_NOTICES.md','requirements.txt','requirements-build.txt','version.py']:
    shutil.copy2(root/name,temporary/name)
shutil.copytree(root/'THIRD_PARTY_LICENSES',temporary/'THIRD_PARTY_LICENSES',dirs_exist_ok=True)
(temporary/'LEGGIMI.txt').write_text(f'Folio 3.1.0.dev1 — {args.target}\n\nPacchetto nativo compilato su GitHub Actions.\nArchitettura: {platform.machine()}. Sistema runner: {platform.platform()}.\nEstrarre tutto lo ZIP e aprire '+('Folio.app' if args.target=='macOS' else binary.name)+'.\nI test offline e la prova GUI del bundle sono stati eseguiti prima del confezionamento.\nNon contiene account, password o libri scaricati.\nBuild di sviluppo; non firmata né notarizzata.\n',encoding='utf-8')
manifest=[]
for file in sorted(temporary.rglob('*')):
    if file.is_file():manifest.append(hashlib.sha256(file.read_bytes()).hexdigest()+'  '+file.relative_to(temporary).as_posix())
(temporary/'SHA256SUMS.txt').write_text('\n'.join(manifest)+'\n',encoding='utf-8')
archive=package/f'Folio-{args.target}.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for file in sorted(temporary.rglob('*')):
        if file.is_file():z.write(file,file.relative_to(package))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(checksum+'  '+archive.name+'\n',encoding='utf-8')
print('Pacchetto verificato:',archive.name,platform.machine())
