import urllib.error
from email.message import Message

from sassy_wallet.core import tezos


def test_infer_is_staking_prefers_tzkt_staking_endpoint(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    addr = "tz1fakeaddressxxxxxxxxxxxxxxxxxxxxxxx"

    seen_urls: list[str] = []

    def _fake_urlopen(req, timeout=15, retries=3):
        url = req.full_url
        seen_urls.append(url)
        if "/v1/operations/staking?" in url and "type=stake" in url:
            return [{"level": 100, "type": "stake"}]
        if "/v1/operations/staking?" in url and "type=unstake" in url:
            return [{"level": 90, "type": "unstake"}]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)

    assert tezos.infer_is_staking(rpc, addr, force_refresh=True) is True
    assert any("/v1/operations/staking?" in u for u in seen_urls)


def test_infer_is_staking_falls_back_when_staking_endpoint_missing(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    addr = "tz1fakeaddressxxxxxxxxxxxxxxxxxxxxxxx"

    def _fake_urlopen(req, timeout=15, retries=3):
        url = req.full_url
        if "/v1/operations/staking?" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=Message(), fp=None)
        if "/v1/operations/transactions?" in url and "entrypoint=stake" in url:
            return [{"level": 50}]
        if "/v1/operations/transactions?" in url and "entrypoint=unstake" in url:
            return [{"level": 0}]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)

    assert tezos.infer_is_staking(rpc, addr, force_refresh=True) is True


def test_get_wallet_chain_state_marks_staking_active_when_unstaked_balance_present(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    addr = "tz1fakeaddressxxxxxxxxxxxxxxxxxxxxxxx"

    def _fake_get_account(_rpc, _addr, force_refresh=False):
        return {
            "address": addr,
            "balance": 123,
            "delegate": "tz1DELEGATE",
            "stakedBalance": 0,
            "unfinalizedUnstakeBalance": 42,
        }

    monkeypatch.setattr(tezos, "_tzkt_get_account", _fake_get_account)

    state = tezos.get_wallet_chain_state(rpc, addr, force_refresh=True)
    assert state["delegate"] == "tz1DELEGATE"
    assert state["staked_mutez"] == 0
    assert state["unstaked_mutez"] == 42
    assert state["staking_active"] is True
