"""
Módulo de Logging Seguro para ENXAME
=====================================
Princípios:
- Nunca logar dados sensíveis (senhas, tokens, chaves, queries completas)
- Ofuscar informações críticas automaticamente
- Suporte a múltiplos níveis de log
- Funcionamento offline-first
- Thread-safe e async-safe
"""
from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Padrões de dados sensíveis a serem ofuscados
SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|pwd|senha)\s*[:=]\s*[\"']?[\w@#$%^&*!]+[\"']?", re.IGNORECASE), r"\1=***REDACTED***"),
    (re.compile(r"(?i)(secret|chave|token|api_key|apikey)\s*[:=]\s*[\"']?[\w\-_.]+[\"']?", re.IGNORECASE), r"\1=***REDACTED***"),
    (re.compile(r"(?i)(bearer\s+[A-Za-z0-9\-_\.]+)", re.IGNORECASE), "Bearer ***REDACTED***"),
    (re.compile(r"(?i)(basic\s+[A-Za-z0-9+/=]+)", re.IGNORECASE), "Basic ***REDACTED***"),
    (re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"), "***EMAIL***"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "***CPF***"),
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "***CNPJ***"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "***CARD***"),
]

# Caracteres perigosos que podem indicar injection attempts
INJECTION_INDICATORS = [
    "--",
    ";",
    "/*",
    "*/",
    "xp_",
    "sp_",
    "UNION",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "EXEC",
    "<script>",
    "</script>",
    "javascript:",
    "onerror=",
    "onload=",
]


def sanitize_log_message(message: str, max_length: int = 500) -> str:
    """
    Sanitiza uma mensagem de log removendo/ofuscando dados sensíveis.
    
    Args:
        message: Mensagem original do log
        max_length: Comprimento máximo da mensagem (evita log flooding)
    
    Returns:
        Mensagem sanitizada e segura para log
    """
    if not message:
        return ""
    
    # Truncar se necessário
    if len(message) > max_length:
        message = message[:max_length] + "... [truncado]"
    
    # Aplicar padrões de ofuscação
    sanitized = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    
    # Detectar possíveis tentativas de injection (apenas alerta, não bloqueia)
    upper_msg = sanitized.upper()
    for indicator in INJECTION_INDICATORS:
        if indicator.upper() in upper_msg:
            # Adiciona marcador de alerta sem revelar o conteúdo exato
            sanitized = f"[ALERTA: padrão suspeito detectado] {sanitized}"
            break
    
    return sanitized


class SecureFormatter(logging.Formatter):
    """Formatter que sanitiza todas as mensagens antes de formatar."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Sanitizar mensagem principal
        if record.msg:
            record.msg = sanitize_log_message(str(record.msg))
        
        # Sanitizar args se existirem
        if record.args:
            try:
                if isinstance(record.args, dict):
                    record.args = {
                        k: sanitize_log_message(str(v)) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        sanitize_log_message(str(a)) if isinstance(a, str) else a
                        for a in record.args
                    )
            except Exception:
                # Em caso de erro, remove args para evitar crash
                record.args = ()
        
        # Adicionar metadados seguros
        record.node_id = os.getenv("NODE_ID", "unknown")
        record.timestamp = datetime.utcnow().isoformat() + "Z"
        
        return super().format(record)


def setup_secure_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
    max_file_size_mb: int = 10,
    backup_count: int = 3,
) -> logging.Logger:
    """
    Configura um logger seguro com rotação de arquivos e sanitização automática.
    
    Args:
        name: Nome do logger (geralmente __name__)
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Caminho para arquivo de log (opcional)
        console_output: Se True, imprime também no console
        max_file_size_mb: Tamanho máximo do arquivo de log em MB
        backup_count: Número de arquivos de backup a manter
    
    Returns:
        Logger configurado com segurança
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Evitar duplicação de handlers
    if logger.handlers:
        return logger
    
    formatter = SecureFormatter(
        fmt="%(asctime)s | %(node_id)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Handler de console (se habilitado)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Handler de arquivo (se especificado)
    if log_file:
        try:
            from logging.handlers import RotatingFileHandler
            
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as exc:
            # Fallback: não falha se não conseguir criar arquivo de log
            logger.warning(f"Falha ao configurar log file {log_file}: {exc}")
    
    logger.propagate = False
    return logger


def log_safe_query(logger: logging.Logger, query: str, context: str = "") -> None:
    """
    Loga uma query de forma segura, mostrando apenas metadados.
    
    Args:
        logger: Logger a ser usado
        query: Query original (NÃO será logada completamente)
        context: Contexto da operação (ex: "search", "insert")
    """
    # Nunca logar a query completa - apenas comprimento e tipo
    query_type = "unknown"
    if query.strip():
        first_word = query.strip().split()[0].upper()
        query_type = first_word if first_word in {"SELECT", "INSERT", "UPDATE", "DELETE", "SEARCH"} else "custom"
    
    logger.info(
        "%s | Query type: %s | Length: %d chars",
        context,
        query_type,
        len(query),
    )


def log_safe_user_action(
    logger: logging.Logger,
    action: str,
    user_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Loga ações de usuário de forma segura.
    
    Args:
        logger: Logger a ser usado
        action: Tipo de ação (ex: "login", "query", "file_upload")
        user_id: ID do usuário (ofuscado parcialmente)
        details: Detalhes adicionais (valores sensíveis serão ofuscados)
    """
    safe_details = {}
    if details:
        for key, value in details.items():
            # Não logar valores de campos sensíveis
            if any(s in key.lower() for s in ["password", "secret", "token", "key"]):
                safe_details[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 50:
                safe_details[key] = f"{value[:50]}... [truncado]"
            else:
                safe_details[key] = value
    
    user_info = "***ANONYMOUS***"
    if user_id:
        # Ofuscar ID parcial se for longo
        if len(user_id) > 8:
            user_info = f"{user_id[:4]}...{user_id[-4:]}"
        else:
            user_info = user_id
    
    logger.info("Ação: %s | Usuário: %s | Detalhes: %s", action, user_info, safe_details)
