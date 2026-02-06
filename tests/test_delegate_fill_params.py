"""Tests for delegation fill behavior with partial overrides."""

from typing import Any, cast

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

    oph = tezos.delegate_to_baker("https://rpc.example", cast(Any, _Key()), "tz1NEW", fee_mutez=500)
    assert oph == "op_hash"

    fill_calls = [c for c in recorder if c[0] == "fill"]
    assert fill_calls, "expected fill() to be called"
    kwargs = fill_calls[0][1]
    # Fee override present, and limits must be included (copied from autofill)
    assert kwargs.get("fee") == 500
    assert kwargs.get("gas_limit") == 169
    assert kwargs.get("storage_limit") == 0


class _GasFallbackOp:
    def __init__(self, recorder):
        self.recorder = recorder
        self._fee = 500
        self._gas = 169
        self._storage = 0

    def autofill(self, **kwargs):
        self.recorder.append(("autofill", kwargs))
        if kwargs.get("fee") is not None:
            self._fee = int(kwargs["fee"])
        if kwargs.get("gas_limit") is not None:
            self._gas = int(kwargs["gas_limit"])
        if kwargs.get("storage_limit") is not None:
            self._storage = int(kwargs["storage_limit"])
        return self

    def json_payload(self):
        return [{
            "contents": [{
                "kind": "delegation",
                "delegate": "tz1NEW",
                "gas_limit": str(self._gas),
                "storage_limit": str(self._storage),
            }]
        }]

    def fill(self, **kwargs):
        self.recorder.append(("fill", kwargs))
        if kwargs.get("fee") is not None:
            self._fee = int(kwargs["fee"])
        if kwargs.get("gas_limit") is not None:
            self._gas = int(kwargs["gas_limit"])
        if kwargs.get("storage_limit") is not None:
            self._storage = int(kwargs["storage_limit"])
        return self

    def sign(self):
        self.recorder.append(("sign", {}))
        return self

    def inject(self):
        self.recorder.append(("inject", {"fee": self._fee, "gas_limit": self._gas, "storage_limit": self._storage}))
        if self._gas < 1000000:
            raise RuntimeError("gas_exhausted.operation")
        return "op_safe"


class _GasFallbackClient:
    def __init__(self, recorder):
        self.recorder = recorder

    def delegation(self, baker_address):
        assert baker_address == "tz1NEW"
        self.recorder.append(("delegation", {"delegate": baker_address}))
        return _GasFallbackOp(self.recorder)


class _AlwaysGasExhaustedOp(_GasFallbackOp):
    def inject(self):
        self.recorder.append(("inject", {"fee": self._fee, "gas_limit": self._gas, "storage_limit": self._storage}))
        raise RuntimeError("gas_exhausted.operation")


class _AlwaysGasExhaustedClient:
    def __init__(self, recorder):
        self.recorder = recorder

    def delegation(self, baker_address):
        assert baker_address == "tz1NEW"
        self.recorder.append(("delegation", {"delegate": baker_address}))
        return _AlwaysGasExhaustedOp(self.recorder)


def test_delegate_to_baker_gas_exhausted_retries_with_safe_limits(monkeypatch):
    recorder = []

    def _fake_using(*, shell, key):
        return _GasFallbackClient(recorder)

    monkeypatch.setattr(tezos, "pytezos", type("P", (), {"using": staticmethod(_fake_using)}))
    monkeypatch.setattr(tezos, "check_pending_operations", lambda rpc, addr: None)
    monkeypatch.setattr(tezos, "is_wallet_revealed", lambda rpc, addr: True)

    class _Key:
        def public_key_hash(self):
            return "tz1SRC"

    oph = tezos.delegate_to_baker(
        "https://rpc.example",
        cast(Any, _Key()),
        "tz1NEW",
        fee_mutez=500,
        gas_limit=1000,
        storage_limit=0,
    )
    assert oph == "op_safe"

    fill_calls = [c[1] for c in recorder if c[0] == "fill"]
    assert fill_calls
    assert any(c.get("fee") == 8000 for c in fill_calls)
    assert any(c.get("gas_limit") == 1040000 for c in fill_calls)

    inject_calls = [c[1] for c in recorder if c[0] == "inject"]
    assert inject_calls
    assert inject_calls[-1].get("gas_limit") == 1040000
    assert inject_calls[-1].get("fee") == 8000


