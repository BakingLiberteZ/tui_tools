"""Tests for send flow override behavior."""

from decimal import Decimal

from sassy_wallet.core import tezos


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


def test_send_xtz_ignores_overrides_for_reveal(monkeypatch):
    recorder = []
    fail_counter = {"calls": 0}

    def _fake_get_client(rpc, key=None):
        return _FakeClient(recorder, fail_counter)

    monkeypatch.setattr(tezos, "get_client", _fake_get_client)

    result = tezos.send_xtz(
        "https://rpc.example",
        object(),
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
