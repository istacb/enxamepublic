@echo off
REM =============================================================================
REM ENXAME - Instalador Oficial para Windows
REM Fluxo: Next > Next > Finish (Totalmente Automático)
REM =============================================================================
REM Este script:
REM 1. Detecta instalações antigas do Enxame ou OpenWebUI
REM 2. Para serviços antigos
REM 3. Faz backup dos dados do usuário
REM 4. Remove completamente a instalação antiga
REM 5. Instala a nova versão limpa
REM 6. Restaura os dados
REM =============================================================================

setlocal EnableDelayedExpansion

:: Configurações
set "ENXAME_VERSION=1.0.0"
set "INSTALL_DIR=%PROGRAMFILES%\Enxame"
set "DATA_DIR=%APPDATA%\Enxame"
set "LOG_DIR=%LOCALAPPDATA%\Enxame\Logs"
set "CONFIG_DIR=%APPDATA%\Enxame\Config"
set "BACKUP_DIR=%TEMP%\enxame_backup_%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"

:: Cores (requer Windows 10+)
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do (
  set "DEL=%%a"
  set "ESC=%%b"
)

title ENXAME v%ENXAME_VERSION% - Instalador Windows

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║         ENXAME v%ENXAME_VERSION% - Instalador Windows          ║
echo ║              Next ^> Next ^> Finish                        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: Verifica se é administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Erro: Execute como Administrador (clique direito ^> Executar como Administrador^)
    pause
    exit /b 1
)

echo >>> PASSO 1/7: Verificando requisitos do sistema...
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado. Por favor, instale Python 3.8+ primeiro.
    echo Baixe em: https://www.python.org/downloads/
    pause
    exit /b 1
) else (
    python --version
)

:: Verifica Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo Node.js nao encontrado. Instalando...
    winget install OpenJS.NodeJS.LTS --silent
    if errorlevel 1 (
        echo Falha ao instalar Node.js automaticamente. Instale manualmente.
        pause
    )
) else (
    node --version
)

echo.
echo [OK] Requisitos verificados
echo.

echo >>> PASSO 2/7: Procurando instalacoes antigas...
echo.

set "OLD_INSTALL_FOUND=false"
set "OPENWEBUI_FOUND=false"
set "ENXAME_OLD_FOUND=false"

:: Detecta OpenWebUI
if exist "%LOCALAPPDATA%\open-webui" (
    echo [DETECTADO] OpenWebUI encontrado no sistema
    set "OPENWEBUI_FOUND=true"
    set "OLD_INSTALL_FOUND=true"
)

if exist "%PROGRAMFILES%\open-webui" (
    echo [DETECTADO] OpenWebUI encontrado em Program Files
    set "OPENWEBUI_FOUND=true"
    set "OLD_INSTALL_FOUND=true"
)

:: Detecta Enxame antigo
if exist "%INSTALL_DIR%" (
    echo [DETECTADO] Instalacao antiga do Enxame detectada
    set "ENXAME_OLD_FOUND=true"
    set "OLD_INSTALL_FOUND=true"
)

