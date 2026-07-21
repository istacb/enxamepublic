@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo   INICIANDO CLUSTER ENXAME (WINDOWS)
echo ==========================================

REM 1. Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale o Python 3.10+ e adicione ao PATH.
    pause
    exit /b 1
)

REM 2. Instalar Dependências
echo [INFO] Instalando/atualizando dependencias...
pip install -q -r requirements.txt
pip install -q -r bibliotecario/requirements.txt

REM 3. Iniciar Bibliotecário (Indexador + API de Dados) em Background
echo [INFO] Iniciando Bibliotecario (Indexacao e Busca)...
start "Enxame-Bibliotecario" cmd /k "python bibliotecario/main.py"
timeout /t 5 /nobreak >nul

REM 4. Iniciar Juiz (Cérebro Central e Roteador)
echo [INFO] Iniciando Juiz (Core e Roteamento)...
start "Enxame-Juiz" cmd /k "python juiz/app.py"
timeout /t 5 /nobreak >nul

REM 5. Iniciar Workers (Agentes Especialistas)
echo [INFO] Iniciando Workers (Agentes)...
start "Enxame-Workers" cmd /k "python agentes/cluster_worker.py"

echo ==========================================
echo   CLUSTER ONLINE!
echo   - Bibliotecario: Indexando e pronto para busca hibrida
echo   - Juiz: Ouvindo requisicoes na porta 8000
echo   - Workers: Aguardando tarefas
echo ==========================================
echo Pressione qualquer tecla para minimizar esta janela de controle...
pause >nul
