# Load users + profiles from JSON files (single source of truth)
function Get-JsonFirstValue {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string[]]$Keys
    )

    if ($null -eq $Object) { return $null }

    foreach ($k in $Keys) {
        $prop = $Object.PSObject.Properties[$k]
        if ($null -ne $prop) {
            $v = $prop.Value
            if ($null -ne $v -and -not [string]::IsNullOrWhiteSpace([string]$v)) {
                return $v
            }
        }
    }

    return $null
}

$script:DataDir = Join-Path (Split-Path $PSScriptRoot -Parent) "data"
$script:DefaultPassword = "Pass@123"

$script:DummyUsers = @()
$script:DummyProfiles = @{}

function Initialize-DummyDataFromFiles {
    $profiles = @{}
    $users = @()
    $seenUsers = @{}

    if (-not (Test-Path $script:DataDir)) {
        Write-Warning "Data folder not found: $script:DataDir"
        $script:DummyUsers = @()
        $script:DummyProfiles = @{}
        return
    }

    $files = Get-ChildItem -Path $script:DataDir -Filter "*.json" -File -ErrorAction SilentlyContinue

    foreach ($file in $files) {
        try {
            $raw = Get-Content -Path $file.FullName -Raw -Encoding UTF8
            if ([string]::IsNullOrWhiteSpace($raw)) { continue }

            $j = $raw | ConvertFrom-Json

            $username = Get-JsonFirstValue -Object $j -Keys @("username", "Username")
            if (-not $username) { $username = [System.IO.Path]::GetFileNameWithoutExtension($file.Name) }
            if (-not $username) { continue }

            $password = Get-JsonFirstValue -Object $j -Keys @("password", "Password")
            if (-not $password) { $password = $script:DefaultPassword }

            $profileNode = $j
            if ($j.PSObject.Properties["profile"] -and $null -ne $j.profile) { $profileNode = $j.profile }

            $userNode = $null
            if ($j.PSObject.Properties["user"] -and $null -ne $j.user) { $userNode = $j.user }

            $firstName = Get-JsonFirstValue -Object $profileNode -Keys @("first_name", "FirstName")
            $lastName  = Get-JsonFirstValue -Object $profileNode -Keys @("last_name", "LastName")

            if (-not $firstName -and $null -ne $userNode) {
                $firstName = Get-JsonFirstValue -Object $userNode -Keys @("first_name", "FirstName")
            }
            if (-not $lastName -and $null -ne $userNode) {
                $lastName = Get-JsonFirstValue -Object $userNode -Keys @("last_name", "LastName")
            }

            if ((-not $firstName -or -not $lastName) -and $null -ne $userNode) {
                $fullName = Get-JsonFirstValue -Object $userNode -Keys @("name", "Name")
                if ($fullName) {
                    $parts = ([string]$fullName).Trim() -split "\s+", 2
                    if (-not $firstName -and $parts.Count -ge 1) { $firstName = $parts[0] }
                    if (-not $lastName) { $lastName = if ($parts.Count -ge 2) { $parts[1] } else { "" } }
                }
            }

            $aadhar = Get-JsonFirstValue -Object $profileNode -Keys @("aadhar_number", "Aadhar")
            if (-not $aadhar) { $aadhar = Get-JsonFirstValue -Object $j -Keys @("aadhar_number", "Aadhar") }
            if (-not $aadhar -and $null -ne $userNode) { $aadhar = Get-JsonFirstValue -Object $userNode -Keys @("aadhar_number", "Aadhar") }

            $pan = Get-JsonFirstValue -Object $profileNode -Keys @("pan_number", "PAN")
            if (-not $pan) { $pan = Get-JsonFirstValue -Object $j -Keys @("pan_number", "PAN") }
            if (-not $pan -and $null -ne $userNode) { $pan = Get-JsonFirstValue -Object $userNode -Keys @("pan_number", "PAN") }

            $profiles[$username] = @{
                FirstName = if ($firstName) { [string]$firstName } else { "" }
                LastName  = if ($lastName)  { [string]$lastName }  else { "" }
                Aadhar    = if ($aadhar)    { [string]$aadhar }    else { "" }
                PAN       = if ($pan)       { [string]$pan }       else { "" }
            }

            if (-not $seenUsers.ContainsKey($username)) {
                $users += @{
                    Username = [string]$username
                    Password = [string]$password
                }
                $seenUsers[$username] = $true
            }
        }
        catch {
            Write-Warning "Skipping invalid JSON: $($file.FullName)"
        }
    }

    # Optional debug
    Write-Host ("Loaded users: {0}, profiles: {1}" -f $users.Count, $profiles.Count) -ForegroundColor DarkGray

    $script:DummyUsers = $users
    $script:DummyProfiles = $profiles
}

Initialize-DummyDataFromFiles

$script:CurrentSession = $null
$script:SessionDir = Join-Path $PSScriptRoot "session"
$script:SessionFile = Join-Path $script:SessionDir "current_user.json"

function Invoke-UserLogin {
    param(
        [Parameter(Mandatory = $true)][string]$Username,
        [Parameter(Mandatory = $true)][string]$Password
    )

    $user = $script:DummyUsers | Where-Object {
        $_.Username -eq $Username -and $_.Password -eq $Password
    }

    if (-not $user) {
        return @{ Success = $false; Message = "Invalid username or password." }
    }

    if (-not $script:DummyProfiles.ContainsKey($Username)) {
        return @{ Success = $false; Message = "Profile not found for user." }
    }

    $script:CurrentSession = @{
        Username = $Username
        Profile  = $script:DummyProfiles[$Username]
    }

    return @{ Success = $true; Message = "Login successful." }
}

function Save-LoginSession {
    if (-not $script:CurrentSession) { return }

    if (-not (Test-Path $script:SessionDir)) {
        New-Item -Path $script:SessionDir -ItemType Directory -Force | Out-Null
    }

    $payload = @{
        username = $script:CurrentSession.Username
        profile  = @{
            first_name    = $script:CurrentSession.Profile.FirstName
            last_name     = $script:CurrentSession.Profile.LastName
            aadhar_number = $script:CurrentSession.Profile.Aadhar
            pan_number    = $script:CurrentSession.Profile.PAN
        }
        login_time = (Get-Date).ToString("o")
    }

    $payload | ConvertTo-Json -Depth 6 | Set-Content -Path $script:SessionFile -Encoding UTF8
}

function Show-LoginUI {
    Clear-Host
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host "        AI Financial Coach         " -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host "Login" -ForegroundColor Yellow
    Write-Host ""

    $username = Read-Host "Username"
    $password = Read-Host "Password"

    return Invoke-UserLogin -Username $username.Trim() -Password $password
}

function Show-DashboardHeader {
    if (-not $script:CurrentSession) { return }

    $p = $script:CurrentSession.Profile
    Write-Host ""
    Write-Host "============ DASHBOARD HEADER ============" -ForegroundColor Green
    Write-Host ("Logged in as : {0}" -f $script:CurrentSession.Username)
    Write-Host ("Name         : {0} {1}" -f $p.FirstName, $p.LastName)
    Write-Host ("Aadhar       : {0}" -f $p.Aadhar)
    Write-Host ("PAN          : {0}" -f $p.PAN)
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
}

# Entry point
$result = Show-LoginUI
if (-not $result.Success) {
    Write-Host $result.Message -ForegroundColor Red
    exit 1
}

Save-LoginSession
Write-Host $result.Message -ForegroundColor Green
Show-DashboardHeader
Write-Host "Session saved: $script:SessionFile" -ForegroundColor DarkGray
exit 0