if exist "%DATA_DIR%\data" (
    echo [DETECTADO] Dados antigos do Enxame detectados
    set "OLD_INSTALL_FOUND=true"
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
    
    if exist "%DATA_DIR%\data" (
        xcopy /E /I /Y "%DATA_DIR%\data" "%BACKUP_DIR%\data" >nul
        echo   [OK] Dados backupados
    )
    
    if exist "%CONFIG_DIR%\.env" (
        copy /Y "%CONFIG_DIR%\.env" "%BACKUP_DIR%\" >nul
        echo   [OK] Configuracoes backupadas
    )
    
    :: Remove instalação antiga
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
        if exist "%LOCALAPPDATA%\open-webui" rmdir /S /Q "%LOCALAPPDATA%\open-webui"
        if exist "%PROGRAMFILES%\open-webui" rmdir /S /Q "%PROGRAMFILES%\open-webui"
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

:: Cria diretórios
mkdir "%INSTALL_DIR%" 2>nul
mkdir "%DATA_DIR%\data" 2>nul
mkdir "%LOG_DIR%" 2>nul
mkdir "%CONFIG_DIR%" 2>nul

:: Copia arquivos. O instalador é distribuído junto com o repositório
:: (fica em api\install\ dentro do proprio checkout), entao nunca e
:: necessario clonar nada aqui: subimos duas pastas (api\install -> raiz
:: do repo) e copiamos o repositorio inteiro, nao so a pasta do instalador.
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"

if not exist "%REPO_ROOT%\juiz" (
    echo Erro: nao encontrei o repositorio do Enxame a partir de %SCRIPT_DIR%.
    echo Execute este script de dentro do checkout do repositorio ^(api\install\install-windows.bat^).
    pause
    exit /b 1
)
if not exist "%REPO_ROOT%\bibliotecario" (
    echo Erro: nao encontrei o repositorio do Enxame a partir de %SCRIPT_DIR%.
    echo Execute este script de dentro do checkout do repositorio ^(api\install\install-windows.bat^).
    pause
    exit /b 1
)

echo Copiando arquivos do Enxame de %REPO_ROOT%...
xcopy /E /I /Y "%REPO_ROOT%\*" "%INSTALL_DIR%" >nul
echo   [OK] Arquivos copiados

cd /d "%INSTALL_DIR%"

:: Instala dependências Python (usando --user para evitar PEP 668 no Python 3.12+)
echo Instalando dependências Python...
if exist "requirements.txt" (
    pip install --user -r requirements.txt --quiet --upgrade
) else if exist "kernel\requirements.txt" (
    pip install --user -r kernel\requirements.txt --quiet --upgrade
)
echo   [OK] Dependencias Python instaladas

:: Instala dependências Node se necessário
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
if exist "%BACKUP_DIR%\data" (
    xcopy /E /I /Y "%BACKUP_DIR%\data" "%DATA_DIR%\" >nul
    echo   [OK] Dados restaurados
)

if exist "%BACKUP_DIR%\.env" (
    copy /Y "%BACKUP_DIR%\.env" "%CONFIG_DIR%\.env" >nul
    echo   [OK] Configuracoes restauradas
) else (
    :: Cria .env padrão
    echo # Enxame Configuration > "%CONFIG_DIR%\.env"
    echo ENXAME_ENV=production >> "%CONFIG_DIR%\.env"
    echo ENXAME_HOST=0.0.0.0 >> "%CONFIG_DIR%\.env"
    echo ENXAME_DATA_PATH=%DATA_DIR% >> "%CONFIG_DIR%\.env"
    echo ENXAME_LOG_PATH=%LOG_DIR% >> "%CONFIG_DIR%\.env"
    echo OLLAMA_URL=http://localhost:11434 >> "%CONFIG_DIR%\.env"
    echo   [OK] Configuracao padrao criada
)

echo.
echo [OK] Configuracao concluida

echo.
echo >>> PASSO 6/7: Criando atalhos...
echo.

:: Cria atalho na área de trabalho
set "DESKTOP=%USERPROFILE%\Desktop"
set "SCRIPT_PATH=%INSTALL_DIR%\run.bat"

:: Cria script de inicialização
echo @echo off > "%SCRIPT_PATH%"
echo cd /d "%INSTALL_DIR%" >> "%SCRIPT_PATH%"
echo python "%INSTALL_DIR%\api\install\run_node.py" --env-file "%CONFIG_DIR%\.env" %%* >> "%SCRIPT_PATH%"

:: Cria atalho
set "SHORTCUT_PATH=%DESKTOP%\Enxame.lnk"
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = '%SCRIPT_PATH%'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Description = 'Enxame AI Platform'; $Shortcut.Save()"

:: Adiciona ao PATH (opcional)
setx ENXAME_HOME "%INSTALL_DIR%" /M >nul

:: Limpa backup
rmdir /S /Q "%BACKUP_DIR%" 2>nul

echo   [OK] Atalhos criados

echo.
echo >>> PASSO 7/7: Configurando funcao do node...
echo.

:: Pergunta a funcao inicial do node (so pergunta de fato se o .env
:: restaurado ainda nao tiver uma funcao salva de uma instalacao anterior),
:: faz a varredura mDNS por outros nodes na rede e, na primeira instalacao,
:: exibe a confirmacao de qual funcao cada node assumiu.
python "%INSTALL_DIR%\api\install\node_role_setup.py" --env-file "%CONFIG_DIR%\.env"

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
echo ║  Funcao e porta deste node: ver %CONFIG_DIR%\.env
echo ╚══════════════════════════════════════════════════════════╝
echo.
pause

exit /b 0
