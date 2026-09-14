# Script to start both backend and frontend servers on Windows

$RootDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if ($RootDir) { Set-Location $RootDir }

# ------------------------------------------------------------------------------
# Secret Management Resolution
# ------------------------------------------------------------------------------
if ($env:DOPPLER_ENVIRONMENT) {
    Write-Host "[Security] Secrets injected via Doppler (Config: $env:DOPPLER_CONFIG / Env: $env:DOPPLER_ENVIRONMENT)"
} elseif ($env:INFISICAL_PROJECT_ID -or $env:INFISICAL_ENV) {
    Write-Host "[Security] Secrets injected via Infisical"
} elseif (Test-Path (Join-Path $RootDir "backend\.env")) {
    Write-Host "[Config] Secrets loaded from local backend/.env"
} else {
    # If no backend/.env exists, check if Doppler is installed and configured
    $dopplerCmd = Get-Command doppler -ErrorAction SilentlyContinue
    $dopplerProject = $null
    if ($dopplerCmd) {
        try {
            $dopplerProject = & doppler configure get project --plain 2>$null
        } catch {
            $dopplerProject = $null
        }
    }

    if ($dopplerCmd -and $dopplerProject) {
        Write-Host "[Notice] No backend/.env found, but Doppler is configured."
        Write-Host "[Security] Launching application with Doppler secret injection..."
        $scriptPath = if ($PSCommandPath) { $PSCommandPath } else { Join-Path $RootDir "start.ps1" }
        & doppler run -- powershell -ExecutionPolicy Bypass -File $scriptPath @args
        exit $LASTEXITCODE
    } else {
        Write-Host "[Notice] backend/.env not found and no Secret Manager active."
        Write-Host "         Please create backend/.env from backend/.env.example or run with 'doppler run -- powershell -File .\start.ps1'."
    }
}

Write-Host "Starting NotbookLM..."

# Start Backend
Write-Host "Setting up and starting Backend on http://localhost:8000..."
Start-Process powershell -WorkingDirectory (Join-Path $RootDir "backend") -ArgumentList "-NoExit", "-Command", "if (!(Test-Path 'venv')) { python -m venv venv }; .\venv\Scripts\activate; uvicorn main:app --reload --port 8000"

# Start Frontend
Write-Host "Starting Frontend on http://localhost:3000..."
Start-Process powershell -WorkingDirectory (Join-Path $RootDir "frontend") -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host "========================================="
Write-Host "✅ NotbookLM servers are running!"
Write-Host "➡️  UI: http://localhost:3000"
Write-Host "➡️  Backend: http://localhost:8000"
Write-Host "========================================="
