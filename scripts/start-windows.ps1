param(
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$PgBin,
    [string]$DataDirectory,
    [int]$DatabasePort=55432,
    [int]$AppPort=8000,
    [switch]$SkipBuild
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
if (-not $DataDirectory) { $DataDirectory=Join-Path $projectRoot 'runtime/pgdata-windows' }
New-Item -ItemType Directory -Path (Join-Path $projectRoot 'runtime') -Force | Out-Null
function Invoke-Checked([string]$Executable,[string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable" }
}
if (-not (Test-Path -LiteralPath (Join-Path $DataDirectory 'PG_VERSION'))) {
    Invoke-Checked (Join-Path $PgBin 'initdb.exe') @('-D',$DataDirectory,'-U','alfa','-A','trust','--encoding=UTF8','--locale=C')
}
& (Join-Path $PgBin 'pg_ctl.exe') -D $DataDirectory status *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Checked (Join-Path $PgBin 'pg_ctl.exe') @('-D',$DataDirectory,'-l',(Join-Path $projectRoot 'runtime/postgres-windows.log'),'-o',"-h 127.0.0.1 -p $DatabasePort",'-w','start')
}
$dbExists=& (Join-Path $PgBin 'psql.exe') -h 127.0.0.1 -p $DatabasePort -U alfa -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='alfa_insight'"
if ($LASTEXITCODE -ne 0) { throw 'Cannot connect to local PostgreSQL' }
if (($dbExists -join '').Trim() -ne '1') {
    Invoke-Checked (Join-Path $PgBin 'createdb.exe') @('-h','127.0.0.1','-p',"$DatabasePort",'-U','alfa','alfa_insight')
}
$env:PYTHONPATH=Join-Path $projectRoot 'backend'
$env:DATABASE_URL="postgresql+psycopg://alfa@127.0.0.1:$DatabasePort/alfa_insight"
Invoke-Checked $PythonExe @('-m','alembic','-c','backend/alembic.ini','upgrade','head')
if (-not $SkipBuild) {
    Push-Location frontend
    try { & pnpm build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' } }
    finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) { throw 'Build frontend first' }
Write-Host "Alfa Insight: http://127.0.0.1:$AppPort"
Invoke-Checked $PythonExe @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$AppPort")
