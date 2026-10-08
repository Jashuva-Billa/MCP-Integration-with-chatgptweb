import logging
import sys
import re
from typing import Any

class SensitiveDataFilter(logging.Filter):
    """Filters out potential secrets, bearer tokens, and keys from log records."""
    
    TOKEN_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE)
    KEY_PATTERN = re.compile(r"(['\"]?(?:api[_-]?key|secret|password|token)['\"]?\s*[:=]\s*['\"]?)([^'\"\s,]{6,})", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.TOKEN_PATTERN.sub(r"\1[REDACTED]", record.msg)
            record.msg = self.KEY_PATTERN.sub(r"\1[REDACTED]", record.msg)
        return True

def setup_logging(level_name: str = "INFO") -> logging.Logger:
    """Configures application-wide structured logging with sensitive data sanitization."""
    log_level = getattr(logging, level_name.upper(), logging.INFO)
    
    logger = logging.getLogger("mcp_server")
    logger.setLevel(log_level)
    
    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        
    return logger

logger = setup_logging()
