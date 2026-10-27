<#
.SYNOPSIS
    ENXAME Bee - Windows Uninstaller

.DESCRIPTION
    Remove completamente o ENXAME Bee do Windows

.EXAMPLE
    .\uninstall_enxame.ps1

.EXAMPLE
    .\uninstall_enxame.ps1 -RemoveOllama -KeepData
#>

param(
    [switch]$RemoveOllama,
    [switch]$ForceRemoveOllama,
    [switch]$KeepData,
    [switch]$DryRun,
    [switch]$Yes
)

# Colors
$GREEN = "`033[0;32m"
$RED = "`033[0;31m"
$YELLOW = "`033[1;33m"
$BLUE = "`033[0;34m"
$NC = "`033[0m"

function Log($msg) { Write-Host "${GREEN}[INFO]${NC} $msg" }
function Warn($msg) { Write-Host "${YELLOW}[WARN]${NC} $msg" }
function Error($msg) { Write-Host "${RED}[ERROR]${NC} $msg" }
function Step($msg) { Write-Host "`n${BLUE}=== $msg ===${NC}" }

# Check Admin
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Warn "Reiniciando como Administrador..."
    Start-Process powershell -ArgumentList "-File", $PSCommandPath, $PSBoundParameters.Keys.ForEach({"-$_"}), "-Verb", "RunAs"
    exit
}

if (-not $Yes -and -not $DryRun) {
    $confirm = Read-Host "Isso removera a Abelha completamente. Continuar? [y/N]"
    if ($confirm -notin 'y','Y') {
        Write-Host "Cancelado."
        exit 0
    }
}

if ($DryRun) {
    Log "MODO DRY-RUN - Nenhuma acao sera executada"
}

Step "Parando servicos..."
if (-not $DryRun) {
    # Stop Bee service
    Get-Service "enxame-bee" -ErrorAction SilentlyContinue | Stop-Service -Force -ErrorAction SilentlyContinue
    Set-Service "enxame-bee" -StartupType Disabled -ErrorAction SilentlyContinue
    
    # Stop scheduled task
    schtasks /Delete /TN "ENXAME Bee" /F 2>$null
}

Step "Removendo binarios..."
if (-not $DryRun) {
    $paths = @(
        "${env:ProgramFiles}\ENXAME Bee",
        "${env:LOCALAPPDATA}\ENXAME Bee",
        "${env:ProgramFiles}\enxame-bee",
        "${env:LOCALAPPDATA}\enxame-bee"
    )
    
    foreach ($path in $paths) {
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
            Log "Removido: $path"
        }
    }
}

Step "Removendo do PATH..."
if (-not $DryRun) {
    # Remove from user PATH
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $newPath = ($userPath -split ';' | Where-Object { $_ -notlike "*enxame*" -and $_ -notlike "*ENXAME*" }) -join ';'
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    
    # Remove from system PATH if present
    $sysPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($sysPath -like "*enxame*" -or $sysPath -like "*ENXAME*") {
        $newSysPath = ($sysPath -split ';' | Where-Object { $_ -notlike "*enxame*" -and $_ -notlike "*ENXAME*" }) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $newSysPath, "Machine")
    }
}

if (-not $KeepData) {
    Step "Removendo dados..."
    if (-not $DryRun) {
        $dataPaths = @(
            "${env:LOCALAPPDATA}\enxame",
            "${env:LOCALAPPDATA}\enxame-bee",
            "${env:APPDATA}\enxame",
            "${env:APPDATA}\enxame-bee"
        )
        
        foreach ($path in $dataPaths) {
            if (Test-Path $path) {
                Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
                Log "Removido: $path"
            }
        }
    }
} else {
    Log "Mantendo dados (--keep-data)"
}

Step "Limpando registro..."
if (-not $DryRun) {
    $regPaths = @(
        "HKCU:\Software\ENXAME",
        "HKCU:\Software\enxame-bee",
        "HKLM:\SOFTWARE\ENXAME",
        "HKLM:\SOFTWARE\enxame-bee"
    )
    
    foreach ($reg in $regPaths) {
        if (Test-Path $reg) {
            Remove-Item -Recurse -Force $reg -ErrorAction SilentlyContinue
            Log "Removido registro: $reg"
        }
    }
}

if ($RemoveOllama -or $ForceRemoveOllama) {
    Step "Removendo Ollama..."
    if (-not $DryRun) {
        # Stop service
        Get-Service "Ollama" -ErrorAction SilentlyContinue | Stop-Service -Force -ErrorAction SilentlyContinue
        Set-Service "Ollama" -StartupType Disabled -ErrorAction SilentlyContinue
        
        # Uninstall via package manager
        try {
            $app = Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like "*Ollama*" }
            if ($app) {
                $app.Uninstall()
            }
        } catch {}
        
        # Remove files
        $ollamaPaths = @(
            "${env:ProgramFiles}\Ollama",
            "${env:LOCALAPPDATA}\Programs\Ollama",
            "${env:USERPROFILE}\.ollama"
        )
        
        foreach ($path in $ollamaPaths) {
            if (Test-Path $path) {
                Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
                Log "Removido: $path"
            }
        }
    }
}

Log "=================================================="
Log "Desinstalacao concluida!"
Log "=================================================="

if ($KeepData) {
    Log "Dados mantidos em: ${env:LOCALAPPDATA}\enxame\bee"
}