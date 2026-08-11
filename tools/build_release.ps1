param(
    [string]$CertificateThumbprint = $env:ARTBOARD_CUTTER_CERT_THUMBPRINT
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Executable = Join-Path $ProjectRoot "dist\ArtboardCutter.exe"
$InstallerScript = Join-Path $ProjectRoot "installer\ArtboardCutter.iss"
$ReleaseDir = Join-Path $ProjectRoot "release"

Push-Location $ProjectRoot
try {
    & .\build_exe.bat
    if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }

    $SignTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($CertificateThumbprint) {
        if (-not $SignTool) { throw "signtool.exe is required when a certificate thumbprint is supplied." }
        & $SignTool.Source sign /sha1 $CertificateThumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Executable
        if ($LASTEXITCODE -ne 0) { throw "Executable signing failed." }
    }

    $Inno = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $Inno) {
        Write-Warning "Inno Setup is not installed. The signed/unsigned standalone EXE is ready at $Executable"
        exit 0
    }
    & $Inno.Source $InstallerScript
    if ($LASTEXITCODE -ne 0) { throw "Installer build failed." }

    $Setup = Get-ChildItem -LiteralPath $ReleaseDir -Filter "ArtboardCutter-*-Setup.exe" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($CertificateThumbprint -and $Setup) {
        & $SignTool.Source sign /sha1 $CertificateThumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Setup.FullName
        if ($LASTEXITCODE -ne 0) { throw "Installer signing failed." }
    }
    Write-Output "Release ready: $($Setup.FullName)"
}
finally {
    Pop-Location
}
