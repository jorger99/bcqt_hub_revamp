import logging

def configure_logger(level: int = logging.INFO,
                      fmt: str = "[%(name)s] %(levelname)s: %(message)s") -> None:
    """
    Configure the root logger once for the entire application.
    Subsequent calls do nothing if already configured.
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    root.setLevel(level)
    root.addHandler(handler)

def get_logger(name: str, *, debug: bool = False) -> logging.Logger:
    """
    Return a logger with the given name. If debug=True, bump its level to DEBUG.
    """
    logger = logging.getLogger(name)
    if debug:
        logger.setLevel(logging.DEBUG)
        
    return logger
