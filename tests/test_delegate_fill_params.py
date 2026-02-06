"""Tests for delegation fill behavior with partial overrides."""

from sassy_wallet.core import tezos


class _FakeOp:
    def __init__(self, recorder):
        self.recorder = recorder
        self._gas = 169
        self._storage = 0

    def autofill(self):
        self.recorder.append(("autofill", {}))
        return self

    def json_payload(self):
        return [{"contents": [{"kind": "delegation", "delegate": "tz1NEW", "gas_limit": str(self._gas), "storage_limit": str(self._storage)}]}]

    def fill(self, **kwargs):
        self.recorder.append(("fill", kwargs))
        return self

    def sign(self):
        self.recorder.append(("sign", {}))
        return self

    def inject(self):
        self.recorder.append(("inject", {}))
        return "op_hash"


class _FakeClient:
    def __init__(self, recorder):
        self.recorder = recorder

    def delegation(self, baker_address):
        # Assert baker address passed correctly
        assert baker_address == "tz1NEW"
        self.recorder.append(("delegation", {"delegate": baker_address}))
        return _FakeOp(self.recorder)


def test_delegate_to_baker_fill_includes_autofilled_limits(monkeypatch):
    recorder = []

    def _fake_using(*, shell, key):
        return _FakeClient(recorder)

    monkeypatch.setattr(tezos, "pytezos", type("P", (), {"using": staticmethod(_fake_using)}))
    monkeypatch.setattr(tezos, "check_pending_operations", lambda rpc, addr: None)
    monkeypatch.setattr(tezos, "is_wallet_revealed", lambda rpc, addr: True)

    class _Key:
        def public_key_hash(self):
            return "tz1SRC"

    oph = tezos.delegate_to_baker("https://rpc.example", _Key(), "tz1NEW", fee_mutez=500)
    assert oph == "op_hash"

    fill_calls = [c for c in recorder if c[0] == "fill"]
    assert fill_calls, "expected fill() to be called"
    kwargs = fill_calls[0][1]
    # Fee override present, and limits must be included (copied from autofill)
    assert kwargs.get("fee") == 500
    assert kwargs.get("gas_limit") == 169
    assert kwargs.get("storage_limit") == 0
