@echo off
REM =============================================================================
REM ENXAME v3 - Instalador Automático para Windows
REM Instalação "Next > Next > Finish" - sem perguntas ao usuário
REM =============================================================================

setlocal EnableDelayedExpansion

echo ============================================================
echo   ENXAME v3 - Instalador Automatico (Windows)
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
set PYTHON_EXE=

echo [INFO] Instalando ENXAME v3 em %ENXAME_DIR%...
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

REM 2. Criar diretórios
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

REM 3. Copiar arquivos do projeto (assumindo que estão no mesmo diretório do instalador)
echo [INFO] Copiando arquivos do projeto...
cd /d "%~dp0"
xcopy /E /I /Y *.py "%ENXAME_DIR%\" >nul 2>&1
xcopy /E /I /Y core "%ENXAME_DIR\core" >nul 2>&1
xcopy /E /I /Y bibliotecario "%ENXAME_DIR\bibliotecario" >nul 2>&1
xcopy /E /I /Y agentes "%ENXAME_DIR\agentes" >nul 2>&1
xcopy /E /I /Y juiz "%ENXAME_DIR\juiz" >nul 2>&1
xcopy /E /I /Y guardian "%ENXAME_DIR\guardian" >nul 2>&1
xcopy /E /I /Y perfis "%ENXAME_DIR\perfis" >nul 2>&1
xcopy /E /I /Y scripts "%ENXAME_DIR\scripts" >nul 2>&1
xcopy /Y requirements.txt "%ENXAME_DIR\" >nul 2>&1

REM Copiar perfis para diretório do usuário
xcopy /E /I /Y perfis\*.json "%USER_ENXAME_DIR%\perfis\" >nul 2>&1

REM 4. Criar ambiente virtual Python
echo [INFO] Criando ambiente virtual Python...
python -m venv "%ENXAME_DIR%\venv"
call "%ENXAME_DIR%\venv\Scripts\activate.bat"

REM 5. Instalar dependências Python
echo [INFO] Instalando dependencias Python...
python -m pip install --upgrade pip -q
pip install fastapi uvicorn pydantic httpx websockets zeroconf typer rich numpy -q

REM 6. Instalar Ollama para Windows
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
<<<<<<< HEAD
=======
    
    REM Pull de modelos básicos
    echo [INFO] Baixando modelos de IA recomendados...
    ollama pull qwen2.5:1.5b
    ollama pull nomic-embed-text
>>>>>>> 4f05cd4d444bc816d363af4224210cd8f5a018c7
) else (
    echo [INFO] Ollama ja esta instalado.
)

<<<<<<< HEAD
REM 7. Verificar e instalar modelos mínimos (apenas se necessário)
echo [INFO] Verificando modelos de IA instalados...

REM Verificar se já existem modelos instalados
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
    echo [INFO] Para adicionar modelos adicionais, execute: ollama pull ^<nome-do-modelo^>
    echo [INFO] Nota: Apenas modelos com ^>= 1.5B parametros sao recomendados para producao.
)

=======
>>>>>>> 4f05cd4d444bc816d363af4224210cd8f5a018c7
REM 7. Criar arquivo de configuração
echo [INFO] Criando arquivo de configuracao...
(
    echo # Configuracao ENXAME v3
    echo NODE_ID=%COMPUTERNAME%
    echo IP_JUIZ=localhost
    echo JUIZ_PORTA=7700
    echo BIBLIOTECARIO_PORTA=7710
    echo GUARDIAN_PORTA=7720
    echo OLLAMA_URL=http://localhost:11434
    echo ENXAME_DIR=%USER_ENXAME_DIR%
) > "%USER_ENXAME_DIR%\.env"

REM 8. Criar scripts de inicialização
echo [INFO] Criando scripts de inicializacao...

REM Script batch para iniciar Juiz
(
    echo @echo off
    echo cd /d "%ENXAME_DIR%"
    echo call venv\Scripts\activate.bat
    echo python juiz.py
) > "%ENXAME_DIR%\start_juiz.bat"

REM Script batch para iniciar Guardian
(
    echo @echo off
    echo cd /d "%ENXAME_DIR%"
    echo call venv\Scripts\activate.bat
    echo python guardian\guardian.py
) > "%ENXAME_DIR%\start_guardian.bat"

REM Script batch para iniciar todos os serviços
(
    echo @echo off
    echo echo Iniciando ENXAME v3...
    echo.
    echo [INFO] Iniciando Juiz...
    echo start "ENXAME Juiz" cmd /k "%ENXAME_DIR%\start_juiz.bat"
    echo timeout /t 3 /nobreak ^>nul
    echo.
    echo [INFO] Iniciando Guardian...
    echo start "ENXAME Guardian" cmd /k "%ENXAME_DIR%\start_guardian.bat"
    echo.
    echo [INFO] ENXAME iniciado!
    echo Acesse: http://localhost:7700
    echo.
    echo Pressione qualquer tecla para fechar esta janela...
    echo pause ^>nul
) > "%ENXAME_DIR%\start_all.bat"

REM 9. Criar atalho na área de trabalho
echo [INFO] Criando atalho na area de trabalho...
set SCRIPT_PATH="%USERPROFILE%\Desktop\Iniciar ENXAME.lnk"
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SCRIPT_PATH%'); $Shortcut.TargetPath = '%ENXAME_DIR%\start_all.bat'; $Shortcut.WorkingDirectory = '%ENXAME_DIR%'; $Shortcut.Description = 'Iniciar ENXAME v3'; $Shortcut.Save()"

REM 10. Configurar firewall do Windows
echo [INFO] Configurando regras de firewall...
netsh advfirewall firewall add rule name="ENXAME Juiz" dir=in action=allow protocol=TCP localport=7700 >nul 2>&1
netsh advfirewall firewall add rule name="ENXAME Bibliotecario" dir=in action=allow protocol=TCP localport=7710 >nul 2>&1
netsh advfirewall firewall add rule name="ENXAME Guardian" dir=in action=allow protocol=TCP localport=7720 >nul 2>&1
netsh advfirewall firewall add rule name="ENXAME Workers" dir=in action=allow protocol=TCP localport=9000-9999 >nul 2>&1

REM 11. Mostrar informações finais
echo.
echo ============================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo ============================================================
echo.
echo [OK] ENXAME v3 foi instalado em: %ENXAME_DIR%
echo [OK] Diretorio do usuario: %USER_ENXAME_DIR%
echo.
echo [OK] Atalho criado na Area de Trabalho
echo.
echo [OK] Portas configuradas:
echo      - Juiz (porta 7700^)
echo      - Guardian (porta 7720^)
echo.
echo [OK] Para iniciar o ENXAME:
echo      - Clique duas vezes em "Iniciar ENXAME.lnk" na Area de Trabalho
echo      - Ou execute: %ENXAME_DIR%\start_all.bat
echo.
echo [OK] Acesse o painel web:
echo      http://localhost:7700
echo.
echo [OK] Documentacao: https://github.com/istacb/enxamepublic
echo.
echo ============================================================
echo.
echo Deseja iniciar o ENXAME agora?
set /p INICIAR="Digite S para sim ou N para nao: "
if /i "!INICIAR!"=="S" (
    start "" "%ENXAME_DIR%\start_all.bat"
)

pause
