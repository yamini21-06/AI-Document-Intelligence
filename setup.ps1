$ErrorActionPreference = "Stop"
Write-Host "`n=== AI Document Intelligence - Setup ===`n" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python is not installed or not on PATH." }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js is not installed or not on PATH." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is not installed or not on PATH." }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw "Ollama is not installed or not on PATH." }

if (-not (Test-Path "backend/.env")) { Copy-Item "backend/.env.example" "backend/.env" }

Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "backend/.venv")) { python -m venv backend/.venv }
& "backend/.venv/Scripts/python.exe" -m pip install --upgrade pip
& "backend/.venv/Scripts/python.exe" -m pip install -r backend/requirements.txt

Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location frontend
npm install
Pop-Location

Write-Host "Starting PostgreSQL..." -ForegroundColor Yellow
docker compose up -d db

Write-Host "Checking Ollama..." -ForegroundColor Yellow
try { Invoke-RestMethod "http://localhost:11434/api/tags" | Out-Null } catch { throw "Ollama is not running. Start Ollama, then run setup again." }

$models = (ollama list | Out-String)
if ($models -notmatch "nomic-embed-text") { Write-Host "Pulling embedding model..." -ForegroundColor Yellow; ollama pull nomic-embed-text }
if ($models -notmatch "llama3.2:3b") { Write-Host "Pulling LLM model..." -ForegroundColor Yellow; ollama pull llama3.2:3b }

Write-Host "`nSetup complete. Run .\start.ps1`n" -ForegroundColor Green
