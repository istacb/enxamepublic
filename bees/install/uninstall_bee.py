#!/usr/bin/env python3
"""
BEE-0008 — Desinstalador da Abelha

Remove completamente:
1. Modelos baixados
2. Configurações locais
3. Manifesto e logs
4. Opcionalmente: Ollama (se instalado pelo script)

Uso:
    python uninstall_bee.py [--remove-ollama] [--keep-data] [--dry-run]
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import argparse
from pathlib import Path
from typing import Optional, List

# Configurações
BEE_HOME = Path.home() / ".enxame" / "bee"
OLD_BEE_HOME = Path.home() / ".enxame"  # Versão antiga
MANIFEST_FILE = BEE_HOME / "manifest.json"
INSTALL_LOG = BEE_HOME / "install.log"


def log(message: str, level: str = "INFO"):
    """Registra mensagem no log e stdout"""
    timestamp = subprocess.getoutput("date '+%Y-%m-%d %H:%M:%S'") if platform.system() != "Windows" else ""
    log_line = f"[{timestamp}] [{level}] {message}" if timestamp else f"[{level}] {message}"
    print(log_line)


def detect_ollama() -> Optional[str]:
    """Detecta se Ollama está instalado"""
    ollama_path = shutil.which("ollama")
    if ollama_path:
        return ollama_path
    
    common_paths = [
        "/usr/local/bin/ollama",
        "/usr/bin/ollama",
        "/opt/ollama/bin/ollama",
        str(Path.home() / ".ollama" / "bin" / "ollama"),
    ]
    
    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    if platform.system() == "Windows":
        win_paths = [
            r"C:\Program Files\Ollama\ollama.exe",
        ]
        for path in win_paths:
            if os.path.isfile(path):
                return path
    
    return None


def was_ollama_installed_by_bee() -> bool:
    """Verifica se Ollama foi instalado pelo instalador da Abelha"""
    # Marcador criado durante instalação
    marker_file = BEE_HOME / ".ollama_installed_by_bee"
    return marker_file.exists()


def remove_directory(path: Path, dry_run: bool = False) -> bool:
    """Remove diretório recursivamente"""
    if not path.exists():
        log(f"Diretório não existe: {path}", "INFO")
        return True
    
    if dry_run:
        log(f"[DRY-RUN] Removeria {path} e todo seu conteúdo", "INFO")
        return True
    
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        
        log(f"Removido: {path}", "SUCCESS")
        return True
        
    except Exception as e:
        log(f"Falha ao remover {path}: {e}", "ERROR")
        return False


def stop_ollama_service() -> bool:
    """Para o serviço Ollama"""
    log("Parando serviço Ollama...")
    
    try:
        if platform.system() == "Linux":
            subprocess.run(["systemctl", "stop", "ollama"], timeout=30)
        elif platform.system() == "Darwin":
            subprocess.run(["launchctl", "unload", "-w", "/Library/LaunchDaemons/com.ollama.ollama.plist"], timeout=30)
        # Windows - parar serviço
        
        log("Serviço Ollama parado", "SUCCESS")
        return True
        
    except Exception as e:
        log(f"Erro ao parar serviço: {e}", "WARN")
        return False


def uninstall_ollama(dry_run: bool = False) -> bool:
    """Desinstala Ollama do sistema"""
    system = platform.system()
    log(f"Desinstalando Ollama ({system})...")
    
    if dry_run:
        log(f"[DRY-RUN] Desinstalaria Ollama de {system}", "INFO")
        return True
    
    try:
        if system == "Linux":
            # Script de desinstalação oficial
            cmd = "curl -fsSL https://ollama.com/install.sh | sh -s -- --uninstall"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                # Fallback: remoção manual
                log("Script oficial falhou, tentando remoção manual...", "WARN")
                
                paths_to_remove = [
                    "/usr/local/bin/ollama",
                    "/usr/bin/ollama",
                    "/opt/ollama",
                    "/etc/systemd/system/ollama.service",
                    str(Path.home() / ".ollama"),
                ]
                
                for path in paths_to_remove:
                    p = Path(path)
                    if p.exists():
                        if p.is_dir():
                            shutil.rmtree(p)
                        else:
                            p.unlink()
                
                # Remover usuário ollama se existir
                subprocess.run(["userdel", "ollama"], capture_output=True)
                
            log("Ollama desinstalado do Linux", "SUCCESS")
            
        elif system == "Darwin":
            if shutil.which("brew"):
                cmd = "brew uninstall ollama"
                subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
            
            # Remover arquivos manuais
            manual_paths = [
                "/Library/LaunchDaemons/com.ollama.ollama.plist",
                "/usr/local/bin/ollama",
                str(Path.home() / ".ollama"),
            ]
            
            for path in manual_paths:
                p = Path(path)
                if p.exists():
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
            
            log("Ollama desinstalado do macOS", "SUCCESS")
            
        elif system == "Windows":
            log("No Windows, use 'Adicionar ou Remover Programas' para remover Ollama", "INFO")
            log("Caminho comum: C:\\Program Files\\Ollama", "INFO")
            return False
        
        return True
        
    except Exception as e:
        log(f"Erro na desinstalação: {e}", "ERROR")
        return False


def list_files_to_remove() -> List[Path]:
    """Lista todos os arquivos que serão removidos"""
    files = []
    
    # Diretório principal da Abelha
    if BEE_HOME.exists():
        for item in BEE_HOME.rglob("*"):
            files.append(item)
    
    # Diretório antigo (se existir)
    if OLD_BEE_HOME.exists() and OLD_BEE_HOME != BEE_HOME.parent:
        for item in OLD_BEE_HOME.rglob("*"):
            if item not in files:
                files.append(item)
    
    # Cache específico
    cache_dirs = [
        Path.home() / ".cache" / "enxame",
        Path.home() / ".cache" / "bee",
    ]
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            for item in cache_dir.rglob("*"):
                if item not in files:
                    files.append(item)
    
    return files


def print_summary(files_removed: int, ollama_removed: bool, data_kept: bool):
    """Imprime resumo da desinstalação"""
    print("\n" + "="*60)
    print("🐝 DESINSTALAÇÃO DA ABELHA")
    print("="*60)
    
    if data_kept:
        print("\n⚠️  DADOS PRESERVADOS (opção --keep-data)")
        print("   Para remover tudo, execute sem --keep-data")
    
    print(f"\nArquivos/diretórios removidos: {files_removed}")
    print(f"Ollama removido: {'Sim' if ollama_removed else 'Não'}")
    
    if not ollama_removed:
        print("\nℹ️  Ollama permanece instalado no sistema")
        print("   Para remover manualmente:")
        print("   - Linux: curl -fsSL https://ollama.com/install.sh | sh -s -- --uninstall")
        print("   - macOS: brew uninstall ollama")
        print("   - Windows: Painel de Controle > Programas")
    
    print("\n" + "="*60)
    print("Desinstalação concluída.")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="Desinstalador da Abelha")
    parser.add_argument("--remove-ollama", action="store_true",
                       help="Também remover Ollama (apenas se instalado pela Abelha)")
    parser.add_argument("--force-remove-ollama", action="store_true",
                       help="Forçar remoção do Ollama mesmo se não instalado pela Abelha")
    parser.add_argument("--keep-data", action="store_true",
                       help="Manter documentos indexados e dados do Bibliotecário")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simular desinstalação sem remover nada")
    parser.add_argument("-y", "--yes", action="store_true",
                       help="Confirmar automaticamente (sem prompt)")
    
    args = parser.parse_args()
    
    log("="*60)
    log("INICIANDO DESINSTALAÇÃO DA ABELHA")
    log("="*60)
    
    # Verificar o que existe
    bee_exists = BEE_HOME.exists()
    old_bee_exists = OLD_BEE_HOME.exists()
    ollama_exists = detect_ollama() is not None
    ollama_installed_by_bee = was_ollama_installed_by_bee()
    
    print("\nEstado atual:")
    print(f"  Abelha instalada: {'Sim' if bee_exists or old_bee_exists else 'Não'}")
    print(f"  Ollama instalado: {'Sim' if ollama_exists else 'Não'}")
    if ollama_exists and ollama_installed_by_bee:
        print(f"  Ollama instalado pela Abelha: Sim")
    
    if not bee_exists and not old_bee_exists:
        log("Nenhuma instalação da Abelha encontrada", "WARN")
        if not args.dry_run:
            print("\nNada para desinstalar.")
        return 0
    
    # Confirmar
    if not args.yes and not args.dry_run:
        print("\n⚠️  ATENÇÃO: Esta operação removerá permanentemente:")
        print("   - Configurações da Abelha")
        print("   - Modelos baixados")
        print("   - Manifesto e logs")
        if not args.keep_data:
            print("   - Documentos indexados localmente")
            print("   - Memória e contexto armazenados")
        
        if args.remove_ollama or args.force_remove_ollama:
            print("   - Ollama (runtime de IA)")
        
        response = input("\nDeseja continuar? (y/N): ")
        if response.lower() != 'y':
            log("Desinstalação cancelada pelo usuário", "INFO")
            return 0
    
    files_removed = 0
    ollama_removed = False
    
    # 1. Parar serviços se estiverem rodando
    log("\nPasso 1: Parando serviços...")
    # Na prática, pararia a Abelha se estivesse rodando
    
    # 2. Remover diretórios da Abelha
    log("\nPasso 2: Removendo arquivos da Abelha...")
    
    dirs_to_remove = []
    
    if BEE_HOME.exists():
        dirs_to_remove.append(BEE_HOME)
    
    if old_bee_exists and OLD_BEE_HOME != BEE_HOME.parent:
        # Evitar duplicação
        if not str(OLD_BEE_HOME).startswith(str(BEE_HOME)):
            dirs_to_remove.append(OLD_BEE_HOME)
    
    # Caches
    if not args.keep_data:
        cache_dirs = [
            Path.home() / ".cache" / "enxame",
            Path.home() / ".cache" / "bee",
        ]
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                dirs_to_remove.append(cache_dir)
    
    # Contar arquivos antes de remover
    total_files = 0
    for d in dirs_to_remove:
        if d.exists():
            try:
                total_files += sum(1 for _ in d.rglob("*"))
            except:
                pass
    
    # Remover
    for dir_path in dirs_to_remove:
        if args.keep_data and "documents" in str(dir_path) or "index" in str(dir_path):
            log(f"Pulando (keep-data): {dir_path}", "INFO")
            continue
        
        if remove_directory(dir_path, dry_run=args.dry_run):
            files_removed += 1
    
    if not args.dry_run:
        log(f"{files_removed} diretórios removidos", "SUCCESS")
    
    # 3. Remover Ollama (opcional)
    if args.remove_ollama or args.force_remove_ollama:
        log("\nPasso 3: Removendo Ollama...")
        
        if not ollama_exists:
            log("Ollama não está instalado", "INFO")
        elif args.remove_ollama and not ollama_installed_by_bee and not args.force_remove_ollama:
            log("Ollama não foi instalado pela Abelha. Use --force-remove-ollama para remover.", "WARN")
        else:
            if stop_ollama_service():
                if uninstall_ollama(dry_run=args.dry_run):
                    ollama_removed = True
                    
                    # Remover marcador
                    marker_file = BEE_HOME / ".ollama_installed_by_bee"
                    if not args.dry_run and marker_file.exists():
                        marker_file.unlink()
    
    # 4. Limpar variáveis de ambiente (apenas aviso)
    log("\nPasso 4: Limpando configurações residuais...")
    
    if not args.dry_run:
        # Remover de shell configs se necessário
        shell_configs = [
            Path.home() / ".bashrc",
            Path.home() / ".zshrc",
            Path.home() / ".profile",
        ]
        
        for config_file in shell_configs:
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        content = f.read()
                    
                    # Remover linhas relacionadas à Abelha
                    lines = content.split('\n')
                    new_lines = [l for l in lines if 'BEE_HOME' not in l and 'OLLAMA' not in l or 'export' not in l]
                    
                    if len(new_lines) != len(lines):
                        with open(config_file, 'w') as f:
                            f.write('\n'.join(new_lines))
                        log(f"Limpo: {config_file}", "INFO")
                        
                except Exception as e:
                    log(f"Erro ao limpar {config_file}: {e}", "WARN")
    
    # Imprimir resumo
    print_summary(files_removed, ollama_removed, args.keep_data)
    
    log("="*60)
    log("DESINSTALAÇÃO CONCLUÍDA")
    log("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
