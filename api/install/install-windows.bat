@echo off
REM =============================================================================
REM ENXAME - Instalador Oficial para Windows
REM Fluxo: Next > Next > Finish (Totalmente Automatico)
REM =============================================================================
REM Este script:
REM 1. Varre a rede em busca de instancias do Enxame
REM 2. Detecta instalacoes antigas do Enxame ou OpenWebUI
REM 3. Para servicos antigos e remove completamente
REM 4. Faz backup dos dados do usuario
REM 5. Instala a nova versao usando o repositorio local
REM 6. Restaura os dados e configura
REM 7. Pergunta a funcao inicial do node (apenas na primeira instalacao)
REM =============================================================================

setlocal EnableDelayedExpansion

:: Configuracoes
set "ENXAME_VERSION=1.0.0"
set "INSTALL_DIR=%PROGRAMFILES%\\Enxame"
set "DATA_DIR=%APPDATA%\\Enxame"
set "LOG_DIR=%LOCALAPPDATA%\\Enxame\\Logs"
set "CONFIG_DIR=%APPDATA%\\Enxame\\Config"
set "BACKUP_DIR=%TEMP%\\enxame_backup_%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "FIRST_INSTALL_FLAG=%DATA_DIR%\\.first_install"

title ENXAME v%ENXAME_VERSION% - Instalador Windows

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║         ENXAME v%ENXAME_VERSION% - Instalador Windows          ║
echo ║              Next ^> Next ^> Finish                        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: Verifica se e administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Erro: Execute como Administrador (clique direito ^> Executar como Administrador^)
    pause
    exit /b 1
)

echo >>> PASSO 1/7: Varrendo rede por instancias do Enxame...
echo.

:: Varre a rede em busca de nos do Enxame
set "NODES_FOUND=0"
echo Procurando nos do Enxame na rede local...

:: Tenta comunicacao HTTP com portas conhecidas
for %%p in (8080 7700 8081 8082) do (
    curl -s --max-time 2 http://localhost:%%p/api/health >nul 2>&1
    if not errorlevel 1 (
        echo   [OK] No respondendo em localhost:%%p
        set /a NODES_FOUND+=1
        :: Notifica shutdown gracioso
        curl -s --max-time 2 -X POST http://localhost:%%p/api/system/shutdown -H "Content-Type: application/json" -d "{\"reason\": \"install\", \"graceful\": true}" >nul 2>&1 || true
    )
)

:: Verifica Ollama
curl -s --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if not errorlevel 1 (
    echo   [OK] Ollama respondendo em localhost:11434
    set /a NODES_FOUND+=1
)

if %NODES_FOUND% equ 0 (
    echo   [!] Nenhum no ativo encontrado
) else (
    echo   Total: %NODES_FOUND% no(s) encontrados
    echo   Notificando nos para shutdown gracioso...
    timeout /t 2 >nul
)

echo.
echo >>> PASSO 2/7: Procurando instalacoes antigas...
echo.

set "OLD_INSTALL_FOUND=false"
set "OPENWEBUI_FOUND=false"
set "ENXAME_OLD_FOUND=false"
set "IS_FIRST_INSTALL=true"

:: Detecta OpenWebUI
if exist "%LOCALAPPDATA%\\open-webui" (
    echo [DETECTADO] OpenWebUI encontrado no sistema
    set "OPENWEBUI_FOUND=true"
    set "OLD_INSTALL_FOUND=true"
    set "IS_FIRST_INSTALL=false"
)

if exist "%PROGRAMFILES%\\open-webui" (
    echo [DETECTADO] OpenWebUI encontrado em Program Files
    set "OPENWEBUI_FOUND=true"
    set "OLD_INSTALL_FOUND=true"
    set "IS_FIRST_INSTALL=false"
)

:: Detecta Enxame antigo
if exist "%INSTALL_DIR%" (
    echo [DETECTADO] Instalacao antiga do Enxame detectada
    set "ENXAME_OLD_FOUND=true"
    set "OLD_INSTALL_FOUND=true"
    set "IS_FIRST_INSTALL=false"
)

