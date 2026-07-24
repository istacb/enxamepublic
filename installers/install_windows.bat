@echo off
REM =============================================================================
REM ENXAME v5 - Instalador Automático para Windows
REM Instalação "Next > Next > Finish" - sem perguntas ao usuário
REM Componentes: Juiz, Bibliotecário, Workers, Consultor, OpenWebUI com Frontend Enxame
REM =============================================================================

setlocal EnableDelayedExpansion

echo ============================================================
echo   ENXAME v5 - Instalador Automatico (Windows)
echo   Sistema de comunicacao descentralizada com IA
echo ============================================================
echo.

REM Verificar se está executando como administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERRO] Por favor, execute como Administrador (clique direito ^> Executar como administrador^)
    pause
    exit /b 1
)

REM Configurar diretórios
set ENXAME_DIR=C:\ProgramData\ENXAME
set USER_ENXAME_DIR=%USERPROFILE%\.enxame
set OPENWEBUI_DIR=%ENXAME_DIR\openwebui
set PYTHON_EXE=

echo [INFO] Instalando ENXAME v5 em %ENXAME_DIR%...
echo.

REM 1. Verificar Python instalado
echo [INFO] Verificando Python...
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [AVISO] Python nao encontrado. Baixando instalador...
    curl -L https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -o %TEMP%\python_installer.exe
    
    echo [INFO] Instalando Python silenciosamente...
    %TEMP%\python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del %TEMP%\python_installer.exe
    
    REM Aguardar registro do Python no PATH
    timeout /t 5 /nobreak >nul
)

REM Recarregar PATH
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path') do set "PATH=%%b"

REM 2. Instalar Node.js (necessário para build do frontend)
echo [INFO] Verificando Node.js...
where node >nul 2>&1
if %errorLevel% neq 0 (
    echo [AVISO] Node.js nao encontrado. Baixando instalador...
    curl -L https://nodejs.org/dist/v20.11.0/node-v20.11.0-x64.msi -o %TEMP%\node_installer.msi
    
    echo [INFO] Instalando Node.js silenciosamente...
    msiexec /i %TEMP%\node_installer.msi /quiet /norestart
    del %TEMP%\node_installer.msi
    
    REM Aguardar instalação
    timeout /t 10 /nobreak >nul
) else (
    echo [INFO] Node.js ja esta instalado.
)

REM Recarregar PATH novamente
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path') do set "PATH=%%b"

REM 3. Criar diretórios
echo [INFO] Criando estrutura de diretorios...
mkdir "%ENXAME_DIR%" 2>nul
mkdir "%USER_ENXAME_DIR%\logs" 2>nul
mkdir "%USER_ENXAME_DIR%\memory" 2>nul
mkdir "%USER_ENXAME_DIR%\guardian" 2>nul
mkdir "%USER_ENXAME_DIR%\failover" 2>nul
mkdir "%USER_ENXAME_DIR%\data\kb_contabil" 2>nul
mkdir "%USER_ENXAME_DIR%\data\kb_engenharia" 2>nul
mkdir "%USER_ENXAME_DIR%\data\kb_rh_trabalhista" 2>nul
mkdir "%USER_ENXAME_DIR%\data\kb_vendas" 2>nul
mkdir "%USER_ENXAME_DIR%\data\kb_seguranca" 2>nul
mkdir "%USER_ENXAME_DIR%\perfis" 2>nul
mkdir "%ENXAME_DIR%\juiz" 2>nul
mkdir "%ENXAME_DIR%\bibliotecario" 2>nul
mkdir "%ENXAME_DIR%\consultor" 2>nul
mkdir "%ENXAME_DIR%\workers" 2>nul
mkdir "%OPENWEBUI_DIR%" 2>nul
mkdir "%OPENWEBUI_DIR%\src" 2>nul
mkdir "%OPENWEBUI_DIR%\static" 2>nul

