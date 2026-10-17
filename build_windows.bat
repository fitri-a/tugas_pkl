@echo off
setlocal
python -m PyInstaller --noconfirm --clean --windowed --name ProgressPLSCS main.py
if errorlevel 1 exit /b 1
echo Build selesai: dist\ProgressPLSCS\ProgressPLSCS.exe