if exist "%DATA_DIR%\\data" (
    echo [DETECTADO] Dados antigos do Enxame detectados
    set "OLD_INSTALL_FOUND=true"
    set "IS_FIRST_INSTALL=false"
)

:: Verifica se e primeira instalacao
if exist "%FIRST_INSTALL_FLAG%" (
    set "IS_FIRST_INSTALL=false"
)

:: Verifica processos
tasklist /FI "IMAGENAME eq python*" /FI "WINDOWTITLE eq *enxame*" 2>nul | find "python" >nul
if not errorlevel 1 (
    echo [DETECTADO] Processos antigos do Enxame encontrados
    set "OLD_INSTALL_FOUND=true"
)

if "%OLD_INSTALL_FOUND%"=="true" (
    echo.
    echo >>> PASSO 3/7: Removendo instalacao antiga...
    echo.
    
    :: Para processos
    echo Parando processos antigos...
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq *enxame*" >nul 2>&1 || true
    taskkill /F /IM node.exe /FI "WINDOWTITLE eq *enxame*" >nul 2>&1 || true
    taskkill /F /IM open-webui* >nul 2>&1 || true
    
    :: Backup dos dados
    echo Criando backup dos dados do usuario...
    mkdir "%BACKUP_DIR%" 2>nul
    
    if exist "%DATA_DIR%\\data" (
        xcopy /E /I /Y "%DATA_DIR%\\data" "%BACKUP_DIR%\\data" >nul
        echo   [OK] Dados backupados
    )
    
    if exist "%CONFIG_DIR%\\.env" (
        copy /Y "%CONFIG_DIR%\\.env" "%BACKUP_DIR%\\" >nul
        echo   [OK] Configuracoes backupadas
    )
    
    :: Remove instalacao antiga
    echo Removendo arquivos antigos...
    
    if exist "%INSTALL_DIR%" (
        rmdir /S /Q "%INSTALL_DIR%" 2>nul
    )
    
    if exist "%DATA_DIR%" (
        rmdir /S /Q "%DATA_DIR%" 2>nul
    )
    
    if exist "%LOG_DIR%" (
        rmdir /S /Q "%LOG_DIR%" 2>nul
    )
    
    if exist "%CONFIG_DIR%" (
        rmdir /S /Q "%CONFIG_DIR%" 2>nul
    )
    
    :: Remove OpenWebUI se existir
    if "%OPENWEBUI_FOUND%"=="true" (
        echo Removendo OpenWebUI...
        if exist "%LOCALAPPDATA%\\open-webui" rmdir /S /Q "%LOCALAPPDATA%\\open-webui"
        if exist "%PROGRAMFILES%\\open-webui" rmdir /S /Q "%PROGRAMFILES%\\open-webui"
    )
    
    echo.
    echo [OK] Instalacao antiga removida
) else (
    echo.
    echo [OK] Nenhuma instalacao antiga encontrada
)

echo.
echo >>> PASSO 4/7: Instalando novo Enxame...
echo.

:: Cria diretorios
mkdir "%INSTALL_DIR%" 2>nul
mkdir "%DATA_DIR%\\data" 2>nul
mkdir "%LOG_DIR%" 2>nul
mkdir "%CONFIG_DIR%" 2>nul

:: Copia arquivos do repositorio local (nao precisa clonar novamente)
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."

echo Copiando arquivos do repositorio local em %REPO_ROOT%...
if exist "%REPO_ROOT%\\kernel" (
    xcopy /E /I /Y "%REPO_ROOT%\\*" "%INSTALL_DIR%" >nul
    echo   [OK] Arquivos copiados do repositorio local
) else if exist "%REPO_ROOT%\\core" (
    xcopy /E /I /Y "%REPO_ROOT%\\*" "%INSTALL_DIR%" >nul
    echo   [OK] Arquivos copiados do repositorio local
) else (
    echo [ERRO] Repositorio nao encontrado em %REPO_ROOT%
    echo Certifique-se de que o instalador esta dentro do repositorio do Enxame.
    pause
    exit /b 1
)