REM 3. Instalar Ollama para Windows (antes das dependências)
echo [INFO] Verificando Ollama...
where ollama >nul 2>&1
if %errorLevel% neq 0 (
    echo [AVISO] Ollama nao encontrado. Instalando...
    curl -L https://ollama.com/download/OllamaSetup.exe -o %TEMP%\OllamaSetup.exe
    %TEMP%\OllamaSetup.exe /SILENT
    del %TEMP%\OllamaSetup.exe
    
    REM Aguardar instalação
    timeout /t 10 /nobreak >nul
    
    REM Adicionar Ollama ao PATH
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Ollama"
) else (
    echo [INFO] Ollama ja esta instalado.
)

REM 4. Instalar modelos de IA (apenas se necessário)
echo [INFO] Verificando modelos de IA instalados...
set HAS_MODELS=0
for /f "tokens=*" %%i in ('ollama list 2^>nul ^| findstr /v "^NAME"') do (
    set HAS_MODELS=1
)

if %HAS_MODELS%==0 (
    echo [AVISO] Nenhum modelo encontrado. Instalando modelos minimos recomendados...
    
    REM Instalar apenas modelos >= 1.5B
    echo [INFO] Baixando qwen2.5:1.5b (minimo 1.5B parametros)...
    ollama pull qwen2.5:1.5b
    
    echo [INFO] Baixando nomic-embed-text (modelo de embedding)...
    ollama pull nomic-embed-text
    
    echo [INFO] Modelos basicos instalados. Usuario pode adicionar mais modelos manualmente.
) else (
    echo [INFO] Modelos ja estao instalados. Nenhum modelo sera modificado.
)

REM 5. Criar ambiente virtual Python
echo [INFO] Criando ambiente virtual Python...
python -m venv "%ENXAME_DIR%\venv"
call "%ENXAME_DIR%\venv\Scripts\activate.bat"

REM 6. Instalar dependências Python
echo [INFO] Instalando dependencias Python...
python -m pip install --upgrade pip -q
pip install fastapi uvicorn pydantic httpx websockets zeroconf typer rich numpy requests docker -q

REM 7. Copiar arquivos do projeto
echo [INFO] Copiando arquivos do projeto...
cd /d "%~dp0"

REM Copiar backend Python
xcopy /E /I /Y core "%ENXAME_DIR%\core" >nul 2>&1
xcopy /E /I /Y bibliotecario "%ENXAME_DIR%\bibliotecario" >nul 2>&1
xcopy /E /I /Y juiz "%ENXAME_DIR%\juiz" >nul 2>&1
xcopy /E /I /Y consultor "%ENXAME_DIR%\consultor" >nul 2>&1
xcopy /E /I /Y workers "%ENXAME_DIR%\workers" >nul 2>&1
xcopy /E /I /Y guardian "%ENXAME_DIR%\guardian" >nul 2>&1
xcopy /E /I /Y perfis "%ENXAME_DIR%\perfis" >nul 2>&1
xcopy /Y requirements.txt "%ENXAME_DIR%\" >nul 2>&1

REM Copiar frontend SvelteKit (OpenWebUI + Enxame)
echo [INFO] Copiando frontend SvelteKit (OpenWebUI + Enxame)...
xcopy /E /I /Y src "%OPENWEBUI_DIR%\src" >nul 2>&1
xcopy /Y package.json "%OPENWEBUI_DIR%\" >nul 2>&1
xcopy /Y package-lock.json "%OPENWEBUI_DIR%\" >nul 2>&1
xcopy /Y svelte.config.js "%OPENWEBUI_DIR%\" >nul 2>&1
xcopy /Y vite.config.ts "%OPENWEBUI_DIR%\" >nul 2>&1
xcopy /Y tsconfig.json "%OPENWEBUI_DIR%\" >nul 2>&1
xcopy /Y .npmrc "%OPENWEBUI_DIR%\" >nul 2>&1
xcopy /E /I /Y static "%OPENWEBUI_DIR%\static" >nul 2>&1

