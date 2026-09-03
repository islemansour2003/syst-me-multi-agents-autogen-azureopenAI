import json
import logging

from protocol.structured_logging import JsonFormatter, get_structured_logger
from protocol.tracing import trace_context


def make_record(message: str, extra_fields=None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="multiagents", level=logging.INFO, pathname="", lineno=0, msg=message, args=(), exc_info=None
    )
    if extra_fields is not None:
        record.extra_fields = extra_fields
    return record


def test_json_formatter_produces_valid_json():
    formatter = JsonFormatter()
    output = formatter.format(make_record("hello"))
    data = json.loads(output)  # lève si ce n'est pas du JSON valide
    assert data["message"] == "hello"
    assert data["level"] == "INFO"
    assert data["logger"] == "multiagents"
    assert "timestamp" in data


def test_json_formatter_includes_trace_id_when_active():
    formatter = JsonFormatter()
    with trace_context("abc123"):
        data = json.loads(formatter.format(make_record("hello")))
    assert data["trace_id"] == "abc123"


def test_json_formatter_omits_trace_id_when_no_context():
    formatter = JsonFormatter()
    data = json.loads(formatter.format(make_record("hello")))
    assert "trace_id" not in data


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    data = json.loads(formatter.format(make_record("agent_message", {"from": "codeur", "to": "reviseur"})))
    assert data["from"] == "codeur"
    assert data["to"] == "reviseur"


def test_get_structured_logger_does_not_duplicate_handlers():
    logger1 = get_structured_logger("multiagents_test_dedup")
    logger2 = get_structured_logger("multiagents_test_dedup")
    assert logger1 is logger2
    assert len(logger1.handlers) == 1
