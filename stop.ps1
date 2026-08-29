Write-Host "Stopping AI Document Intelligence..." -ForegroundColor Yellow
Get-Process python,node,cmd -ErrorAction SilentlyContinue | Where-Object {$_.Path -like "*ai-doc-rag*" -or $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*vite*"} | Stop-Process -Force -ErrorAction SilentlyContinue
docker compose stop db | Out-Null
Write-Host "Stopped." -ForegroundColor Green