def test_delegate_to_baker_gas_exhausted_falls_back_to_rpc_forge(monkeypatch):
    recorder = []
    posted_payload = {}

    def _fake_using(*, shell, key):
        return _AlwaysGasExhaustedClient(recorder)

    class _FakeHead:
        @staticmethod
        def hash():
            return "BLfakebranch"

    class _FakeShell:
        head = _FakeHead()

    class _FakeClient:
        shell = _FakeShell()

    class _FakeResponse:
        status_code = 200
        text = '"deadbeef"'

    monkeypatch.setattr(tezos, "pytezos", type("P", (), {"using": staticmethod(_fake_using)}))
    monkeypatch.setattr(tezos, "check_pending_operations", lambda rpc, addr: None)
    monkeypatch.setattr(tezos, "is_wallet_revealed", lambda rpc, addr: True)
    monkeypatch.setattr(tezos, "get_client", lambda rpc, key=None: _FakeClient())
    monkeypatch.setattr(tezos, "get_counter", lambda rpc, addr: 42)
    def _fake_post(*args, **kwargs):
        posted_payload["payload"] = kwargs.get("json") or {}
        return _FakeResponse()

    monkeypatch.setattr(tezos.requests, "post", _fake_post)
    monkeypatch.setattr(tezos, "sign_and_inject_from_rpc_forge", lambda rpc, key, forged: "op_forged")

    class _Key:
        def public_key_hash(self):
            return "tz1SRC"

    oph = tezos.delegate_to_baker(
        "https://rpc.example",
        cast(Any, _Key()),
        "tz1NEW",
        fee_mutez=500,
        gas_limit=1000,
        storage_limit=0,
    )
    assert oph == "op_forged"
    contents = posted_payload["payload"]["contents"][0]
    assert contents["fee"] == "8000"
    assert contents["gas_limit"] == "1040000"


class _AutofillGasExhaustedOp:
    def __init__(self, recorder):
        self.recorder = recorder

    def autofill(self, **kwargs):
        self.recorder.append(("autofill", kwargs))
        raise RuntimeError("gas_exhausted.operation")


class _AutofillGasExhaustedClient:
    def __init__(self, recorder):
        self.recorder = recorder

    def delegation(self, baker_address):
        assert baker_address == "tz1NEW"
        self.recorder.append(("delegation", {"delegate": baker_address}))
        return _AutofillGasExhaustedOp(self.recorder)


def test_delegate_to_baker_gas_exhausted_on_autofill_falls_back_to_rpc_forge(monkeypatch):
    recorder = []

    def _fake_using(*, shell, key):
        return _AutofillGasExhaustedClient(recorder)

    class _FakeHead:
        @staticmethod
        def hash():
            return "BLfakebranch"

    class _FakeShell:
        head = _FakeHead()

    class _FakeClient:
        shell = _FakeShell()

    class _FakeResponse:
        status_code = 200
        text = '"deadbeef"'

    monkeypatch.setattr(tezos, "pytezos", type("P", (), {"using": staticmethod(_fake_using)}))
    monkeypatch.setattr(tezos, "check_pending_operations", lambda rpc, addr: None)
    monkeypatch.setattr(tezos, "is_wallet_revealed", lambda rpc, addr: True)
    monkeypatch.setattr(tezos, "get_client", lambda rpc, key=None: _FakeClient())
    monkeypatch.setattr(tezos, "get_counter", lambda rpc, addr: 42)
    monkeypatch.setattr(tezos.requests, "post", lambda *args, **kwargs: _FakeResponse())
    monkeypatch.setattr(tezos, "sign_and_inject_from_rpc_forge", lambda rpc, key, forged: "op_forged_autofill")

    class _Key:
        def public_key_hash(self):
            return "tz1SRC"

    oph = tezos.delegate_to_baker(
        "https://rpc.example",
        cast(Any, _Key()),
        "tz1NEW",
        fee_mutez=500,
        gas_limit=1000,
        storage_limit=0,
    )
    assert oph == "op_forged_autofill"


