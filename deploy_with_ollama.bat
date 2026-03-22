@echo off
cd /d %~dp0

REM ===== 0. Ollama installation and configuration =====
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [Ollama] Ollama not found, installing...
    winget install Ollama.Ollama -e
    if %errorlevel% neq 0 (
        echo [Ollama] Install failed. Please install manually: https://ollama.com/download
        pause
        exit /b 1
    )
)

REM Check if Ollama is already running
powershell -Command "try {Invoke-WebRequest -Uri http://localhost:11434 -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0} catch {exit 1}"
if errorlevel 1 (
    echo [Ollama] Starting Ollama server...
    set OLLAMA_NUM_PARALLEL=4
    set OLLAMA_CONTEXT_LENGTH=8192
    start "ollama" cmd /k "ollama serve"
    timeout /t 3 >nul
) else (
    echo [Ollama] Already running.
)

REM ===== 1. Pull model if not exists =====
set OLLAMA_MODEL=llama3.1

ollama list | findstr %OLLAMA_MODEL% >nul
if %errorlevel% neq 0 (
    echo [Ollama] Pulling model %OLLAMA_MODEL% ...
    ollama pull %OLLAMA_MODEL%
)

REM Set Ollama API URL environment variable
set OLLAMA_API_URL=http://localhost:11434

REM Update backend/.env file with Ollama API URL
set ENV_FILE=backend\.env
if not exist %ENV_FILE% (
    echo OLLAMA_API_URL=%OLLAMA_API_URL% > %ENV_FILE%
) else (
    powershell -Command "(Get-Content %ENV_FILE% | Where-Object {$_ -notmatch '^OLLAMA_API_URL='}) + 'OLLAMA_API_URL=%OLLAMA_API_URL%' | Set-Content %ENV_FILE%"
)

REM ===== 2. Virtual environment =====
if not exist venv (
    echo [Setup] Creating virtual environment...
    python -m venv venv || exit /b 1
)

echo [Setup] Activating virtual environment...
call venv\Scripts\activate || exit /b 1

REM ===== 3. Backend =====
cd backend || exit /b 1

echo [Backend] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || exit /b 1

echo [Backend] Starting server...
start "backend" cmd /k "call ..\venv\Scripts\activate && python -m uvicorn main:app --reload > backend.log 2>&1"

cd ..

REM ===== 4. Frontend =====
cd frontend || exit /b 1

echo [Frontend] Creating .env...
if not exist .env (
    echo VITE_VTT_API_BASE_URL=http://localhost:8000> .env
)

echo [Frontend] Installing dependencies...
call npm install || exit /b 1

echo [Frontend] Starting dev server...
start "frontend" cmd /k "npm run dev"

cd ..

echo.
echo Deployment complete!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173

REM ===== 5. Wait backend =====
:wait_backend
powershell -Command "try {Invoke-WebRequest -Uri http://localhost:8000 -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0} catch {exit 1}"
if errorlevel 1 (
    timeout /t 1 >nul
    goto wait_backend
)

timeout /t 2 >nul
start http://localhost:5173