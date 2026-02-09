# Outreach Engine - Start Script (No Docker)
# Runs backend and frontend with Ollama LLM
# Usage: .\start.ps1

param(
    [switch]$SkipInstall,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          🚀 OUTREACH ENGINE - Startup Script                 ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ══════════════════════════════════════════════════════════════════════════════
# CHECK PREREQUISITES
# ══════════════════════════════════════════════════════════════════════════════

Write-Host "📋 Checking prerequisites..." -ForegroundColor Yellow
Write-Host ""

# Check Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Python: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}

# Check Node.js
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Node.js: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Node.js not found. Install from https://nodejs.org" -ForegroundColor Red
    exit 1
}

# Check Ollama
$ollamaCheck = ollama --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Ollama: installed" -ForegroundColor Green
} else {
    Write-Host "  ✗ Ollama not found. Install from https://ollama.ai" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ══════════════════════════════════════════════════════════════════════════════
# CHECK OLLAMA SERVICE & MODEL
# ══════════════════════════════════════════════════════════════════════════════

Write-Host "🤖 Checking Ollama service..." -ForegroundColor Yellow

# Try to list models (this will fail if Ollama isn't running)
$ollamaList = ollama list 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ⚠ Ollama service not running. Starting it..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# Check for models
$models = ollama list 2>&1
if ($models -match "mistral|llama|phi|gemma") {
    Write-Host "  ✓ Ollama models available" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Available models:" -ForegroundColor Gray
    ollama list | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
} else {
    Write-Host "  ⚠ No models found. Pulling default model (mistral)..." -ForegroundColor Yellow
    Write-Host "    This may take a few minutes (4GB download)..." -ForegroundColor Gray
    ollama pull mistral
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ✗ Failed to pull model. Check your internet connection." -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Model 'mistral' installed" -ForegroundColor Green
}

Write-Host ""

# ══════════════════════════════════════════════════════════════════════════════
# SETUP ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════

if (-not $SkipInstall) {
    Write-Host "📦 Setting up environment..." -ForegroundColor Yellow

    # Create directories
    New-Item -ItemType Directory -Force -Path "sessions" | Out-Null
    New-Item -ItemType Directory -Force -Path "uploads" | Out-Null
    New-Item -ItemType Directory -Force -Path "chroma_data" | Out-Null
    Write-Host "  ✓ Directories created" -ForegroundColor Green

    # Create .env if missing
    if (-not (Test-Path ".\.env")) {
        if (Test-Path ".\.env.example") {
            Copy-Item ".\.env.example" ".\.env"
            Write-Host "  ✓ Created .env from template" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ No .env.example found. Create .env manually." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ✓ .env file exists" -ForegroundColor Green
    }

    # Setup Python virtual environment
    if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
        Write-Host "  Creating Python virtual environment..." -ForegroundColor Gray
        python -m venv venv
    }
    Write-Host "  ✓ Python venv ready" -ForegroundColor Green

    # Install Python dependencies
    Write-Host "  Installing Python packages..." -ForegroundColor Gray
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt -q 2>&1 | Out-Null
    Write-Host "  ✓ Python dependencies installed" -ForegroundColor Green

    # Install frontend dependencies
    if (-not (Test-Path ".\frontend\node_modules")) {
        Write-Host "  Installing frontend packages..." -ForegroundColor Gray
        Push-Location frontend
        npm install --silent 2>&1 | Out-Null
        Pop-Location
    }
    Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green
}

Write-Host ""

# ══════════════════════════════════════════════════════════════════════════════
# START SERVICES
# ══════════════════════════════════════════════════════════════════════════════

Write-Host "🚀 Starting services..." -ForegroundColor Yellow
Write-Host ""

if (-not $FrontendOnly) {
    Write-Host "  Starting Backend API (port 8080)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
        `$Host.UI.RawUI.WindowTitle = 'Outreach Engine - Backend API'
        Write-Host '🔧 Backend API Server' -ForegroundColor Cyan
        Write-Host '─────────────────────' -ForegroundColor Gray
        cd '$PWD'
        .\venv\Scripts\Activate.ps1
        python -m uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8080
"@
    Start-Sleep -Seconds 2
}

if (-not $BackendOnly) {
    Write-Host "  Starting Frontend (port 5173)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
        `$Host.UI.RawUI.WindowTitle = 'Outreach Engine - Frontend'
        Write-Host '🎨 Frontend Dev Server' -ForegroundColor Cyan
        Write-Host '──────────────────────' -ForegroundColor Gray
        cd '$PWD\frontend'
        npm run dev
"@
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    ✅ STARTUP COMPLETE                       ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  📡 Backend API:   http://localhost:8080" -ForegroundColor White
Write-Host "  🎨 Frontend UI:   http://localhost:5173" -ForegroundColor White
Write-Host "  📚 API Docs:      http://localhost:8080/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Configured Model: $((Get-Content .\.env | Select-String 'OLLAMA_MODEL').ToString().Split('=')[1])" -ForegroundColor Gray
Write-Host ""
Write-Host "  To change model, edit .env and set OLLAMA_MODEL=<model_name>" -ForegroundColor Gray
Write-Host "  Available: mistral, llama3, llama2, phi3, gemma, mixtral" -ForegroundColor Gray
Write-Host ""

# Open browser after a delay
Write-Host "Opening browser in 5 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"
