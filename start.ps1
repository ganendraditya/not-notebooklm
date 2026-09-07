Write-Host "Starting NotbookLM..."

# Start Backend
Write-Host "Setting up and starting Backend on http://localhost:8000..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; if (!(Test-Path venv)) { python -m venv venv }; .\venv\Scripts\activate; uvicorn main:app --reload --port 8000"

# Start Frontend
Write-Host "Starting Frontend on http://localhost:3000..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "========================================="
Write-Host "✅ NotbookLM servers are running!"
Write-Host "➡️  UI: http://localhost:3000"
Write-Host "➡️  Backend: http://localhost:8000"
Write-Host "========================================="
