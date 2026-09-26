@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install -r backend\requirements.txt
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
endlocal
