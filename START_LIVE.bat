@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title CFD Bot - Capital.com LIVE

echo ============================================================
echo ^|                       BY @BONE                         ^|
echo ============================================================
echo.

set "VENV_PY=.venv\Scripts\python.exe"
set "PY_KIND="
set "PY_EXE="
set "PY_ARGS="

echo [1/6] Checking Python...

rem Prefer an already-working project virtual environment.
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    echo Using existing virtual environment.
    goto :dependencies
  )
  echo Existing .venv is unusable or older than Python 3.11. Rebuilding it...
)

call :detect_python
if not errorlevel 1 goto :python_found

echo.
echo Python 3.11+ was not found.
echo Attempting to install Python 3.12 automatically...
echo.

where winget >nul 2>&1
if errorlevel 1 goto :no_winget

winget install -e --id Python.Python.3.12 --scope user --source winget --accept-package-agreements --accept-source-agreements --silent
if errorlevel 1 (
  echo.
  echo Automatic Python installation failed.
  goto :manual_install
)

echo.
echo Python installation completed. Detecting it...
call :detect_python
if not errorlevel 1 goto :python_found

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PY_KIND=exe"
  set "PY_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
  goto :python_found
)

echo.
echo Python appears to be installed, but this window cannot detect it yet.
echo Close this window, double-click START_LIVE.bat again, and it should continue.
pause
exit /b 0

:no_winget
echo WinGet is not available on this Windows installation.
echo Downloading the official Python 3.12 installer instead...
set "PY_INSTALLER=%TEMP%\cfd_bot_python312.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%PY_INSTALLER%'; Start-Process -FilePath '%PY_INSTALLER%' -ArgumentList '/quiet InstallAllUsers=0 PrependPath=0 Include_pip=1 Include_test=0' -Wait"
if errorlevel 1 (
  echo.
  echo Automatic Python download or installation failed.
  goto :manual_install
)
if exist "%PY_INSTALLER%" del /q "%PY_INSTALLER%" >nul 2>&1
call :detect_python
if not errorlevel 1 goto :python_found
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PY_KIND=exe"
  set "PY_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
  goto :python_found
)
echo Python installation completed, but this window could not detect it.
echo Close this window and double-click START_LIVE.bat again.
pause
exit /b 0

:manual_install
echo.
echo Install Python 3.12, then run START_LIVE.bat again.
echo Official package ID: Python.Python.3.12
echo.
echo You can install it from a new Command Prompt with:
echo   winget install -e --id Python.Python.3.12 --scope user
echo.
echo Or install Python 3.12 manually and enable "Add python.exe to PATH".
goto :fail

:python_found
echo Found Python:
if "%PY_KIND%"=="launcher" (
  %PY_EXE% %PY_ARGS% --version
) else (
  "%PY_EXE%" --version
)

echo [2/6] Preparing virtual environment...
if exist ".venv" rmdir /s /q ".venv"

if "%PY_KIND%"=="launcher" (
  %PY_EXE% %PY_ARGS% -m venv .venv
) else (
  "%PY_EXE%" -m venv .venv
)
if errorlevel 1 (
  echo Could not create .venv.
  goto :fail
)

if not exist "%VENV_PY%" (
  echo Virtual environment was not created correctly.
  goto :fail
)

:dependencies
echo [3/6] Checking dependencies...
"%VENV_PY%" -c "import pandas,yaml,dotenv,optuna" >nul 2>&1
if errorlevel 1 (
  echo Installing dependencies...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :fail
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :fail
)

echo [4/6] Checking configuration...
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example.
)

"%VENV_PY%" scripts\check_login.py
if errorlevel 1 (
  echo.
  echo Fill CAPITAL_EMAIL, CAPITAL_API_KEY, and CAPITAL_API_PASSWORD in .env.
  echo These credentials must work with your Capital.com LIVE environment.
  start "" notepad ".env"
  pause
  "%VENV_PY%" scripts\check_login.py
  if errorlevel 1 goto :fail
)

"%VENV_PY%" -c "import app.auto,app.desk,app.web_app" >nul 2>&1
if errorlevel 1 (
  echo Startup import check failed.
  "%VENV_PY%" -c "import app.auto,app.desk,app.web_app"
  goto :fail
)

echo [5/6] Confirming LIVE trading...
echo.
echo ============================================================
echo                    CAPITAL.COM LIVE
echo ============================================================
echo This launcher sends orders to the LIVE Capital.com endpoint.
echo It uses the current settings in config.yaml.
echo.
"%VENV_PY%" -c "import yaml; r=yaml.safe_load(open('config.yaml', encoding='utf-8')).get('risk',{}); print('Risk per trade:', r.get('risk_per_trade_pct'), 'pct'); print('Portfolio allocation cap:', r.get('max_portfolio_allocation_pct', 100), 'pct'); print('Daily loss limit:', ('ON (' + str(r.get('max_daily_loss_pct')) + ' pct)') if r.get('daily_loss_enabled', True) else 'OFF'); print('Max open positions:', r.get('max_open_positions')); print('Max index positions:', r.get('max_index_positions'))"
echo.
set "CONFIRM="
set /p "CONFIRM=Type LIVE and press Enter to continue: "
if /I not "%CONFIRM%"=="LIVE" (
  echo.
  echo Live start cancelled.
  pause
  exit /b 0
)

echo.
echo [6/6] Starting CFD bot in LIVE mode...
echo Dashboard opens automatically with a one-run control token.
echo Automatic tuning is skipped at startup.
echo.
"%VENV_PY%" -m app.auto --mode live --skip-tune
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo LIVE bot stopped with exit code %EXIT_CODE%.
  goto :fail
)

echo.
echo LIVE bot stopped normally.
pause
exit /b 0

:detect_python
set "PY_KIND="
set "PY_EXE="
set "PY_ARGS="

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PY_KIND=launcher"
  set "PY_EXE=py"
  set "PY_ARGS=-3"
  exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PY_KIND=exe"
  set "PY_EXE=python"
  exit /b 0
)

python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PY_KIND=exe"
  set "PY_EXE=python3"
  exit /b 0
)

for %%V in (314 313 312 311) do (
  if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
    "%LocalAppData%\Programs\Python\Python%%V\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
      set "PY_KIND=exe"
      set "PY_EXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
      exit /b 0
    )
  )
)

for %%V in (314 313 312 311) do (
  if exist "%ProgramFiles%\Python%%V\python.exe" (
    "%ProgramFiles%\Python%%V\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
      set "PY_KIND=exe"
      set "PY_EXE=%ProgramFiles%\Python%%V\python.exe"
      exit /b 0
    )
  )
)

exit /b 1

:fail
echo.
echo Startup failed. Read the error above.
pause
exit /b 1
