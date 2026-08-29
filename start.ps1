$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path "backend/.venv/Scripts/python.exe")) { throw "Run .\setup.ps1 first." }
if (-not (Test-Path "backend/.env")) { Copy-Item "backend/.env.example" "backend/.env" }

docker compose up -d db | Out-Null
try { Invoke-RestMethod "http://localhost:11434/api/tags" | Out-Null } catch { throw "Ollama is not running. Start Ollama first." }

Write-Host "Starting FastAPI..." -ForegroundColor Cyan
$backend = Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --reload --port 8000" -WorkingDirectory "$root\backend" -PassThru

Write-Host "Waiting for backend..." -ForegroundColor Yellow
$ok=$false
for($i=0;$i -lt 30;$i++){Start-Sleep -Seconds 1;try{$h=Invoke-RestMethod "http://localhost:8000/api/health";if($h.status -eq "ok"){$ok=$true;break}}catch{}}
if(-not $ok){throw "Backend did not start. Check the Python process/output."}

Write-Host "Starting React..." -ForegroundColor Cyan
$frontend = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev -- --host localhost" -WorkingDirectory "$root\frontend" -PassThru
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"

Write-Host "`nApplication is running:`n  UI:  http://localhost:5173`n  API: http://localhost:8000/docs`n" -ForegroundColor Green
Write-Host "Close this PowerShell window only after running .\stop.ps1 if you want to stop the services." -ForegroundColor DarkGray
