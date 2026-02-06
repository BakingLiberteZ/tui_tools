from __future__ import annotations

import pytest

from sassy_wallet.ui.app import WalletApp


def test_with_rpc_fallback_retries_once_on_stale_branch_error() -> None:
    calls: list[str] = []

    class Dummy:
        def _ensure_working_rpc(self):
            return "https://rpc.new", True, True

    def _fn(rpc: str):
        calls.append(rpc)
        if len(calls) == 1:
            raise RuntimeError("async_injection_failed: block too old")
        return "ok"

    rpc_used, payload = WalletApp._with_rpc_fallback(
        Dummy(),
        action="send",
        rpc="https://rpc.old",
        fn=_fn,
    )

    assert rpc_used == "https://rpc.new"
    assert payload == "ok"
    assert calls == ["https://rpc.old", "https://rpc.new"]


def test_with_rpc_fallback_does_not_retry_when_selected_rpc_is_unchanged() -> None:
    calls: list[str] = []

    class Dummy:
        def _ensure_working_rpc(self):
            return "https://rpc.old", True, True

    def _fn(rpc: str):
        calls.append(rpc)
        raise RuntimeError("branch on either old block; too old")

    with pytest.raises(RuntimeError, match="too old"):
        WalletApp._with_rpc_fallback(
            Dummy(),
            action="send",
            rpc="https://rpc.old",
            fn=_fn,
        )

    assert calls == ["https://rpc.old"]


def test_with_rpc_fallback_does_not_trigger_on_non_stale_errors() -> None:
    ensure_calls = {"count": 0}

    class Dummy:
        def _ensure_working_rpc(self):
            ensure_calls["count"] += 1
            return "https://rpc.new", True, True

    def _fn(_rpc: str):
        raise RuntimeError("permission denied")

    with pytest.raises(RuntimeError, match="permission denied"):
        WalletApp._with_rpc_fallback(
            Dummy(),
            action="send",
            rpc="https://rpc.old",
            fn=_fn,
        )

    assert ensure_calls["count"] == 0
