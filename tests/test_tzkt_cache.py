"""Tests for TzKT account cache refresh behavior."""

from sassy_wallet.core import tezos


def test_tzkt_get_account_force_refresh_bypasses_cache(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    addr = "tz1fakeaddressxxxxxxxxxxxxxxxxxxxxxxx"
    url = f"{tezos._tzkt_base_from_rpc(rpc)}/v1/accounts/{addr}"

    # Make cache entry "fresh"
    monkeypatch.setattr(tezos.time, "time", lambda: 1000.0)
    tezos._tzkt_account_cache[url] = (1000.0, {"address": addr, "delegate": "tz1OLD", "balance": 0, "stakedBalance": 0})

    calls = {"n": 0}

    def _fake_urlopen(_req, timeout=15, retries=3):
        calls["n"] += 1
        return {"address": addr, "delegate": "tz1NEW", "balance": 1, "stakedBalance": 2}

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)

    # Without force_refresh: should hit cache, no network call
    data = tezos._tzkt_get_account(rpc, addr)
    assert calls["n"] == 0
    assert data.get("delegate") == "tz1OLD"

    # With force_refresh: should bypass cache and update it
    data2 = tezos._tzkt_get_account(rpc, addr, force_refresh=True)
    assert calls["n"] == 1
    assert data2.get("delegate") == "tz1NEW"

