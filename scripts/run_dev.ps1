# Start FastAPI backend and Next.js frontend together
$projectRoot = $PSScriptRoot | Split-Path -Parent

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .venv\Scripts\Activate.ps1; python -m uvicorn api.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\frontend-next'; npm run dev"

Write-Host ""
Write-Host "Starting development servers..." -ForegroundColor Cyan
Write-Host "  Backend  -> http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend -> http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "API docs available at http://localhost:8000/docs" -ForegroundColor Yellow
