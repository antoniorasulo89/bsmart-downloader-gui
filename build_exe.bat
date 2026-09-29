@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install pip==26.2.1
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip check
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip_audit
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe test_all.py
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe test_security.py
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name Folio --icon assets\folio.ico --version-file assets\folio-version.txt --collect-all customtkinter app_gui.py
if errorlevel 1 exit /b 1
echo Fatto: dist\Folio.exe
