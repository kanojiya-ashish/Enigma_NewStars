@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install -r backend\requirements.txt
python verify_release.py
python verify_security.py
python -m compileall -q backend\app
node check_frontend_syntax.cjs
node check_frontend_structure.cjs
if errorlevel 1 (
  echo One or more release checks failed.
  pause
  exit /b 1
)
echo All Reloop release checks passed.
pause
endlocal
