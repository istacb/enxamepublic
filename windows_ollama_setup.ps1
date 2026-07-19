# ============================================================================
# ENXAME v3 - windows_ollama_setup.ps1
# Roda no Windows do ARTISTA (ex: notebook com GPU), PowerShell como Admin.
# Instala/configura Ollama nativo para expor a GPU na rede do enxame.
# O agente (agente_universal.py) roda no WSL2 e aponta pra este Ollama.
# ============================================================================

Write-Host "ENXAME v3 - Setup do Ollama no Windows (Artista)" -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama não encontrado. Baixe e instale em: https://ollama.com/download/windows" -ForegroundColor Yellow
    Start-Process "https://ollama.com/download/windows"
    Read-Host "Pressione ENTER depois de instalar o Ollama"
}

Write-Host "Liberando Ollama na rede (0.0.0.0:11434)..."
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')

Write-Host "Criando regra de firewall..."
New-NetFirewallRule -DisplayName "Ollama ENXAME" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -ErrorAction SilentlyContinue

Write-Host "Reiniciando Ollama..."
Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden

Write-Host ""
Write-Host "Escolha o modelo conforme a GPU deste artista:" -ForegroundColor Cyan
Write-Host "  GPU >= 6GB VRAM  -> qwen2.5:7b"
Write-Host "  GPU 2-4GB VRAM   -> qwen2.5:3b"
Write-Host "  GPU fraca/integrada -> qwen2.5:1.5b"
$modelo = Read-Host "Digite o modelo a baixar (ex: qwen2.5:3b)"
if ([string]::IsNullOrWhiteSpace($modelo)) { $modelo = "qwen2.5:3b" }

ollama pull $modelo

Write-Host ""
Write-Host "Pronto! Ollama rodando e acessível na rede na porta 11434." -ForegroundColor Green
Write-Host "Modelo baixado: $modelo"
Write-Host ""
Write-Host "Agora, no WSL2 (Ubuntu), rode:"
Write-Host "  bash bootstrap_node.sh --juiz <IP_DO_JUIZ> --papel artista --modelo $modelo"
