@echo off
:: launch_sim.bat — Windows launcher for DroneLiveStreamDemo
setlocal EnableDelayedExpansion

:: Resolve REPO to the directory containing this script
set "REPO=%~dp0"
:: Strip trailing backslash
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"

:: Load .env from the repo root
set "ENV_FILE=%REPO%\.env"
if not exist "%ENV_FILE%" (
    echo [ERROR] .env not found at %ENV_FILE%
    echo Copy .env.example to .env and fill in your values.
    pause
    exit /b 1
)

:: Parse .env — skip blank lines and comments
for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    set "line=%%A"
    if not "!line:~0,1!"=="#" if not "!line!"=="" (
        set "%%A=%%B"
    )
)

:: Validate required vars
if "%STREAM_HOST%"=="" ( echo [ERROR] STREAM_HOST is not set in .env & pause & exit /b 1 )
if "%MOSQUITTO_BIN%"=="" ( echo [ERROR] MOSQUITTO_BIN is not set in .env & pause & exit /b 1 )
if "%MOSQUITTO_CONF%"=="" ( echo [ERROR] MOSQUITTO_CONF is not set in .env & pause & exit /b 1 )

:: mediamtx is always in the repo's bin folder
set "MEDIAMTX_BIN=%REPO%\bin\mediamtx.exe"

:: Export STREAM_HOST for child processes
set "STREAM_HOST=%STREAM_HOST%"

echo.
echo === Drone Sim Launcher (Windows) ===
echo.
echo REPO:        %REPO%
echo STREAM_HOST: %STREAM_HOST%
echo.

:: mosquitto — opened in a new titled window
echo [mosquitto] Starting MQTT broker...
start "mosquitto" /min cmd /c ^
    ""%MOSQUITTO_BIN%" -c "%MOSQUITTO_CONF%" 2>&1"
timeout /t 3 /nobreak >nul

:: mediamtx — opened in a new titled window
echo [mediamtx] Starting RTSP/HLS server...
start "mediamtx" /min cmd /c ^
    ""%MEDIAMTX_BIN%" "%REPO%\bin\mediamtx.yml" 2>&1"
timeout /t 1 /nobreak >nul

:: dock simulator
echo [dock_sim] Starting dock simulator...
start "dock_sim" /min cmd /c ^
    "cd /d "%REPO%\dock" && python dock_sim.py 2>&1"
timeout /t 1 /nobreak >nul

:: API server
echo [api_sim] Starting API server...
start "api_sim" /min cmd /c ^
    "cd /d "%REPO%\api" && node api_sim.js 2>&1"
timeout /t 1 /nobreak >nul

echo.
echo All services running in background windows.
echo Close those windows (or this one) to stop individual services.
echo Press any key to stop ALL services and exit.
echo.
pause >nul

:: Kill all child processes by window title
taskkill /fi "WindowTitle eq mosquitto" /f >nul 2>&1
taskkill /fi "WindowTitle eq mediamtx"  /f >nul 2>&1
taskkill /fi "WindowTitle eq dock_sim"  /f >nul 2>&1
taskkill /fi "WindowTitle eq api_sim"   /f >nul 2>&1

echo All processes stopped.
endlocal