def test_delegate_to_baker_forge_fallback_caps_fee_to_spendable_balance(monkeypatch):
    recorder = []
    posted_payload = {}

    def _fake_using(*, shell, key):
        return _AutofillGasExhaustedClient(recorder)

    class _FakeHead:
        @staticmethod
        def hash():
            return "BLfakebranch"

    class _FakeShell:
        head = _FakeHead()

    class _FakeClient:
        shell = _FakeShell()

    class _FakeResponse:
        status_code = 200
        text = '"deadbeef"'

    def _fake_post(*args, **kwargs):
        posted_payload["payload"] = kwargs.get("json") or {}
        return _FakeResponse()

    monkeypatch.setattr(tezos, "pytezos", type("P", (), {"using": staticmethod(_fake_using)}))
    monkeypatch.setattr(tezos, "check_pending_operations", lambda rpc, addr: None)
    monkeypatch.setattr(tezos, "is_wallet_revealed", lambda rpc, addr: True)
    monkeypatch.setattr(tezos, "get_client", lambda rpc, key=None: _FakeClient())
    monkeypatch.setattr(tezos, "get_counter", lambda rpc, addr: 42)
    monkeypatch.setattr(tezos, "get_balance_mutez", lambda rpc, addr: 7000)
    monkeypatch.setattr(tezos.requests, "post", _fake_post)
    monkeypatch.setattr(tezos, "sign_and_inject_from_rpc_forge", lambda rpc, key, forged: "op_capped")

    class _Key:
        def public_key_hash(self):
            return "tz1SRC"

    oph = tezos.delegate_to_baker(
        "https://rpc.example",
        cast(Any, _Key()),
        "tz1NEW",
        fee_mutez=500,
        gas_limit=1000,
        storage_limit=0,
    )
    assert oph == "op_capped"
    contents = posted_payload["payload"]["contents"][0]
    assert contents["fee"] == "6500"
    assert contents["gas_limit"] == "1040000"


def test_estimate_delegation_uses_high_profile_when_stake_context_detected(monkeypatch):
    monkeypatch.setattr(tezos, "is_revealed", lambda rpc, addr: True)
    monkeypatch.setattr(
        tezos,
        "get_wallet_chain_state",
        lambda rpc, addr, force_refresh=False, prefer_rpc=True: {
            "staked_mutez": 5_000_000,
            "unstaked_mutez": 0,
            "staking_active": True,
        },
    )

    est = tezos.estimate_delegation("https://rpc.example", "tz1SRC", "tz1NEW")
    assert est["tx"]["fee_mutez"] == 8000
    assert est["tx"]["gas_limit"] == 30000
    assert est["fee_options"]["priority"]["gas_limit"] == 60000


def test_estimate_delegation_keeps_low_profile_without_stake_context(monkeypatch):
    monkeypatch.setattr(tezos, "is_revealed", lambda rpc, addr: True)
    monkeypatch.setattr(
        tezos,
        "get_wallet_chain_state",
        lambda rpc, addr, force_refresh=False, prefer_rpc=True: {
            "staked_mutez": 0,
            "unstaked_mutez": 0,
            "staking_active": False,
        },
    )

    est = tezos.estimate_delegation("https://rpc.example", "tz1SRC", "tz1NEW")
    assert est["tx"]["fee_mutez"] == 800
    assert est["tx"]["gas_limit"] == 1000
