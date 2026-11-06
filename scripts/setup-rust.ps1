# Default mode only inspects prerequisites. Install modes are explicit and separate.
[CmdletBinding(DefaultParameterSetName = 'Check')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'BuildTools')]
    [switch]$InstallBuildTools,
    [Parameter(Mandatory = $true, ParameterSetName = 'Rust')]
    [switch]$InstallRust
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Get-NyxRustBin {
    if ($env:CARGO_HOME) { return (Join-Path $env:CARGO_HOME 'bin') }
    return (Join-Path $env:USERPROFILE '.cargo\bin')
}

function Get-NyxToolchainState {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    $msvc = $false
    if (Test-Path -LiteralPath $vswhere) {
        $linkers = @(& $vswhere -all -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find 'VC\Tools\MSVC\**\bin\Hostx64\x64\link.exe')
        $msvc = ($LASTEXITCODE -eq 0 -and $linkers.Count -gt 0)
    }
    $sdk = $false
    $sdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\Lib'
    if (Test-Path -LiteralPath $sdkRoot) {
        foreach ($version in Get-ChildItem -LiteralPath $sdkRoot -Directory) {
            if ((Test-Path -LiteralPath (Join-Path $version.FullName 'um\x64\kernel32.lib')) -and
                (Test-Path -LiteralPath (Join-Path $version.FullName 'ucrt\x64\ucrt.lib'))) {
                $sdk = $true
            }
        }
    }
    $rustBin = Get-NyxRustBin
    $rustCommand = Get-Command rustc.exe -ErrorAction SilentlyContinue
    $cargoCommand = Get-Command cargo.exe -ErrorAction SilentlyContinue
    [PSCustomObject]@{
        RustInstalled = ($null -ne $rustCommand -or (Test-Path -LiteralPath (Join-Path $rustBin 'rustc.exe')))
        CargoInstalled = ($null -ne $cargoCommand -or (Test-Path -LiteralPath (Join-Path $rustBin 'cargo.exe')))
        MsvcInstalled = $msvc
        WindowsSdkInstalled = $sdk
        Administrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
}

$state = Get-NyxToolchainState
if (-not $InstallBuildTools -and -not $InstallRust) {
    $state
    return
}

if ($InstallBuildTools) {
    if ($state.MsvcInstalled -and $state.WindowsSdkInstalled) {
        Write-Host 'MSVC and the Windows SDK are already present; nothing installed.'
        return
    }
    if (-not $state.Administrator) {
        throw 'MSVC/SDK setup requires an Administrator PowerShell. No changes made. Run .\scripts\setup-rust.ps1 -InstallBuildTools there.'
    }
} else {
    if (-not $state.MsvcInstalled -or -not $state.WindowsSdkInstalled) {
        throw 'Install MSVC and the Windows SDK first. No changes made. Use .\scripts\setup-rust.ps1 -InstallBuildTools from an Administrator PowerShell.'
    }
    if ($state.Administrator) {
        throw 'Run -InstallRust from your normal user PowerShell so Rust belongs to the intended account. No changes made.'
    }
    if ($state.RustInstalled -or $state.CargoInstalled) {
        Write-Host 'Existing user Rust installation detected; preserved. Check rustup show and cargo --version before modifying it.'
        return
    }
}

$downloads = Join-Path $root '.tools\setup'
$null = New-Item -ItemType Directory -Path $downloads -Force
if ($InstallBuildTools) {
    $installer = Join-Path $downloads 'vs_buildtools.exe'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://aka.ms/vs/17/release/vs_BuildTools.exe' -OutFile $installer
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') {
        throw 'Microsoft installer signature validation failed; nothing executed.'
    }
    $arguments = @('--quiet', '--wait', '--norestart', '--nocache', '--addProductLang', 'En-us',
        '--add', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
        '--add', 'Microsoft.VisualStudio.Component.Windows11SDK.26100')
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010)) {
        throw "MSVC installer failed with exit code $($process.ExitCode)."
    }
    if ($process.ExitCode -eq 3010) {
        Write-Host 'MSVC installer requests a reboot; no reboot was performed. Recheck after your next restart.'
    }
    $updated = Get-NyxToolchainState
    $updated
    if (-not $updated.MsvcInstalled -or -not $updated.WindowsSdkInstalled) {
        if ($process.ExitCode -eq 3010) { return }
        throw 'Installer exited successfully but required MSVC/SDK components were not detected. Rust was not installed; inspect the installer result.'
    }
    Write-Host 'Next, use your normal user PowerShell: .\scripts\setup-rust.ps1 -InstallRust'
} else {
    $installer = Join-Path $downloads 'rustup-init.exe'
    $url = 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe'
    $expected = ((Invoke-WebRequest -UseBasicParsing -Uri ($url + '.sha256')).Content.Trim() -split '\s+')[0]
    if ($expected -notmatch '^[a-fA-F0-9]{64}$') { throw 'Invalid official Rust installer checksum; nothing executed.' }
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $installer
    if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $expected) {
        throw 'Rust installer checksum mismatch; nothing executed.'
    }
    & $installer -y --profile minimal --default-host x86_64-pc-windows-msvc --default-toolchain stable
    if ($LASTEXITCODE -ne 0) { throw "Rust installer failed with exit code $LASTEXITCODE." }
    $updated = Get-NyxToolchainState
    $updated
    if (-not $updated.RustInstalled -or -not $updated.CargoInstalled) {
        throw 'Rust installer exited successfully but required user executables were not detected.'
    }
    $rustBin = Get-NyxRustBin
    & (Join-Path $rustBin 'rustc.exe') --version
    if ($LASTEXITCODE -ne 0) { throw 'Installed Rust compiler did not start successfully.' }
    & (Join-Path $rustBin 'cargo.exe') --version
    if ($LASTEXITCODE -ne 0) { throw 'Installed Cargo did not start successfully.' }
    Write-Host 'Open a fresh normal PowerShell, then run cargo test and cargo build --release --jobs 1.'
}
