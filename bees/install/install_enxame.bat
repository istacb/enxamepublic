@echo off
REM ============================================================================
REM ENXAME Bee - Windows Installer Helpers
REM ============================================================================

setlocal enabledelayedexpansion

REM Colors
set GREEN=\033[92m
set RED=\033[91m
set YELLOW=\033[93m
set BLUE=\033[94m
set RESET=\033[0m

echo %BLUE%==================================================%RESET%
echo %BLUE%  ENXAME Bee - Windows Setup%RESET%
echo %BLUE%==================================================%RESET%
echo.

REM ---------------------------------------------------------------------------
REM Check if running as Administrator
REM ---------------------------------------------------------------------------
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[ERRO] Este script precisa ser executado como Administrador%RESET%
    echo %YELLOW%Por favor, clique com botao direito e escolha "Executar como administrador"%RESET%
    pause
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM Detect Python
REM ---------------------------------------------------------------------------
echo %BLUE%[1/5] Verificando Python...%RESET%
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo %YELLOW%Python nao encontrado no PATH. Tentando caminhos comuns...%RESET%
    if exist "%ProgramFiles%\Python312\python.exe" set PYTHON="%ProgramFiles%\Python312\python.exe"
    if exist "%ProgramFiles%\Python311\python.exe" set PYTHON="%ProgramFiles%\Python311\python.exe"
    if exist "%ProgramFiles%\Python310\python.exe" set PYTHON="%ProgramFiles%\Python310\python.exe"
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set PYTHON="%LocalAppData%\Programs\Python\Python312\python.exe"
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set PYTHON="%LocalAppData%\Programs\Python\Python311\python.exe"
    if exist "%LocalAppData%\Programs\Python\Python310\python.exe" set PYTHON="%LocalAppData%\Programs\Python\Python310\python.exe"
) else (
    set PYTHON=python
)

if not defined PYTHON (
    echo %RED%[ERRO] Python 3.10+ nao encontrado.%RESET%
    echo %YELLOW%Por favor, instale Python de https://python.org/downloads/%RESET%
    pause
    exit /b 1
)

echo %GREEN%[OK] Python encontrado: !PYTHON!%RESET%

REM ---------------------------------------------------------------------------
REM Check Python version
REM ---------------------------------------------------------------------------
for /f "tokens=2 delims= " %%a in ('!PYTHON! -c "import sys; print(sys.version_info[:2])"') do set PY_VER=%%a
echo %GREEN%[OK] Python version: !PY_VER!%RESET%

REM ---------------------------------------------------------------------------
REM Install/Update Ollama
REM ---------------------------------------------------------------------------
echo.
echo %BLUE%[2/5] Verificando Ollama...%RESET%
where ollama >nul 2>&1
if %errorLevel% neq 0 (
    echo %YELLOW%Ollama nao encontrado. Instalando...%RESET%
    
    REM Download Ollama installer
    powershell -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe'"
    if %errorLevel% neq 0 (
        echo %RED%[ERRO] Falha ao baixar Ollama%RESET%
        pause
        exit /b 1
    )
    
    REM Install silently
    "%TEMP%\OllamaSetup.exe" /S
    if %errorLevel% neq 0 (
        echo %RED%[ERRO] Falha ao instalar Ollama%RESET%
        pause
        exit /b 1
    )
    
    echo %GREEN%[OK] Ollama instalado%RESET%
) else (
    echo %GREEN%[OK] Ollama ja instalado%RESET%
)

REM ---------------------------------------------------------------------------
REM Start Ollama service
REM ---------------------------------------------------------------------------
echo.
echo %BLUE%[3/5] Iniciando servico Ollama...%RESET%
ollama list >nul 2>&1
if %errorLevel% neq 0 (
    echo %YELLOW%Iniciando servico Ollama...%RESET%
    start /B ollama serve
    timeout /t 5 >nul
    
    ollama list >nul 2>&1
    if %errorLevel% neq 0 (
        echo %RED%[ERRO] Ollama nao iniciou corretamente%RESET%
        pause
        exit /b 1
    )
)
echo %GREEN%[OK] Ollama rodando%RESET%

REM ---------------------------------------------------------------------------
REM Install Python dependencies
REM ---------------------------------------------------------------------------
echo.
echo %BLUE%[4/5] Instalando dependencias Python...%RESET%
!PYTHON! -m pip install --upgrade pip setuptools wheel >nul 2>&1
!PYTHON! -m pip install httpx pydantic pydantic-settings psutil zeroconf cryptography rich pyyaml >nul 2>&1
if %errorLevel% neq 0 (
    echo %YELLOW%[AVISO] Algumas dependencias podem nao ter instalado corretamente%RESET%
) else (
    echo %GREEN%[OK] Dependencias instaladas%RESET%
)

REM ---------------------------------------------------------------------------
REM Run Bee installer
REM ---------------------------------------------------------------------------
echo.
echo %BLUE%[5/5] Executando instalador da Abelha...%RESET%
cd /d "%~dp0.."
!PYTHON! -m bees.install.install_bee
if %errorLevel% neq 0 (
    echo %RED%[ERRO] Instalacao da Abelha falhou%RESET%
    pause
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM Create Start Menu shortcut
REM ---------------------------------------------------------------------------
echo.
echo %BLUE%==================================================%RESET%
echo %GREEN%Instalacao concluida com sucesso!%RESET%
echo %BLUE%==================================================%RESET%
echo.
echo %YELLOW%Proximos passos:%RESET%
echo  1. Abra um novo terminal (PowerShell ou CMD)
echo  2. Execute: bee status
echo  3. Inicie a Abelha: bee start
echo  4. Descubra peers: bee discover
echo  5. Faca uma query: bee query "Sua pergunta"
echo.
echo %BLUE%Documentacao: https://github.com/enxame/enxamepublic%RESET%
echo.

REM Offer to start Bee now
choice /C YN /M "Deseja iniciar a Abelha agora?"
if %errorLevel% equ 1 (
    start "ENXAME Bee" cmd /k "bee start"
)

pause