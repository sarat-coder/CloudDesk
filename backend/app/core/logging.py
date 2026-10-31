from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Iterator


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_workflow_id: ContextVar[str | None] = ContextVar("workflow_id", default=None)
_JSON_HANDLER_MARKER = "_clouddesk_json_handler"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
            "workflow_id": _workflow_id.get(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack"] = self.formatStack(record.stack_info)
        return json.dumps(entry, ensure_ascii=False, separators=(",", ":"))


@contextmanager
def log_context(
    *, request_id: str | None = None, workflow_id: str | None = None
) -> Iterator[None]:
    tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = []
    if request_id is not None:
        tokens.append((_request_id, _request_id.set(request_id)))
    if workflow_id is not None:
        tokens.append((_workflow_id, _workflow_id.set(workflow_id)))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def setup_logging(level: int | str = logging.INFO) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers[:] = [
        handler
        for handler in root_logger.handlers
        if not getattr(handler, _JSON_HANDLER_MARKER, False)
    ]

    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _JSON_HANDLER_MARKER, True)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
