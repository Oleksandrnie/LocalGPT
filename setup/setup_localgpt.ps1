$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

function Find-CompatiblePython {
    $candidates = @(
        @{ Command = "py"; Prefix = @("-3") },
        @{ Command = "python"; Prefix = @() }
    )
    foreach ($candidate in $candidates) {
        if (Get-Command $candidate.Command -ErrorAction SilentlyContinue) {
            $Prefix = $candidate.Prefix
            & $candidate.Command @Prefix -c "import sys; raise SystemExit(sys.version_info < (3, 10))" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
    }
    return $null
}

try {
    $Python = Find-CompatiblePython
    if (-not $Python) {
        $Answer = Read-Host "Python 3.10+ is missing. Install Python 3.13 with winget? [Y/n]"
        if ($Answer -match "^(n|no)$") {
            throw "Setup cancelled: Python is required."
        }
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw "winget is unavailable. Install Microsoft App Installer and rerun setup."
        }
        & winget install --id Python.Python.3.13 --exact --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "Python installation failed with exit code $LASTEXITCODE."
        }

        $KnownPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
        if (Test-Path $KnownPython) {
            $Python = @{ Command = $KnownPython; Prefix = @() }
        } else {
            $Python = Find-CompatiblePython
        }
        if (-not $Python) {
            throw "Python was installed but is not visible yet. Reopen PowerShell and rerun setup."
        }
    }

    $Prefix = $Python.Prefix
    $SetupCore = Join-Path $PSScriptRoot "setup_localgpt.py"
    & $Python.Command @Prefix $SetupCore @args
    $SetupExit = $LASTEXITCODE
} catch {
    Write-Host "[!] $($_.Exception.Message)" -ForegroundColor Red
    $SetupExit = 1
}

Write-Host ""
Read-Host "Press Enter to close PowerShell"
exit $SetupExit
