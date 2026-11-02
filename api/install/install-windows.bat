@echo off
:: =============================================================================
:: ENXAME - Instalador Windows
:: =============================================================================
:: Fluxo interativo:
::   1. Pergunta a pasta de instalação (padrão: C:\Program Files\Enxame)
::   2. Pergunta se inicia junto ao boot (tarefa agendada)
::   3. Pergunta a função do node
::   4. Instala o código, cria serviço em segundo plano e atalho na área de trabalho
:: =============================================================================

setlocal enabledelayedexpansion

chcp 65001 >nul
title Enxame - Instalador Windows

echo.
echo ============================================================================
echo                    ENXAME - Instalador Windows
echo                        v1.0 - Instalação
echo ============================================================================
echo.

:: Verifica administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [Erro] Execute como Administrador (clique direito > Executar como Administrador).
    pause
    exit /b 1
)

set DEFAULT_INSTALL_DIR=C:\Program Files\Enxame

:: ---------------------------------------------------------------------------
:: PASSO 1: Pasta de instalação
:: ---------------------------------------------------------------------------
echo >>> PASSO 1/6: Pasta de instalação
echo.
set /p INSTALL_DIR="Onde deseja instalar o Enxame? [%DEFAULT_INSTALL_DIR%]: "
if "!INSTALL_DIR!"=="" set INSTALL_DIR=%DEFAULT_INSTALL_DIR%
:: Remove barra final
if "!INSTALL_DIR:~-1!"=="\" set INSTALL_DIR=!INSTALL_DIR:~0,-1!
echo.
echo [OK] Pasta de instalacao: %INSTALL_DIR%
echo.

:: ---------------------------------------------------------------------------
:: PASSO 2: Iniciar junto ao boot
:: ---------------------------------------------------------------------------
echo >>> PASSO 2/6: Iniciar junto ao boot
echo.
echo Deseja que o Enxame inicie automaticamente junto ao boot da maquina?
echo   [s] Sim - inicia sozinho sempre que ligar o computador (recomendado)
echo   [n] Nao - voce iniciara manualmente ou pelo atalho da area de trabalho
set /p START_ON_BOOT="Opcao (s/n) [padrao: s]: "
if "!START_ON_BOOT!"=="" set START_ON_BOOT=s
echo.
if /I "!START_ON_BOOT!"=="s" (
    set ENABLE_BOOT=true
    echo [OK] Iniciar junto ao boot: SIM
) else (
    set ENABLE_BOOT=false
    echo [OK] Iniciar junto ao boot: NAO
)
echo.

:: ---------------------------------------------------------------------------
:: PASSO 3: Funcao do node
:: ---------------------------------------------------------------------------
echo >>> PASSO 3/6: Funcao do node
echo.
echo Qual a funcao inicial deste node?
echo   [1] Juiz         - orquestracao, validacao e auditoria (porta 7700)
echo   [2] Bibliotecario - busca e gestao de conhecimento (porta 7701)
echo   [3] Agente        - worker com todas as especialidades
echo   [4] Automatico    - deixar o Enxame decidir pelo hardware
set /p ROLE_CHOICE="Escolha (1-4) [padrao: 4]: "
if "!ROLE_CHOICE!"=="" set ROLE_CHOICE=4
if "!ROLE_CHOICE!"=="1" set NODE_ROLE=juiz
if "!ROLE_CHOICE!"=="2" set NODE_ROLE=bibliotecario
if "!ROLE_CHOICE!"=="3" set NODE_ROLE=agente
if "!ROLE_CHOICE!"=="4" set NODE_ROLE=auto
echo.
echo [OK] Funcao do node: %NODE_ROLE%
echo.

:: ---------------------------------------------------------------------------
:: PASSO 4: Instalar arquivos
:: ---------------------------------------------------------------------------
echo >>> PASSO 4/6: Instalando arquivos
echo.
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
echo Copiando arquivos do Enxame para %INSTALL_DIR%...
xcopy /E /H /K /O /X "%~dp0..\.." "%INSTALL_DIR%\" /exclude:nul >nul 2>&1 || (
    robocopy "%~dp0..\.." "%INSTALL_DIR%\" /E /XD .git .venv __pycache__ >nul
)
echo [OK] Arquivos copiados

set DATA_DIR=%APPDATA%\Enxame\data
set LOG_DIR=%LOCALAPPDATA%\Enxame\Logs
set CONFIG_DIR=%APPDATA%\Enxame\Config

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
echo [OK] Diretorios criados:
echo        Dados:   %DATA_DIR%
echo        Logs:    %LOG_DIR%
echo        Config:  %CONFIG_DIR%

