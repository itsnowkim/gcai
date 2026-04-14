import logging
from logging.config import dictConfig


def configure_logging(level: str = "INFO") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s",
                }
            },
            "filters": {
                "request_context": {
                    "()": "app.middleware.request_context.RequestContextFilter",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_context"],
                }
            },
            "root": {"handlers": ["console"], "level": level.upper()},
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
