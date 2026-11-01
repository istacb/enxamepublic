@echo off
REM ENXAME Launcher para Windows
REM =============================
REM Duplo clique neste arquivo para iniciar o Enxame e abrir o navegador

chcp 65001 >nul
title ENXAME - Iniciando...

echo.
echo  ========================================
echo   ENXAME - Inicializando...
echo  ========================================
echo.

REM Verifica se Python está disponível
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python não encontrado no PATH
    echo    Instale Python em https://python.org
    echo.
    pause
    exit /b 1
)

REM Verifica se está no diretório correto
if not exist "run_enxame.py" (
    echo ❌ Arquivo run_enxame.py não encontrado
    echo    Execute este arquivo a partir da pasta raiz do Enxame
    echo.
    pause
    exit /b 1
)

REM Inicia o Enxame
echo 🚀 Iniciando Enxame Kernel...
echo.

python run_enxame.py %*

echo.
echo  ========================================
echo   Enxame finalizado
echo  ========================================
echo.
pause