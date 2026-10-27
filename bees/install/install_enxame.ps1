<#
.SYNOPSIS
    ENXAME Bee - Universal Installer (PowerShell for Windows)

.DESCRIPTION
    Detecta Windows e executa instalacao completa do ENXAME Bee

.EXAMPLE
    .\install_enxame.ps1

.EXAMPLE
    .\install_enxame.ps1 -DryRun -SkipModelTest
#>

param(
    [switch]$DryRun,
    [switch]$SkipOllama,
    [switch]$SkipModelTest,
    [switch]$ForceOllama,
    [switch]$ForceModelDownload
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

# Check if running as Administrator
function Test-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Main
Step "ENXAME Bee - Windows Installer v1.0.0"

if (-not (Test-Admin)) {
    Warn "Reiniciando como Administrador..."
    Start-Process powershell -ArgumentList "-File", $PSCommandPath, "-Verb", "RunAs"
    exit
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$batFile = Join-Path $scriptDir "install_enxame.bat"

if (-not (Test-Path $batFile)) {
    Error "install_enxame.bat nao encontrado em $scriptDir"
    exit 1
}

# Build arguments
$args = @()
if ($DryRun) { $args += "--dry-run" }
if ($SkipOllama) { $args += "--skip-ollama" }
if ($SkipModelTest) { $args += "--skip-model-test" }
if ($ForceOllama) { $args += "--force-ollama" }
if ($ForceModelDownload) { $args += "--force-model-download" }

Log "Executando instalador Windows..."
& cmd /c "`"$batFile`" $($args -join ' ')"

if ($LASTEXITCODE -ne 0) {
    Error "Instalacao falhou com codigo $LASTEXITCODE"
    exit $LASTEXITCODE
}

Log "Instalacao concluida com sucesso!"