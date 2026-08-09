"""Observability middleware tests: probe paths stay quiet, real requests carry their id.

Catches the exact bug Docker logs revealed: every access line showed request_id=-
because the contextvar was reset before the log call was emitted.
"""

from __future__ import annotations

import logging

from app.core.logging import RequestIdFilter


def test_health_endpoints_do_not_spam_access_logs(client, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="cropmind.http"):
        assert client.get("/health").status_code == 200
        assert client.get("/health/ready").status_code == 200
    assert not [r for r in caplog.records if r.getMessage().startswith("GET /health")]


def test_access_log_carries_the_request_id(client) -> None:
    # Reproduce the production stdout path exactly: a handler carrying RequestIdFilter,
    # so the filter runs AT EMIT TIME inside the request — i.e. while the contextvar is
    # still set. (caplog's own handler has no such filter, so it can't prove ordering.)
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    from app.core.middleware import logger as http_logger

    handler = _Capture()
    handler.addFilter(RequestIdFilter())
    http_logger.addHandler(handler)
    try:
        resp = client.get("/supported-crops", headers={"x-request-id": "pytest-req-123"})
    finally:
        http_logger.removeHandler(handler)

    lines = [r for r in records if r.getMessage().startswith("GET /supported-crops")]
    assert len(lines) == 1
    assert lines[0].request_id == "pytest-req-123"
    assert resp.headers["x-request-id"] == "pytest-req-123"


def test_generated_request_id_still_propagates(client, caplog) -> None:
    resp = client.get("/supported-crops")  # no header → middleware generates one
    generated = resp.headers["x-request-id"]
    assert len(generated) == 12
