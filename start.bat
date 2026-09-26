@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Checking Python...
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is not installed. Install Python 3.11+ and run this again.
    pause
    exit /b 1
  )
  set "PY=python"
)

%PY% --version
if not exist ".venv\Scripts\python.exe" (
  echo [2/4] Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Failed to create Python virtual environment.
    pause
    exit /b 1
  )
) else (
  echo [2/4] Virtual environment already exists.
)

call ".venv\Scripts\activate.bat"
python -m pip install -r backend\requirements.txt
if errorlevel 1 (
  echo Failed to install backend dependencies.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js/npm is not installed. Install Node.js 20+ and run this again.
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo [3/4] Installing frontend dependencies...
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    echo Frontend dependency installation failed.
    pause
    exit /b 1
  )
  popd
) else (
  echo [3/4] Frontend dependencies already installed.
)

echo [4/4] Starting Reloop services...
start "Reloop Backend" cmd /k call "%~dp0run_backend.bat"
start "Reloop Frontend" cmd /k call "%~dp0run_frontend.bat"

echo.
echo Frontend: http://localhost:5173
 echo Backend:  http://localhost:8000
 echo Swagger:  http://localhost:8000/docs
 echo.
echo Demo organization: org@reloop.demo / demo123
 echo Demo receiver:     receiver@reloop.demo / demo123
 echo Demo recycler:     recycler@reloop.demo / demo123
 echo Demo logistics:    logistics@reloop.demo / demo123
 echo Demo driver:       driver2@reloop.demo / demo123
 echo Internal admin:    admin@reloop.demo / demo123
 echo.
echo Press any key to close this launcher. Services remain open in their own windows.
pause >nul
endlocal
