@echo off
REM Crea il file .exe in un click (Windows)
pip install -r requirements.txt
pyinstaller --onefile --windowed --name ScaricaLibri --collect-all customtkinter app_gui.py --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module pandas --exclude-module scipy --exclude-module matplotlib --exclude-module sklearn --exclude-module numba --exclude-module llvmlite --exclude-module pyarrow --exclude-module tensorflow --exclude-module transformers --exclude-module cv2 --exclude-module yt_dlp --exclude-module av --exclude-module soundfile --exclude-module onnxruntime --exclude-module lxml --exclude-module sympy --exclude-module tiktoken --exclude-module regex --exclude-module IPython
echo.
echo Fatto! Trovi il file in dist\ScaricaLibri.exe
pause
