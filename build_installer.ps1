# build_installer.ps1
Write-Host "Building Voro Executable..." -ForegroundColor Green

# 1. Clean previous builds
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# 2. Run PyInstaller (Single line to prevent PowerShell parsing errors)
& e:\Noise\.venv\Scripts\pyinstaller.exe --noconfirm --onedir --windowed --icon "logo.ico" --name "Voro" --add-data "logo.ico;." --add-data "logo.png;." --hidden-import "PySide6.QtMultimedia" --hidden-import "pydantic" --hidden-import "mss" --hidden-import "httpx" --hidden-import "easyocr" --hidden-import "torch" --hidden-import "keyboard" --hidden-import "edge_tts" --hidden-import "dotenv" --hidden-import "pydantic_settings" "main.py"

Write-Host "PyInstaller Build Complete!" -ForegroundColor Green
Write-Host "NOTE: To create the final setup.exe, install Inno Setup and run voro.iss" -ForegroundColor Yellow