REM Copiar perfis para diretório do usuário
xcopy /E /I /Y perfis\*.json "%USER_ENXAME_DIR%\perfis\" >nul 2>&1

REM 8. Criar arquivo de configuração
echo [INFO] Criando arquivo de configuracao...
(
    echo # Configuracao ENXAME v5
    echo NODE_ID=%COMPUTERNAME%
    echo IP_JUIZ=localhost
    echo JUIZ_PORTA=7700
    echo BIBLIOTECARIO_PORTA=7710
    echo GUARDIAN_PORTA=7720
    echo OLLAMA_URL=http://localhost:11434
    echo OPENWEBUI_URL=http://localhost:8080
    echo ENXAME_DIR=%USER_ENXAME_DIR%
    echo DEFAULT_MODEL=qwen2.5:1.5b
) > "%USER_ENXAME_DIR%\.env"

REM 9. Instalar dependências Node.js e build do frontend
echo [INFO] Instalando dependencias Node.js e build do frontend...
cd /d "%OPENWEBUI_DIR%"

REM Instalar dependências npm
call npm install --legacy-peer-deps 2>nul || call npm install 2>nul || echo [AVISO] Erro ao instalar dependencias npm

REM Build do frontend
echo [INFO] Compilando frontend SvelteKit...
call npm run build 2>nul || echo [AVISO] Erro ao compilar frontend

cd /d "%ENXAME_DIR%"

REM 10. Criar scripts de inicialização
echo [INFO] Criando scripts de inicializacao...

REM Script batch para iniciar Juiz
(
    echo @echo off
    echo cd /d "%ENXAME_DIR%"
    echo call venv\Scripts\activate.bat
    echo python juiz\juiz.py
) > "%ENXAME_DIR%\start_juiz.bat"

REM Script batch para iniciar Guardian
(
    echo @echo off
    echo cd /d "%ENXAME_DIR%"
    echo call venv\Scripts\activate.bat
    echo python guardian\guardian.py
) > "%ENXAME_DIR%\start_guardian.bat"

REM Script batch para iniciar OpenWebUI (com frontend Enxame)
(
    echo @echo off
    echo cd /d "%OPENWEBUI_DIR%"
    echo call ..\venv\Scripts\activate.bat
    echo python -m uvicorn backend.open_webui.main:app --host 0.0.0.0 --port 8080
) > "%ENXAME_DIR%\start_openwebui.bat"

REM Script batch para iniciar Worker (exemplo genérico)
(
    echo @echo off
    echo cd /d "%ENXAME_DIR%"
    echo call venv\Scripts\activate.bat
    echo python workers\worker.py --role generic --pool-size 4
) > "%ENXAME_DIR%\start_worker.bat"

REM Script batch para iniciar todos os serviços
(
    echo @echo off
    echo echo ============================================================
    echo echo   INICIANDO ENXAME v5...
    echo echo ============================================================
    echo echo.
    echo echo [INFO] Iniciando Juiz (porta 7700^)...
    echo start "ENXAME Juiz" cmd /k "%ENXAME_DIR%\start_juiz.bat"
    echo timeout /t 3 /nobreak ^>nul
    echo.
    echo echo [INFO] Iniciando Guardian (porta 7720^)...
    echo start "ENXAME Guardian" cmd /k "%ENXAME_DIR%\start_guardian.bat"
    echo timeout /t 3 /nobreak ^>nul
    echo.
    echo echo [INFO] Iniciando OpenWebUI com Enxame (porta 8080^)...
    echo start "ENXAME OpenWebUI" cmd /k "%ENXAME_DIR%\start_openwebui.bat"
    echo timeout /t 5 /nobreak ^>nul
    echo.
    echo echo ============================================================
    echo echo   ENXAME iniciado com sucesso!
    echo echo ============================================================
    echo echo.
    echo echo [OK] Acesse o Juiz: http://localhost:7700
    echo echo [OK] Acesse o Guardian: http://localhost:7720
    echo echo [OK] Acesse o OpenWebUI + Enxame: http://localhost:8080
    echo echo [OK] Acesse o Mission Control: http://localhost:8080/enxame
    echo echo.
    echo echo Para adicionar workers, execute:
    echo echo   %ENXAME_DIR%\start_worker.bat
    echo echo.
    echo echo Pressione qualquer tecla para fechar esta janela...
    echo pause ^>nul
) > "%ENXAME_DIR%\start_all.bat"

