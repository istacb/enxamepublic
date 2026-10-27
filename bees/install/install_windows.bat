@echo off
REM ============================================================
REM Instalador Enxame - Windows (next-next-finish)
REM ============================================================
setlocal enabledelayedexpansion

title Instalador Enxame
echo.
echo ============================================================
echo   Instalador Enxame - IA de enxame para maquinas antigas
echo ============================================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python nao encontrado.
    echo     Instale o Python em https://www.python.org/downloads/
    echo     e marque "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)
echo [OK] Python encontrado.

REM Diretorio de instalacao
set "ENXAME_DIR=%USERPROFILE%\enxame"
if not exist "%ENXAME_DIR%" mkdir "%ENXAME_DIR%"
echo [OK] Diretorio: %ENXAME_DIR%

REM Instalar dependencias
echo.
echo [.] Instalando dependencias (pip)... isso pode demorar.
pip install -r requirements.txt
if errorlevel 1 (
    echo [!] Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

REM Perguntar papel do no
echo.
echo Escolha o papel deste computador:
echo   1) Juiz (coordenador - fica ligado, distribui trabalho)
echo   2) Agente (trabalhador - ajuda o Juiz nas tarefas)
set /p ROLE="Digite 1 ou 2 [2]: "
if "!ROLE!"=="1" set ROLE=juiz
if "!ROLE!"=="" set ROLE=agente
if "!ROLE!"=="2" set ROLE=agente

REM Criar node.toml (politica de doacao)
echo.
echo [.] Criando configuracao de doacao...
echo [donation] > "%ENXAME_DIR%\node.toml"
echo enabled = true >> "%ENXAME_DIR%\node.toml"
echo max_cpu_pct = 70 >> "%ENXAME_DIR%\node.toml"
echo min_free_ram_gb = 1.5 >> "%ENXAME_DIR%\node.toml"
echo max_concurrent = 1 >> "%ENXAME_DIR%\node.toml"
echo run_when = "idle" >> "%ENXAME_DIR%\node.toml"
echo pause_on_battery = true >> "%ENXAME_DIR%\node.toml"
echo [OK] Configuracao criada.

REM Criar atalhos de inicio
echo.
echo [.] Criando atalhos...
echo @echo off > "%ENXAME_DIR%\iniciar_juiz.bat"
echo set ENXAME_ROOT=%~dp0..\.. >> "%ENXAME_DIR%\iniciar_juiz.bat"
echo set NODE_ID=juiz-01 >> "%ENXAME_DIR%\iniciar_juiz.bat"
echo set JUIZ_URL=ws://localhost:7700/exp >> "%ENXAME_DIR%\iniciar_juiz.bat"
echo set JUIZ_HTTP_URL=http://localhost:7700 >> "%ENXAME_DIR%\iniciar_juiz.bat"
echo python -m juiz >> "%ENXAME_DIR%\iniciar_juiz.bat"

echo @echo off > "%ENXAME_DIR%\iniciar_agente.bat"
echo set ENXAME_ROOT=%~dp0..\.. >> "%ENXAME_DIR%\iniciar_agente.bat"
echo set NODE_ID=ag-%COMPUTERNAME% >> "%ENXAME_DIR%\iniciar_agente.bat"
echo set JUIZ_URL=ws://localhost:7700/exp >> "%ENXAME_DIR%\iniciar_agente.bat"
echo set JUIZ_HTTP_URL=http://localhost:7700 >> "%ENXAME_DIR%\iniciar_agente.bat"
echo python -m agentes >> "%ENXAME_DIR%\iniciar_agente.bat"
echo [OK] Atalhos criados.

echo.
echo ============================================================
echo   Instalacao concluida!
echo ============================================================
echo.
echo Para iniciar o Juiz: duplo clique em iniciar_juiz.bat
echo Para iniciar um Agente: duplo clique em iniciar_agente.bat
echo Acesse a UI em: http://localhost:7700
echo.
pause
