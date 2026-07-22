from pydantic import BaseSettings, Field
from typing import Optional, List

class Settings(BaseSettings):
    # General
    PLUGIN_NAME: str = "Enxame OS"
    ENABLED: bool = True
    DEBUG_MODE: bool = False
    
    # Security (Guard)
    GUARD_ENABLED: bool = True
    BLOCK_JAILBREAK: bool = True
    BLOCK_INJECTION: bool = True
    
    # Knowledge (Librarian)
    LIBRARIAN_ENABLED: bool = True
    INDEX_PATH: str = "./data/enxame/index"
    
    # Orchestration
    MAX_AGENTS: int = 5
    TIMEOUT_SECONDS: int = 60
    RETRY_COUNT: int = 3
    
    class Config:
        env_prefix = "ENXAME_"
        env_file = ".env"

settings = Settings()