<#>
.SYNOPSIS
    ENXAME Universal Installer - Windows Wrapper
.DESCRIPTION
    Baixa e executa o instalador Python universal.
    Para usuários não-técnicos: duplo clique ou PowerShell.
.NOTES
    Requer: PowerShell 5.1+ (Windows 10/11), Internet
#>

param(
    [switch]$Auto,
    [switch]$ForceOllama,
    [switch]$ForceModel,
    [string]$Model,
    [switch]$NoVision,
    [switch]$NoShortcuts,
    [string]$DataDir,
    [int]$Port = 8765,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Cores
$Red = "`e[91m"; $Green = "`e[92m"; $Yellow = "`e[93m"; $Blue = "`e[94m"; $Reset = "`e[0m"
function Log-Info  { Write-Host "$Blue[INFO]$Reset $args" }
function Log-Ok    { Write-Host "$Green[OK]$Reset $args" }
function Log-Warn  { Write-Host "$Yellow[AVISO]$Reset $args" }
function Log-Error { Write-Host "$Red[ERRO]$Reset $args" }

Write-Host "`n$Blue============================================"
Write-Host "  ENXAME UNIVERSAL INSTALLER - Windows"
Write-Host "============================================`n"

# Verificar Python
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $pythonCmd = "python" }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $pythonCmd = "python3" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $pythonCmd = "py -3" }

if (-not $pythonCmd) {
    Log-Warn "Python não encontrado. Instalando via winget..."
    winget install --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if (Get-Command python -ErrorAction SilentlyContinue) { $pythonCmd = "python" }
    else { Log-Error "Falha ao instalar Python. Instale manualmente em python.org"; exit 1 }
}
Log-Ok "Python encontrado: $($pythonCmd)"

# Verificar pip
try { & $pythonCmd -m pip --version | Out-Null }
catch {
    Log-Warn "pip não encontrado. Instalando..."
    & $pythonCmd -m ensurepip --upgrade
}

# Baixar instalador universal
$installerUrl = "https://raw.githubusercontent.com/enxamepublic/enxamepublic/main/bees/install/universal_installer.py"
$installerPath = "$env:TEMP\enxame_universal_installer.py"

Log-Info "Baixando instalador universal..."
try {
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    Log-Ok "Instalador baixado"
}
catch {
    Log-Error "Falha ao baixar instalador: $_"
    exit 1
}

# Construir argumentos
$argsList = @()
if ($Auto) { $argsList += "--auto" }
if ($ForceOllama) { $argsList += "--force-ollama" }
if ($ForceModel) { $argsList += "--force-model" }
if ($Model) { $argsList += "--model $Model" }
if ($NoVision) { $argsList += "--no-vision" }
if ($NoShortcuts) { $argsList += "--no-shortcuts" }
if ($DataDir) { $argsList += "--data-dir `"$DataDir`"" }
if ($Port) { $argsList += "--port $Port" }
if ($DryRun) { $argsList += "--dry-run" }

$cmd = "$pythonCmd `"$installerPath`" $($argsList -join ' ')"
Log-Info "Executando: $cmd"
Log-Info "Isso pode levar vários minutos (download de modelos)...`n"

# Executar
$exitCode = 0
try {
    & $pythonCmd $installerPath @argsList
    $exitCode = $LASTEXITCODE
}
catch {
    Log-Error "Erro durante instalação: $_"
    $exitCode = 1
}

if ($exitCode -eq 0) {
    Log-Ok "`nInstalação concluída com sucesso!"
} else {
    Log-Error "`nInstalação falhou (código $exitCode)"
    Log-Info "Verifique o log em: $env:LOCALAPPDATA\enxame\bee\install.log"
}

Read-Host -Prompt "Pressione Enter para sair"
exit $exitCode