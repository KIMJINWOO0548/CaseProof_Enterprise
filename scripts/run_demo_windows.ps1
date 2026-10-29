param([ValidateRange(1024,65535)][int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 venv creation failed; use a supported installed Python.' }
}
$DemoPython = '.\.venv\Scripts\python.exe'
& $DemoPython -m pip install --require-hashes -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$env:CASEPROOF_DEMO_MODE = '1'
if (-not $env:CASEPROOF_DATABASE_URL) { $env:CASEPROOF_DATABASE_URL = 'sqlite:///./caseproof_demo.sqlite3' }
Write-Host '[CaseProof] Local synthetic demo. Credentials below must stay private.'
& $DemoPython -m service.cli init-demo
if ($LASTEXITCODE -ne 0) { throw 'Demo initialization failed.' }
Write-Host "Open http://127.0.0.1:$Port and use the generated role tokens."
& $DemoPython -m uvicorn service.app:app --host 127.0.0.1 --port $Port --workers 1
if ($LASTEXITCODE -ne 0) { throw 'Demo server exited with an error.' }