:: ---------------------------------------------------------------------------
:: PASSO 5: Criar .env
:: ---------------------------------------------------------------------------
echo.
echo >>> PASSO 5/6: Configuracao (.env)
echo.
set ENV_FILE=%CONFIG_DIR%\.env
if exist "%ENV_FILE%" (
    echo [!] Arquivo .env ja existe. Mantendo valores existentes.
) else (
    echo # Configuracao do Enxame > "%ENV_FILE%"
    echo ENXAME_ENV=production >> "%ENV_FILE%"
    echo ENXAME_HOST=0.0.0.0 >> "%ENV_FILE%"
    echo ENXAME_INSTALL_DIR=%INSTALL_DIR% >> "%ENV_FILE%"
    echo ENXAME_DATA_PATH=%DATA_DIR% >> "%ENV_FILE%"
    echo ENXAME_LOG_PATH=%LOG_DIR% >> "%ENV_FILE%"
    echo ENXAME_NODE_ROLE=%NODE_ROLE% >> "%ENV_FILE%"
    echo OLLAMA_URL=http://localhost:11434 >> "%ENV_FILE%"
    echo [OK] Arquivo .env criado em %ENV_FILE%
)

set DB_PATH=%DATA_DIR%\enxame.db
if not exist "%DB_PATH%" (
    type nul > "%DB_PATH%"
    echo [OK] Banco de dados inicial criado em %DB_PATH%
)

:: ---------------------------------------------------------------------------
:: PASSO 6: Servico (segundo plano) e atalho da area de trabalho
:: ---------------------------------------------------------------------------
echo.
echo >>> PASSO 6/6: Servico em segundo plano e atalho
echo.

set SERVICE_NAME=Enxame
set PORT=7700
if /I "!NODE_ROLE!"=="bibliotecario" set PORT=7701

:: Criar tarefa agendada para iniciar junto ao boot (se escolhido)
if /I "!ENABLE_BOOT!"=="true" (
    echo Criando tarefa agendada para iniciar junto ao boot...
    schtasks /Create /TN "Enxame" /TR "\"%INSTALL_DIR%\api\install\run_node.py\" --env-file %ENV_FILE%" /SC ONSTART /RL HIGHEST /F >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] Tarefa agendada criada (inicia junto ao boot).
    ) else (
        echo [!] Nao foi possivel criar tarefa agendada. Voce podera iniciar pelo atalho.
    )
)

:: Iniciar o servico em segundo plano agora
echo Iniciando o Enxame em segundo plano...
start /B "" python "%INSTALL_DIR%\api\install\run_node.py" --env-file %ENV_FILE%

:: Atalho na area de trabalho
set DESKTOP=%USERPROFILE%\Desktop
if not exist "%DESKTOP%" mkdir "%DESKTOP%"
set SHORTCUT=%DESKTOP%\Enxame.lnk

echo Criando atalho na area de trabalho...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT%'); $Shortcut.TargetPath = '%INSTALL_DIR%\api\install\enxame-desktop.bat'; $Shortcut.Arguments = '%INSTALL_DIR% %ENV_FILE%'; $Shortcut.Description = 'Reiniciar servico e abrir o Enxame no navegador'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Save()"

echo [OK] Atalho criado: %SHORTCUT%

:: Script wrapper do atalho (Windows)
echo @echo off > "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo setlocal enabledelayedexpansion >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo set INSTALL_DIR=%~1 >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo set ENV_FILE=%~2 >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo if "!INSTALL_DIR!"=="" set INSTALL_DIR=C:\Program Files\Enxame >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo if "!ENV_FILE!"=="" set ENV_FILE=%APPDATA%\Enxame\Config\.env >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo set PORT=8765 >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo set URL=http://localhost:!PORT!/ >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo echo Verificando se o Enxame esta em segundo plano... >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo tasklist /FI "IMAGENAME eq python.exe" | findstr /i "python" >nul || ( >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo     echo Iniciando o Enxame em segundo plano... >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo     start /B "" python "!INSTALL_DIR!\run_enxame.py" --no-browser >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo     timeout /t 5 /nobreak >nul >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo ) >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo echo Abrindo o navegador em !URL! >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo start "" "!URL!" >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"
echo exit /b 0 >> "%INSTALL_DIR%\api\install\enxame-desktop.bat"

echo.
echo ============================================================================
echo                    INSTALACAO CONCLUIDA COM SUCESSO!
echo ============================================================================
echo.
echo Resumo da instalacao:
echo   . Pasta de instalacao: %INSTALL_DIR%
echo   . Dados:               %DATA_DIR%
echo   . Config:              %ENV_FILE%
echo   . Logs:                %LOG_DIR%
echo   . Funcao do node:      %NODE_ROLE%
echo   . Iniciar junto ao boot: !ENABLE_BOOT!
echo   . Servico em segundo plano: ativo
echo.
echo Como usar:
echo   . Duplo-clique no atalho 'Enxame' na area de trabalho para
echo     iniciar/reiniciar o servico e abrir o navegador.
echo   . Acesse tambem em: http://localhost:8765/ (Web UI)
echo.
echo Para desinstalar:
echo   execute como Administrador: uninstall.bat
echo.
pause