REM 11. Criar atalho na área de trabalho
echo [INFO] Criando atalho na area de trabalho...
set SCRIPT_PATH="%USERPROFILE%\Desktop\Iniciar ENXAME.lnk"
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SCRIPT_PATH%'); $Shortcut.TargetPath = '%ENXAME_DIR%\start_all.bat'; $Shortcut.WorkingDirectory = '%ENXAME_DIR%'; $Shortcut.Description = 'Iniciar ENXAME v5 - Juiz, Guardian, OpenWebUI com Enxame'; $Shortcut.Save()"

REM 12. Configurar firewall do Windows
echo [INFO] Configurando regras de firewall...
netsh advfirewall firewall add rule name="ENXAME Juiz" dir=in action=allow protocol=TCP localport=7700 >nul 2>&1
netsh advfirewall firewall add rule name="ENXAME Guardian" dir=in action=allow protocol=TCP localport=7720 >nul 2>&1
netsh advfirewall firewall add rule name="ENXAME OpenWebUI" dir=in action=allow protocol=TCP localport=8080 >nul 2>&1
netsh advfirewall firewall add rule name="ENXAME Workers" dir=in action=allow protocol=TCP localport=9000-9999 >nul 2>&1
netsh advfirewall firewall add rule name="Ollama" dir=in action=allow protocol=TCP localport=11434 >nul 2>&1

REM 13. Mostrar informações finais
echo.
echo ============================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo ============================================================
echo.
echo [OK] ENXAME v5 foi instalado em: %ENXAME_DIR%
echo [OK] Diretorio do usuario: %USER_ENXAME_DIR%
echo [OK] Frontend OpenWebUI: %OPENWEBUI_DIR%
echo.
echo [OK] Atalho criado na Area de Trabalho
echo.
echo [OK] Componentes instalados:
echo      - Juiz (porta 7700^)
echo      - Guardian (porta 7720^)
echo      - OpenWebUI com Enxame (porta 8080^)
echo      - Workers (portas 9000-9999^)
echo      - Ollama (porta 11434^)
echo.
echo [OK] Modelos de IA instalados (minimo 1.5B^):
echo      - qwen2.5:1.5b
echo      - nomic-embed-text
echo.
echo [OK] Para iniciar o ENXAME:
echo      - Clique duas vezes em "Iniciar ENXAME.lnk" na Area de Trabalho
echo      - Ou execute: %ENXAME_DIR%\start_all.bat
echo.
echo [OK] Acesse os paineis web:
echo      - Juiz: http://localhost:7700
echo      - Guardian: http://localhost:7720
echo      - OpenWebUI + Enxame: http://localhost:8080
echo      - Mission Control: http://localhost:8080/enxame
echo.
echo [OK] Para recompilar o frontend apos alteracoes:
echo      - Execute: cd %OPENWEBUI_DIR% ^&^& npm run build
echo.
echo [OK] Documentacao: https://github.com/istacb/enxamepublic
echo.
echo ============================================================
echo.
set /p INICIAR="Deseja iniciar o ENXAME agora? (S/N): "
if /i "!INICIAR!"=="S" (
    start "" "%ENXAME_DIR%\start_all.bat"
)

pause
