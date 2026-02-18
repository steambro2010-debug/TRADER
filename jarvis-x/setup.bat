@echo off
setlocal

if not exist .venv (
    py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo JARVIS-X setup complete.
echo Next steps:
echo 1) Install and start Ollama (default endpoint http://127.0.0.1:11434)
echo 2) Pull a small model, e.g.: ollama pull tinyllama
echo 3) Download a Vosk model into models\
echo 4) Run: python main.py

endlocal
