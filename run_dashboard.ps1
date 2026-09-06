$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1) Run login first
$loginScript = Join-Path $PSScriptRoot "app\login.ps1"
$sessionFile = Join-Path $PSScriptRoot "app\session\current_user.json"

if (-not (Test-Path $loginScript)) {
    Write-Host "Login script not found: $loginScript" -ForegroundColor Red
    exit 1
}

# Remove stale session so login must recreate it
if (Test-Path $sessionFile) {
    Remove-Item $sessionFile -Force -ErrorAction SilentlyContinue
}

# Resolve shell executable
$psExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

Write-Host "Starting login workflow..." -ForegroundColor Yellow
& $psExe -NoProfile -ExecutionPolicy Bypass -File $loginScript
$loginExitCode = $LASTEXITCODE

if ($loginExitCode -ne 0) {
    Write-Host "Access denied. Dashboard will not start." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $sessionFile)) {
    Write-Host "Session file missing after login: $sessionFile" -ForegroundColor Red
    exit 1
}

# Resolve which user data file will be loaded by dashboard
try {
    $session = Get-Content -Path $sessionFile -Raw | ConvertFrom-Json
    $username = $session.username
    $explicitPath = $session.user_json_path
    if (-not $explicitPath -and $session.profile) {
        $explicitPath = $session.profile.user_json_path
    }

    $dataFileToLoad = if ($explicitPath) {
        $explicitPath
    } else {
        Join-Path $PSScriptRoot ("data\{0}.json" -f $username)
    }

    Write-Host "User data file to load: $dataFileToLoad" -ForegroundColor Cyan
}
catch {
    Write-Host "Could not resolve user data file from session: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 2) Expose session file path for Streamlit app
$env:AIFC_SESSION_FILE = $sessionFile
Write-Host "Login validated. Opening dashboard..." -ForegroundColor Green

# 3) Start dashboard
& streamlit run app\dashboard.py
exit $LASTEXITCODE