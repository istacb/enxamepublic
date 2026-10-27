@echo off
REM ============================================================================
REM ENXAME Bee - Windows Batch Uninstaller
REM ============================================================================

setlocal enabledelayedexpansion

set GREEN=\033[92m
set RED=\033[91m
set YELLOW=\033[93m
set BLUE=\033[94m
set RESET=\033[0m

echo %BLUE%==================================================%RESET%
echo %BLUE%  ENXAME Bee - Windows Desinstalador%RESET%
echo %BLUE%==================================================%RESET%
echo.

REM Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[ERRO] Execute como Administrador%RESET%
    echo %YELLOW%Clique com botao direito > Executar como administrador%RESET%
    pause
    exit /b 1
)

set REMOVE_OLLAMA=false
set FORCE_OLLAMA=false
set KEEP_DATA=false
set DRY_RUN=false
set YES=false

:parse_args
if "%~1"=="" goto :run
if "%~1"=="--remove-ollama" set REMOVE_OLLAMA=true
if "%~1"=="--force-remove-ollama" set FORCE_OLLAMA=true
if "%~1"=="--keep-data" set KEEP_DATA=true
if "%~1"=="--dry-run" set DRY_RUN=true
if "%~1"=="-y" set YES=true
if "%~1"=="--yes" set YES=true
shift
goto :parse_args

:run
if "%YES%"=="false" if "%DRY_RUN%"=="false" (
    choice /C YN /M "Isso removera a Abelha completamente. Continuar? [y/N]"
    if %errorLevel% equ 2 (
        echo Cancelado.
        exit /b 0
    )
)

if "%DRY_RUN%"=="true" (
    echo %YELLOW%[DRY-RUN] Modo simulacao - nenhuma acao sera executada%RESET%
)

echo %BLUE%==================================================%RESET%
echo %BLUE%  Parando servicos...%RESET%
echo %BLUE%==================================================%RESET%
if "%DRY_RUN%"=="false" (
    net stop "enxame-bee" >nul 2>&1
    sc config "enxame-bee" start= disabled >nul 2>&1
    schtasks /Delete /TN "ENXAME Bee" /F >nul 2>&1
)

echo %BLUE%==================================================%RESET%
echo %BLUE%  Removendo binarios...%RESET%
echo %BLUE%==================================================%RESET%
if "%DRY_RUN%"=="false" (
    for %%p in (
        "%ProgramFiles%\ENXAME Bee"
        "%LocalAppData%\ENXAME Bee"
        "%ProgramFiles%\enxame-bee"
        "%LocalAppData%\enxame-bee"
    ) do (
        if exist "%%p" (
            rmdir /s /q "%%p" 2>nul
            echo %GREEN%[OK] Removido: %%p%RESET%
        )
    )
)

echo %BLUE%==================================================%RESET%
echo %BLUE%  Removendo do PATH...%RESET%
echo %BLUE%==================================================%RESET%
if "%DRY_RUN%"=="false" (
    REM User PATH
    for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set USER_PATH=%%b
    if defined USER_PATH (
        set NEW_PATH=
        for %%p in (%USER_PATH:;= %) do (
            echo "%%p" | findstr /i "enxame" >nul
            if errorlevel 1 set NEW_PATH=!NEW_PATH!;%%p
        )
        if defined NEW_PATH (
            reg add "HKCU\Environment" /v Path /t REG_EXPAND_SZ /d "!NEW_PATH:~1!" /f >nul
        )
    )
    
    REM System PATH
    for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set SYS_PATH=%%b
    if defined SYS_PATH (
        echo %SYS_PATH% | findstr /i "enxame" >nul
        if not errorlevel 1 (
            set NEW_SYS_PATH=
            for %%p in (%SYS_PATH:;= %) do (
                echo "%%p" | findstr /i "enxame" >nul
                if errorlevel 1 set NEW_SYS_PATH=!NEW_SYS_PATH!;%%p
            )
            if defined NEW_SYS_PATH (
                reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path /t REG_EXPAND_SZ /d "!NEW_SYS_PATH:~1!" /f >nul
            )
        )
    )
)

if "%KEEP_DATA%"=="false" (
    echo %BLUE%==================================================%RESET%
    echo %BLUE%  Removendo dados...%RESET%
    echo %BLUE%==================================================%RESET%
    if "%DRY_RUN%"=="false" (
        for %%p in (
            "%LocalAppData%\enxame"
            "%LocalAppData%\enxame-bee"
            "%AppData%\enxame"
            "%AppData%\enxame-bee"
        ) do (
            if exist "%%p" (
                rmdir /s /q "%%p" 2>nul
                echo %GREEN%[OK] Removido: %%p%RESET%
            )
        )
    )
) else (
    echo %YELLOW%[INFO] Mantendo dados (--keep-data)%RESET%
)

echo %BLUE%==================================================%RESET%
echo %BLUE%  Limpando registro...%RESET%
echo %BLUE%==================================================%RESET%
if "%DRY_RUN%"=="false" (
    for %%r in (
        "HKCU\Software\ENXAME"
        "HKCU\Software\enxame-bee"
        "HKLM\SOFTWARE\ENXAME"
        "HKLM\SOFTWARE\enxame-bee"
    ) do (
        reg delete "%%r" /f >nul 2>&1
        if not errorlevel 1 echo %GREEN%[OK] Removido registro: %%r%RESET%
    )
)

if "%REMOVE_OLLAMA%"=="true" (
    echo %BLUE%==================================================%RESET%
    echo %BLUE%  Removendo Ollama...%RESET%
    echo %BLUE%==================================================%RESET%
    if "%DRY_RUN%"=="false" (
        net stop "Ollama" >nul 2>&1
        sc config "Ollama" start= disabled >nul 2>&1
        
        for %%p in (
            "%ProgramFiles%\Ollama"
            "%LocalAppData%\Programs\Ollama"
            "%UserProfile%\.ollama"
        ) do (
            if exist "%%p" (
                rmdir /s /q "%%p" 2>nul
                echo %GREEN%[OK] Removido: %%p%RESET%
            )
        )
    )
)

echo.
echo %BLUE%==================================================%RESET%
echo %GREEN%  Desinstalacao concluida!%RESET%
echo %BLUE%==================================================%RESET%
echo.

if "%KEEP_DATA%"=="true" (
    echo %YELLOW%Dados mantidos em: %LocalAppData%\enxame\bee%RESET%
)

pause