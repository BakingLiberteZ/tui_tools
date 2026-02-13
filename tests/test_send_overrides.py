"""Tests for send flow override behavior."""

from decimal import Decimal
from typing import Any, cast

from sassy_wallet.core import tezos


class _FakeKey:
    def public_key_hash(self) -> str:
        return "tz1SOURCE11111111111111111111111111111"


class _FakeOp:
    def __init__(self, kind, recorder, fail_counter=None):
        self.kind = kind
        self.recorder = recorder
        self.fail_counter = fail_counter

    def autofill(self, **kwargs):
        self.recorder.append((self.kind, "autofill", kwargs))
        return self

    def fill(self, **kwargs):
        self.recorder.append((self.kind, "fill", kwargs))
        return self

    def sign(self):
        self.recorder.append((self.kind, "sign", {}))
        return self

    def inject(self, _async=False):
        self.recorder.append((self.kind, "inject", {}))
        if self.kind == "tx" and self.fail_counter is not None:
            self.fail_counter["calls"] += 1
            if self.fail_counter["calls"] == 1:
                raise RuntimeError("unrevealed manager key")
        return f"op_{self.kind}"


class _FakeClient:
    def __init__(self, recorder, fail_counter):
        self.recorder = recorder
        self.fail_counter = fail_counter

    def transaction(self, **kwargs):
        self.recorder.append(("tx", "build", kwargs))
        return _FakeOp("tx", self.recorder, self.fail_counter)

    def reveal(self, **kwargs):
        self.recorder.append(("reveal", "build", kwargs))
        return _FakeOp("reveal", self.recorder)

    def bulk(self, *ops):
        self.recorder.append(
            (
                "bulk",
                "build",
                {
                    "count": len(ops),
                    "kinds": [getattr(op, "kind", "?") for op in ops],
                },
            )
        )
        return _FakeOp("reveal_tx", self.recorder)


def test_send_xtz_batches_reveal_with_first_tx_when_unrevealed(monkeypatch):
    recorder = []
    fail_counter = None

    def _fake_get_client(rpc, key=None):
        return _FakeClient(recorder, fail_counter)

    monkeypatch.setattr(tezos, "get_client", _fake_get_client)
    monkeypatch.setattr(tezos, "is_revealed", lambda rpc, addr: False)

    result = tezos.send_xtz(
        "https://rpc.example",
        cast(Any, _FakeKey()),
        "tz1fakeaddressxxxxxxxxxxxxxxxxxxxxxxx",
        Decimal("1.0"),
        fee_mutez=1234,
        gas_limit=2222,
        storage_limit=3333,
    )

    assert result == "op_reveal_tx"

    bulk_build = [r for r in recorder if r[0] == "bulk" and r[1] == "build"]
    assert bulk_build
    assert bulk_build[0][2]["count"] == 2
    assert bulk_build[0][2]["kinds"] == ["reveal", "tx"]

    reveal_build = [r for r in recorder if r[0] == "reveal" and r[1] == "build"]
    assert reveal_build
    assert reveal_build[0][2]["fee"] == 1300
    assert reveal_build[0][2]["gas_limit"] == 10000
    assert reveal_build[0][2]["storage_limit"] == 0

    tx_build = [r for r in recorder if r[0] == "tx" and r[1] == "build"]
    assert tx_build
    assert tx_build[0][2]["fee"] == 1234
    assert tx_build[0][2]["gas_limit"] == 2222
    assert tx_build[0][2]["storage_limit"] == 3333

    bulk_autofill = [r for r in recorder if r[0] == "reveal_tx" and r[1] == "autofill"]
    assert bulk_autofill
    assert bulk_autofill[0][2] == {}


def test_send_xtz_ignores_overrides_for_reveal_in_legacy_fallback(monkeypatch):
    recorder = []
    fail_counter = {"calls": 0}

    def _fake_get_client(rpc, key=None):
        return _FakeClient(recorder, fail_counter)

    monkeypatch.setattr(tezos, "get_client", _fake_get_client)
    monkeypatch.setattr(tezos, "is_revealed", lambda rpc, addr: True)

    result = tezos.send_xtz(
        "https://rpc.example",
        cast(Any, _FakeKey()),
        "tz1fakeaddressxxxxxxxxxxxxxxxxxxxxxxx",
        Decimal("1.0"),
        fee_mutez=1234,
        gas_limit=2222,
        storage_limit=3333,
    )

    assert result == "op_tx"

    reveal_autofill = [r for r in recorder if r[0] == "reveal" and r[1] == "autofill"]
    assert reveal_autofill
    assert reveal_autofill[0][2] == {}

    tx_autofill = [r for r in recorder if r[0] == "tx" and r[1] == "autofill"]
    assert any(r[2].get("fee") == 1234 for r in tx_autofill)
