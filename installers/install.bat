@echo off
:: =============================================================================
:: ENXAME - Instalador Unificado (Windows Batch)
:: Executa instalador Python next-next-finish
:: =============================================================================

chcp 65001 >nul
title Enxame - Instalador Unificado

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set INSTALLER=%SCRIPT_DIR%install.py

if not exist "%INSTALLER%" (
    echo Instalador Python não encontrado: %INSTALLER%
    pause
    exit /b 1
)

python "%INSTALLER%" %*
