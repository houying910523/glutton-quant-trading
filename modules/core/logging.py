import logging


def get_logger(logger_name=None) -> logging.Logger:
    """Get logger."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(name)s:%(levelname)s] %(process)d.%(threadName)s [%(pathname)s::%(funcName)s:%(lineno)d] %(message)s"
    )
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger
