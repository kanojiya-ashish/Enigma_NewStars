@echo off
setlocal
cd /d "%~dp0"
if exist "backend\reloop.db" del /q "backend\reloop.db"
if exist "reloop.db" del /q "reloop.db"
echo Reloop demo data reset.
echo Start the application again with start.bat to seed fresh demo data.
pause
endlocal
