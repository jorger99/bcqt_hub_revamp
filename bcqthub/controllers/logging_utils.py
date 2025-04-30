import logging

def get_logger(
    name: str,
    debug: bool = False,
    fmt: str = "[%(name)s] %(levelname)s: %(message)s",
) -> logging.Logger:
    """
    Return a logger for `name`, configured with its own StreamHandler
    so that record.name == `name`. Subsequent calls won’t add duplicate handlers.
    """
    logger = logging.getLogger(name)

    # only add handler once
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    # set level based on debug flag
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False  # prevent double‐logging to root
    return logger
