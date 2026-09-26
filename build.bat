@echo off
echo Building Voro with PyInstaller...
call .venv\Scripts\activate.bat
pip install pyinstaller
pyinstaller Voro.spec --clean
echo Build complete! The executable is in the dist/Voro folder.
pause
