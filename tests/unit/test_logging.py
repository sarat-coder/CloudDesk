import json
import logging

from app.core.logging import JsonFormatter, log_context, setup_logging


def test_json_formatter_includes_context_ids():
    record = logging.LogRecord(
        name="clouddesk.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=12,
        msg="workflow started",
        args=(),
        exc_info=None,
    )

    with log_context(request_id="request-123", workflow_id="workflow-456"):
        payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "workflow started"
    assert payload["request_id"] == "request-123"
    assert payload["workflow_id"] == "workflow-456"
    assert payload["level"] == "INFO"
    assert payload["timestamp"].endswith("Z")


def test_json_formatter_uses_null_for_unbound_context():
    record = logging.LogRecord(
        name="clouddesk.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=12,
        msg="background startup",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] is None
    assert payload["workflow_id"] is None


def test_log_context_nests_and_restores_values():
    record = logging.LogRecord(
        name="clouddesk.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=12,
        msg="nested",
        args=(),
        exc_info=None,
    )
    formatter = JsonFormatter()

    with log_context(request_id="request-123"):
        with log_context(workflow_id="workflow-456"):
            nested = json.loads(formatter.format(record))
        restored = json.loads(formatter.format(record))

    assert nested["request_id"] == "request-123"
    assert nested["workflow_id"] == "workflow-456"
    assert restored["request_id"] == "request-123"
    assert restored["workflow_id"] is None


def test_setup_logging_is_idempotent():
    root_logger = logging.getLogger()

    setup_logging()
    handlers_after_first_setup = [
        handler
        for handler in root_logger.handlers
        if getattr(handler, "_clouddesk_json_handler", False)
    ]
    setup_logging()
    handlers_after_second_setup = [
        handler
        for handler in root_logger.handlers
        if getattr(handler, "_clouddesk_json_handler", False)
    ]

    assert len(handlers_after_first_setup) == 1
    assert len(handlers_after_second_setup) == 1

    for handler in handlers_after_second_setup:
        root_logger.removeHandler(handler)
        handler.close()
