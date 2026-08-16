@echo off
setlocal
cd /d %~dp0

set "PYEXE="

where py >nul 2>nul
if not errorlevel 1 (
  for /f "usebackq delims=" %%i in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYEXE=%%i"
)

if not defined PYEXE if exist "%LocalAppData%\Python\pythoncore-3.14-64\python.exe" set "PYEXE=%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYEXE if exist "%LocalAppData%\Programs\Python\Python310\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python310\python.exe"

if not defined PYEXE (
  echo Could not find Python executable.
  echo Install Python from python.org ^(tick Add python.exe to PATH^), then run this again.
  echo Or start manually: py -3 bridge.py
  pause
  exit /b 1
)

echo Using Python: %PYEXE%
"%PYEXE%" -c "import aiohttp,websockets" >nul 2>nul
if errorlevel 1 (
  echo Installing required packages for current user...
  "%PYEXE%" -m pip install --user --upgrade pip
  "%PYEXE%" -m pip install --user -r requirements.txt
)

echo Starting Wikipelago bridge...
"%PYEXE%" bridge.py

endlocal
