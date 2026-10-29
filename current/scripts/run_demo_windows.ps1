param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .venv\Scripts\python.exe)) {
    py -3 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:CASEPROOF_DEMO_MODE = "1"
$env:CASEPROOF_DATABASE_URL = "sqlite:///./caseproof_demo.sqlite3"
Write-Host "[CaseProof] SYNTHETIC LOCAL DATA ONLY. Never import real insurance customer data."
& .\.venv\Scripts\python.exe -m service.cli init-demo
Write-Host "Open http://127.0.0.1:$Port and paste a generated role token."
& .\.venv\Scripts\python.exe -m uvicorn service.app:app --host 127.0.0.1 --port $Port --workers 1
