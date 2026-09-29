@echo off
REM Crea il file .exe in un click (Windows)
pip install -r requirements.txt
pyinstaller --onefile --windowed --name bSmartDownloaderGUI bsmart_gui.py
echo.
echo Fatto! Trovi il file in dist\bSmartDownloaderGUI.exe
pause
