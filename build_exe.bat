@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pyinstaller.exe" (
  echo [!] 先准备环境：
  echo     uv venv --python 3.11 .venv
  echo     uv pip install --python .venv\Scripts\python.exe -r requirements.txt pyinstaller
  pause
  exit /b 1
)

rem 单文件 exe（启动慢一点，但只有一个文件）
.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --onefile ^
  --name WeChatVoiceAlert ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --collect-all rapidocr_onnxruntime ^
  --collect-all onnxruntime ^
  --collect-submodules edge_tts ^
  --hidden-import win32com.client ^
  --hidden-import pythoncom ^
  --hidden-import PIL._tkinter_finder ^
  app.py

echo.
echo 产物：dist\WeChatVoiceAlert.exe
pause
