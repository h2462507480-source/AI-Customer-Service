param(
    [string]$Python = "python",
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReleaseDir = Join-Path $ProjectRoot "release"
$Executable = Join-Path $ProjectRoot "dist\AI-Customer-Service.exe"

Push-Location $ProjectRoot
try {
    & $Python -m pip install -e ".[dev,build]"
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    if (-not $SkipTests) {
        & $Python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
    }
    & $Python -m PyInstaller --noconfirm --clean "packaging\AI-Customer-Service.spec"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    $SmokeTest = Start-Process -FilePath $Executable -ArgumentList "--smoke-test" -Wait -PassThru
    if ($SmokeTest.ExitCode -ne 0) {
        throw "Packaged executable smoke test failed with exit code $($SmokeTest.ExitCode)."
    }

    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    Copy-Item -LiteralPath $Executable -Destination $ReleaseDir -Force
    Compress-Archive -LiteralPath $Executable -DestinationPath (Join-Path $ReleaseDir "AI-Customer-Service-Portable.zip") -Force

    if (-not $SkipInstaller) {
        $MakeNsis = @(
            "C:\Program Files (x86)\NSIS\makensis.exe",
            "C:\Program Files\NSIS\makensis.exe",
            (Join-Path $env:LOCALAPPDATA "Programs\NSIS\makensis.exe")
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $MakeNsis) {
            throw "NSIS was not found. Install it or run with -SkipInstaller."
        }
        $Version = & $Python -c "import importlib.metadata; print(importlib.metadata.version('ai-store-support'))"
        & $MakeNsis "/INPUTCHARSET" "UTF8" "/DSOURCE_DIR=$($ProjectRoot)\dist" "/DOUTPUT_DIR=$ReleaseDir" "/DAPP_VERSION=$Version" "/DAPP_VERSION_NUM=$Version.0" "packaging\installer.nsi"
        if ($LASTEXITCODE -ne 0) { throw "NSIS build failed." }
    }

    Get-ChildItem -LiteralPath $ReleaseDir -File |
        Where-Object { $_.Name -ne "SHA256SUMS.txt" } |
        ForEach-Object { "$(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName | Select-Object -ExpandProperty Hash)  $($_.Name)" } |
        Set-Content -LiteralPath (Join-Path $ReleaseDir "SHA256SUMS.txt") -Encoding ascii
} finally {
    Pop-Location
}