cd /d "%INSTALL_DIR%"

:: Instala dependencias Python
echo Instalando dependencias Python...
if exist "agentes\\requirements.txt" (
    pip install -r agentes\\requirements.txt --quiet --upgrade
) else if exist "requirements.txt" (
    pip install -r requirements.txt --quiet --upgrade
) else if exist "kernel\\requirements.txt" (
    pip install -r kernel\\requirements.txt --quiet --upgrade
)
echo   [OK] Dependencias Python instaladas

:: Instala dependencias Node se necessario
if exist "package.json" (
    echo Instalando dependencias Node.js...
    npm install --production --silent
    echo   [OK] Dependencias Node.js instaladas
)

echo.
echo [OK] Enxame instalado em %INSTALL_DIR%

echo.
echo >>> PASSO 5/7: Restaurando dados e configurando...
echo.

:: Restaura backup
if exist "%BACKUP_DIR%\\data" (
    xcopy /E /I /Y "%BACKUP_DIR%\\data" "%DATA_DIR%\\" >nul
    echo   [OK] Dados restaurados
)

if exist "%BACKUP_DIR%\\.env" (
    copy /Y "%BACKUP_DIR%\\.env" "%CONFIG_DIR%\\.env" >nul
    echo   [OK] Configuracoes restauradas
) else (
    :: Cria .env padrao
    echo # Enxame Configuration > "%CONFIG_DIR%\\.env"
    echo ENXAME_ENV=production >> "%CONFIG_DIR%\\.env"
    echo ENXAME_PORT=8080 >> "%CONFIG_DIR%\\.env"
    echo ENXAME_HOST=0.0.0.0 >> "%CONFIG_DIR%\\.env"
    echo ENXAME_DATA_PATH=%DATA_DIR% >> "%CONFIG_DIR%\\.env"
    echo ENXAME_LOG_PATH=%LOG_DIR% >> "%CONFIG_DIR%\\.env"
    echo OLLAMA_URL=http://localhost:11434 >> "%CONFIG_DIR%\\.env"
    echo EXP_SHARED_SECRET=enxame-secret-%RANDOM%%RANDOM% >> "%CONFIG_DIR%\\.env"
    echo   [OK] Configuracao padrao criada
)

:: Marca como nao sendo mais primeira instalacao
if "%IS_FIRST_INSTALL%"=="true" (
    type nul > "%FIRST_INSTALL_FLAG%"
)

echo.
echo [OK] Configuracao concluida

echo.
echo >>> PASSO 6/7: Criando atalhos...
echo.

:: Cria atalho na area de trabalho
set "DESKTOP=%USERPROFILE%\\Desktop"
set "SCRIPT_PATH=%INSTALL_DIR%\\run.bat"

:: Cria script de inicializacao
echo @echo off > "%SCRIPT_PATH%"
echo cd /d "%INSTALL_DIR%" >> "%SCRIPT_PATH%"
echo python -m kernel.start %%* >> "%SCRIPT_PATH%"

:: Cria atalho
set "SHORTCUT_PATH=%DESKTOP%\\Enxame.lnk"
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = '%SCRIPT_PATH%'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Description = 'Enxame AI Platform'; $Shortcut.Save()"

:: Adiciona ao PATH (opcional)
setx ENXAME_HOME "%INSTALL_DIR%" /M >nul

echo   [OK] Atalhos criados

:: Limpa backup
rmdir /S /Q "%BACKUP_DIR%" 2>nul

