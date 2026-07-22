import logging
import sys
from typing import Optional

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    logger = logging.getLogger(f"enxame.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(mission_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Add mission_id filter
        logger.addFilter(lambda record: setattr(record, 'mission_id', getattr(record, 'mission_id', 'N/A')) or True)
        
    return logger

def setup_logging():
    """Setup global logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )