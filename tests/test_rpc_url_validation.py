"""Tests for RPC/URL validation hardening."""

import urllib.request

import pytest

from sassy_wallet.core import tezos
from sassy_wallet.core.validation import normalize_https_url, normalize_rpc_url
from sassy_wallet.ui import app as ui_app


def test_normalize_rpc_url_strips_trailing_slash() -> None:
    assert normalize_rpc_url(" https://rpc.tzkt.io/mainnet/ ") == "https://rpc.tzkt.io/mainnet"


def test_normalize_rpc_url_rejects_non_https() -> None:
    with pytest.raises(ValueError):
        normalize_rpc_url("file:///tmp/rpc")

    with pytest.raises(ValueError):
        normalize_rpc_url("http://rpc.tzkt.io/mainnet")


def test_normalize_https_url_rejects_credentials() -> None:
    with pytest.raises(ValueError):
        normalize_https_url("https://user:pass@example.com/api")


def test_choose_working_rpc_skips_invalid_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui_app, "_MAINNET_RPC_CANDIDATES", ["file:///tmp/rpc", "https://rpc.tzkt.io/mainnet"])
    monkeypatch.setattr(ui_app, "_GHOSTNET_RPC_CANDIDATES", ["https://rpc.tzkt.io/ghostnet"])
    monkeypatch.setattr(ui_app, "rpc_supports_send", lambda rpc: rpc == "https://rpc.tzkt.io/mainnet")
    monkeypatch.setattr(ui_app, "rpc_supports_simulation", lambda rpc: rpc == "https://rpc.tzkt.io/mainnet")

    rpc, can_send, can_sim = ui_app.choose_working_rpc("file:///tmp/rpc")

    assert rpc == "https://rpc.tzkt.io/mainnet"
    assert can_send is True
    assert can_sim is True


def test_wallet_app_falls_back_to_safe_default_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    saved_store: dict = {}

    monkeypatch.setattr(ui_app, "load_store", lambda: {"rpc": "file:///tmp/rpc", "accounts": []})
    monkeypatch.setattr(ui_app, "list_accounts", lambda _store: [])
    monkeypatch.setattr(ui_app, "save_store", lambda data: saved_store.update(data))

    app = ui_app.WalletApp()
    assert app.rpc == ui_app.Config.RPC_DEFAULT_GHOSTNET
    assert saved_store.get("rpc") == ui_app.Config.RPC_DEFAULT_GHOSTNET


def test_http_code_blocks_unsafe_scheme_without_urlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}

    def _fake_urlopen(*_args, **_kwargs):
        called["count"] += 1
        raise AssertionError("urlopen should not be called for unsafe URLs")

    monkeypatch.setattr(ui_app.urllib.request, "urlopen", _fake_urlopen)

    status = ui_app._http_code("file:///tmp/rpc")
    assert status == 0
    assert called["count"] == 0


def test_tezos_urlopen_helpers_reject_non_https_urls() -> None:
    req = urllib.request.Request("file:///tmp/rpc")

    with pytest.raises(RuntimeError):
        tezos._urlopen_json_with_retries(req, timeout=1, retries=1)

    with pytest.raises(RuntimeError):
        tezos._urlopen_bytes_with_retries(req, timeout=1, retries=1)