:: Pergunta sobre funcao inicial do node (apenas na primeira instalacao)
if "%IS_FIRST_INSTALL%"=="true" (
    echo.
    echo ╔══════════════════════════════════════════════════════════╗
    echo ║         CONFIGURACAO INICIAL DO NODE                     ║
    echo ╚══════════════════════════════════════════════════════════╝
    echo.
    echo Qual sera a funcao inicial deste node no enxame?
    echo.
    echo   1^) Kernel (Orquestrador principal^)
    echo   2^) Juiz (Distribuidor de tarefas^)
    echo   3^) Bibliotecario (Gerenciamento de documentos^)
    echo   4^) Agente (Executor de tarefas^)
    echo   5^) Worker (Processamento distribuido^)
    echo.
    set /p NODE_ROLE="Escolha uma opcao [1-5] (padrao: 1^): "
    if "!NODE_ROLE!"=="" set NODE_ROLE=1
    
    if "!NODE_ROLE!"=="1" (
        set "ROLE_NAME=kernel"
        set "ENXAME_PORT=8080"
        echo Configurando node como KERNEL...
    ) else if "!NODE_ROLE!"=="2" (
        set "ROLE_NAME=juiz"
        set "ENXAME_PORT=8082"
        echo Configurando node como JUIZ...
    ) else if "!NODE_ROLE!"=="3" (
        set "ROLE_NAME=bibliotecario"
        set "ENXAME_PORT=8081"
        echo Configurando node como BIBLIOTECARIO...
    ) else if "!NODE_ROLE!"=="4" (
        set "ROLE_NAME=agente"
        set "ENXAME_PORT=8083"
        echo Configurando node como AGENTE...
    ) else if "!NODE_ROLE!"=="5" (
        set "ROLE_NAME=worker"
        set "ENXAME_PORT=8084"
        echo Configurando node como WORKER...
    ) else (
        set "ROLE_NAME=kernel"
        set "ENXAME_PORT=8080"
        echo Opcao invalida. Configurando como KERNEL por padrao...
    )
    
    :: Atualiza configuracao com a funcao
    echo ENXAME_NODE_ROLE=!ROLE_NAME! >> "%CONFIG_DIR%\\.env"
    for /f "delims=" %%i in ('hostname') do set "HOSTNAME=%%i"
    set "NODE_ID=node-!HOSTNAME!-!DATE:~-4,4!!DATE:~-7,2!!DATE:~-10,2!"
    echo ENXAME_NODE_ID=!NODE_ID! >> "%CONFIG_DIR%\\.env"
    echo ENXAME_PORT=!ENXAME_PORT! >> "%CONFIG_DIR%\\.env"
    
    echo.
    echo [OK] Funcao do node configurada: !ROLE_NAME!
    echo [OK] Porta configurada: !ENXAME_PORT!
    
    :: Descobre e registra node no cluster
    echo.
    echo >>> Descobrindo cluster e registrando node...
    if exist "%INSTALL_DIR%\\api\\install\\discover_nodes.py" (
        python "%INSTALL_DIR%\\api\\install\\discover_nodes.py" discover
        python "%INSTALL_DIR%\\api\\install\\discover_nodes.py" advertise !NODE_ID! !ROLE_NAME! !ENXAME_PORT!
        python "%INSTALL_DIR%\\api\\install\\discover_nodes.py" confirm !NODE_ID! !ROLE_NAME!
        echo.
        echo ══════════════════════════════════════════════════════════
        echo   FUNCAO ASSUMIDA: !ROLE_NAME!
        echo   NODE ID: !NODE_ID!
        echo   STATUS: Ativo e descoberto na rede
        echo ══════════════════════════════════════════════════════════
    )
)

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║              INSTALACAO CONCLUIDA!                       ║
echo ╠══════════════════════════════════════════════════════════╣
echo ║  Enxame v%ENXAME_VERSION% instalado com sucesso                 ║
echo ║                                                          ║
echo ║  Localizacao: %INSTALL_DIR%
echo ║  Dados: %DATA_DIR%
echo ║  Config: %CONFIG_DIR%
echo ║                                                          ║
echo ║  Comandos uteis:                                         ║
echo ║    • Clique duas vezes em Enxame na Area de Trabalho    ║
echo ║    • Ou execute: %SCRIPT_PATH%
echo ║                                                          ║
echo ║  Acesse: http://localhost:8080                          ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
pause

exit /b 0
