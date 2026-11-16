#requires -Version 5.1
# =============================================================================
# ENXAME - Instalador Unificado (PowerShell)
# Executa instalador Python next-next-finish
# =============================================================================

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$installer = Join-Path $scriptDir "install.py"

if (!(Test-Path $installer)) {
    Write-Host "Instalador Python não encontrado: $installer" -ForegroundColor Red
    exit 1
}

python $installer $args
