@echo off
cd /d %~dp0

REM ===== 0. Virtual environment =====
if not exist venv (
    echo [Setup] Creating virtual environment...
    python -m venv venv || exit /b 1
)

echo [Setup] Activating virtual environment...
call venv\Scripts\activate || exit /b 1

REM ===== 1. Backend =====
cd backend || exit /b 1

if not exist .env (
    (
        echo GEMINI_API_KEY=
        echo GROQ_API_KEY=
    ) > .env
)
echo [Backend] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || exit /b 1

echo [Backend] Starting server...
start "backend" cmd /k "call ..\venv\Scripts\activate && python -m uvicorn main:app --reload > backend.log 2>&1"

cd ..

REM ===== 2. Frontend =====
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

REM ===== 3. Wait backend =====
:wait_backend
powershell -Command "try {Invoke-WebRequest -Uri http://localhost:8000 -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0} catch {exit 1}"
if errorlevel 1 (
    timeout /t 1 >nul
    goto wait_backend
)

timeout /t 2 >nul
start http://localhost:5173