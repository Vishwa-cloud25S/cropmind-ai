"""Structured logging with a request-id context for traceability (spec §54)."""

import contextvars
import logging
import logging.config

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_CONFIGURED = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {
                "structured": {
                    "format": 'ts=%(asctime)s level=%(levelname)s logger=%(name)s '
                    'request_id=%(request_id)s msg="%(message)s"',
                }
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "structured",
                    "filters": ["request_id"],
                }
            },
            "root": {"level": level, "handlers": ["stdout"]},
            "loggers": {"uvicorn.access": {"level": "WARNING"}},
        }
    )
    _CONFIGURED = True
