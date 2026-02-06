"""Tests for logging redaction behavior."""

import io
import logging

from sassy_wallet.core.logger import safe_log_exception, get_logger, redact_sensitive_text


def test_safe_log_exception_does_not_log_args_values():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.ERROR)
    logger = get_logger()
    logger.addHandler(handler)
    try:
        @safe_log_exception(default_return=None, user_message="boom")
        def _explode(secret_value: str):
            raise RuntimeError("expected")

        _explode("super-secret-value")
        out = stream.getvalue()
        assert "super-secret-value" not in out
        assert "ArgCount: 1 Positional, 0 Keyword" in out
    finally:
        logger.removeHandler(handler)


def test_redact_sensitive_text_masks_addresses_hashes_and_keys():
    msg = (
        "from tz1WMTY8n6gdR66rrGXWmvddmAH5WvJnspPA "
        "op oo2WNyRzvhFkyWkjpkW2VeEXemFXudHHGENMmKmCDN8Me9HHn7y "
        "key edskRv2gYhN8iFj1ec8PjTX8zP1J3Lr59vFDeNnW56xQGxQn8e6pYv "
        "sig sigMzJ4GVAvXEd2RjsKGfG2H9QvqM74nRb3sB4N9Y4JQW8xYfG6Q2P"
    )
    redacted = redact_sensitive_text(msg)
    assert "tz1WMTY8n6gdR66rrGXWmvddmAH5WvJnspPA" not in redacted
    assert "oo2WNyRzvhFkyWkjpkW2VeEXemFXudHHGENMmKmCDN8Me9HHn7y" not in redacted
    assert "edskRv2gYhN8iFj1ec8PjTX8zP1J3Lr59vFDeNnW56xQGxQn8e6pYv" not in redacted
    assert "sigMzJ4GVAvXEd2RjsKGfG2H9QvqM74nRb3sB4N9Y4JQW8xYfG6Q2P" not in redacted
    assert "<tezos-address:redacted>" in redacted
    assert "<operation-hash:redacted>" in redacted
    assert "<secret-key:redacted>" in redacted
    assert "<signature:redacted>" in redacted


def test_logger_filter_redacts_direct_logger_messages():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    logger = get_logger()
    logger.addHandler(handler)
    try:
        logger.info(
            "Sending 0.01 XTZ from tz1hgj8R5trNi9PfszA8BHbQEHETrrqyfLkZ "
            "to tz1UnwM8q4myTakWcS8WKtkD79ZPwV3FJjyY "
            "oph oo2WNyRzvhFkyWkjpkW2VeEXemFXudHHGENMmKmCDN8Me9HHn7y"
        )
        out = stream.getvalue()
        assert "tz1hgj8R5trNi9PfszA8BHbQEHETrrqyfLkZ" not in out
        assert "tz1UnwM8q4myTakWcS8WKtkD79ZPwV3FJjyY" not in out
        assert "oo2WNyRzvhFkyWkjpkW2VeEXemFXudHHGENMmKmCDN8Me9HHn7y" not in out
        assert "<tezos-address:redacted>" in out
        assert "<operation-hash:redacted>" in out
    finally:
        logger.removeHandler(handler)
