#!/usr/bin/env python3
"""
BeeConfig — Configuração Cross-Platform da Abelha
=================================================
Gerencia:
- Diretórios de dados multiplataforma
- Carregamento de configuração de arquivo/env
- Defaults sensíveis
"""

from __future__ import annotations

import json
import os
import platform
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class BeeConfig:
    """Configuração completa da Abelha."""

    # Identidade
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Rede
    host: str = "0.0.0.0"
    port: int = 8765
    host_ip: str = "127.0.0.1"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    model: str = "llama3.2:3b"

    # Diretórios (resolvidos em __post_init__)
    data_dir: Path = field(default_factory=lambda: Path.home() / ".enxame" / "bee")

    # Comportamento
    allow_web: bool = False
    shared_secret: str | None = None
    log_level: str = "INFO"

    # Thresholds para política LOCAL -> ENXAME -> WEB
    confidence_threshold_enxame: float = 0.7
    confidence_threshold_web: float = 0.8

    # Heartbeat
    heartbeat_interval: float = 5.0
    heartbeat_timeout: float = 15.0

    # Limites
    max_concurrent_queries: int = 4
    query_timeout_seconds: int = 60
    max_cache_items: int = 1000

    def __post_init__(self) -> None:
        """Resolve paths e valida configuração."""
        self.data_dir = Path(self.data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Subdiretórios
        (self.data_dir / "documents").mkdir(exist_ok=True)
        (self.data_dir / "zim").mkdir(exist_ok=True)
        (self.data_dir / "lancedb").mkdir(exist_ok=True)
        (self.data_dir / "cache").mkdir(exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)

        # Detectar IP local se não definido
        if self.host_ip == "127.0.0.1":
            self.host_ip = self._detect_local_ip()

    def _detect_local_ip(self) -> str:
        """Detecta IP local da máquina."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "host_ip": self.host_ip,
            "ollama_base_url": self.ollama_base_url,
            "model": self.model,
            "data_dir": str(self.data_dir),
            "allow_web": self.allow_web,
            "shared_secret": self.shared_secret,
            "log_level": self.log_level,
            "confidence_threshold_enxame": self.confidence_threshold_enxame,
            "confidence_threshold_web": self.confidence_threshold_web,
            "heartbeat_interval": self.heartbeat_interval,
            "heartbeat_timeout": self.heartbeat_timeout,
            "max_concurrent_queries": self.max_concurrent_queries,
            "query_timeout_seconds": self.query_timeout_seconds,
            "max_cache_items": self.max_cache_items,
        }

    def save(self, path: Path | None = None) -> None:
        """Salva configuração em arquivo JSON."""
        path = path or (self.data_dir / "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> BeeConfig:
        """Carrega configuração de arquivo JSON."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Converter data_dir de volta para Path
        if "data_dir" in data:
            data["data_dir"] = Path(data["data_dir"])
        return cls(**data)


def get_default_data_dir() -> Path:
    """Retorna diretório de dados padrão multiplataforma."""
    system = platform.system()

    if system == "Windows":
        # Windows: %LOCALAPPDATA%\enxame\bee
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        # macOS: ~/Library/Application Support/enxame/bee
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux/Unix: ~/.local/share/enxame/bee ou ~/.enxame/bee
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return base / "enxame" / "bee"


def load_config(args: Any | None = None) -> BeeConfig:
    """
    Carrega configuração combinando:
    1. Defaults
    2. Arquivo de configuração (~/.enxame/bee/config.json)
    3. Variáveis de ambiente
    4. Argumentos de linha de comando (args)
    """
    # 1. Defaults
    config = BeeConfig(data_dir=get_default_data_dir())

    # 2. Arquivo de configuração
    config_file = config.data_dir / "config.json"
    if config_file.exists():
        try:
            file_config = BeeConfig.load(config_file)
            # Mesclar mantendo node_id do arquivo
            config.node_id = file_config.node_id
            config.host = file_config.host
            config.port = file_config.port
            config.host_ip = file_config.host_ip
            config.ollama_base_url = file_config.ollama_base_url
            config.model = file_config.model
            config.allow_web = file_config.allow_web
            config.shared_secret = file_config.shared_secret
            config.log_level = file_config.log_level
            config.confidence_threshold_enxame = file_config.confidence_threshold_enxame
            config.confidence_threshold_web = file_config.confidence_threshold_web
            config.heartbeat_interval = file_config.heartbeat_interval
            config.heartbeat_timeout = file_config.heartbeat_timeout
            config.max_concurrent_queries = file_config.max_concurrent_queries
            config.query_timeout_seconds = file_config.query_timeout_seconds
            config.max_cache_items = file_config.max_cache_items
        except Exception as e:
            print(f"Aviso: erro ao carregar config: {e}")

    # 3. Variáveis de ambiente
    env_mapping = {
        "BEE_NODE_ID": ("node_id", str),
        "BEE_HOST": ("host", str),
        "BEE_PORT": ("port", int),
        "BEE_HOST_IP": ("host_ip", str),
        "BEE_OLLAMA_URL": ("ollama_base_url", str),
        "BEE_MODEL": ("model", str),
        "BEE_DATA_DIR": ("data_dir", Path),
        "BEE_ALLOW_WEB": ("allow_web", lambda x: x.lower() == "true"),
        "BEE_SHARED_SECRET": ("shared_secret", str),
        "BEE_LOG_LEVEL": ("log_level", str),
        "BEE_CONFIDENCE_ENXAME": ("confidence_threshold_enxame", float),
        "BEE_CONFIDENCE_WEB": ("confidence_threshold_web", float),
        "BEE_HEARTBEAT_INTERVAL": ("heartbeat_interval", float),
        "BEE_HEARTBEAT_TIMEOUT": ("heartbeat_timeout", float),
    }

    for env_var, (attr, converter) in env_mapping.items():
        value = os.getenv(env_var)
        if value is not None:
            try:
                setattr(config, attr, converter(value))
            except Exception as e:
                print(f"Aviso: erro ao converter {env_var}={value}: {e}")

    # 4. Argumentos de linha de comando
    if args:
        arg_mapping = {
            "config": ("data_dir", Path),  # --config aponta para diretório
            "data_dir": ("data_dir", Path),
            "host": ("host", str),
            "port": ("port", int),
            "ollama_url": ("ollama_base_url", str),
            "model": ("model", str),
            "allow_web": ("allow_web", lambda x: x),
            "shared_secret": ("shared_secret", str),
            "log_level": ("log_level", str),
        }

        for arg_name, (attr, converter) in arg_mapping.items():
            value = getattr(args, arg_name, None)
            if value is not None:
                try:
                    setattr(config, attr, converter(value))
                except Exception as e:
                    print(f"Aviso: erro ao converter arg {arg_name}={value}: {e}")

    # Re-resolver paths após possíveis mudanças
    config.__post_init__()

    return config


def generate_identity(data_dir: Path) -> dict[str, Any]:
    """Gera nova identidade para a Abelha."""
    import uuid
    from cryptography.hazmat.primitives.asymmetric import ed25519
    import base64

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    identity = {
        "node_id": str(uuid.uuid4()),
        "public_key": base64.b64encode(
            public_key.public_bytes_raw()
        ).decode("ascii"),
        "private_key": base64.b64encode(
            private_key.private_bytes_raw()
        ).decode("ascii"),
        "created_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        "protocol_version": "1.0",
    }

    identity_file = data_dir / "identity.json"
    with open(identity_file, "w") as f:
        json.dump(identity, f, indent=2)

    return identity


def load_identity(data_dir: Path) -> dict[str, Any] | None:
    """Carrega identidade existente."""
    identity_file = data_dir / "identity.json"
    if identity_file.exists():
        with open(identity_file) as f:
            return json.load(f)
    return None