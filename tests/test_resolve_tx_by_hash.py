from sassy_wallet.core import tezos


def test_resolve_tx_by_hash_falls_back_to_staking_endpoint_for_stake(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    address = "tz1SOURCE11111111111111111111111111111"
    oph = "op_stake_via_staking_endpoint"

    def _fake_urlopen(req, timeout=15, retries=2):
        url = req.full_url
        if "/v1/operations/transactions?" in url and f"hash={oph}" in url:
            return []
        if "/v1/operations/staking?" in url and f"hash={oph}" in url:
            return [
                {
                    "hash": oph,
                    "timestamp": "2026-02-06T12:10:00Z",
                    "type": "stake",
                    "sender": {"address": address},
                    "delegate": {"address": "tz1BAKER11111111111111111111111111111"},
                    "amount": 10_000,
                    "status": "applied",
                    "metadata": {},
                }
            ]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)
    monkeypatch.setattr(tezos, "get_baker_info", lambda rpc, baker_addr: {"alias": "Baker One"})

    item = tezos.resolve_tx_by_hash(rpc, address, oph)

    assert item is not None
    assert item.get("hash") == oph
    assert item.get("direction") == "STK"
    assert item.get("entrypoint") == "stake"
    assert item.get("kind") == "transaction"


def test_resolve_tx_by_hash_handles_staking_action_field_for_stake(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    address = "tz1SOURCE11111111111111111111111111111"
    oph = "op_stake_via_staking_action"

    def _fake_urlopen(req, timeout=15, retries=2):
        url = req.full_url
        if "/v1/operations/transactions?" in url and f"hash={oph}" in url:
            return []
        if "/v1/operations/staking?" in url and f"hash={oph}" in url:
            return [
                {
                    "hash": oph,
                    "timestamp": "2026-02-06T12:10:00Z",
                    "type": "staking",
                    "action": "stake",
                    "sender": {"address": address},
                    "staker": {"address": address},
                    "baker": {"address": "tz1BAKER11111111111111111111111111111"},
                    "amount": 10_000,
                    "status": "applied",
                    "metadata": {},
                }
            ]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)
    monkeypatch.setattr(tezos, "get_baker_info", lambda rpc, baker_addr: {"alias": "Baker One"})

    item = tezos.resolve_tx_by_hash(rpc, address, oph)

    assert item is not None
    assert item.get("hash") == oph
    assert item.get("direction") == "STK"
    assert item.get("entrypoint") == "stake"
    assert item.get("kind") == "transaction"


def test_resolve_tx_by_hash_falls_back_to_staking_endpoint_for_unstake(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    address = "tz1SOURCE11111111111111111111111111111"
    oph = "op_unstake_via_staking_endpoint"

    def _fake_urlopen(req, timeout=15, retries=2):
        url = req.full_url
        if "/v1/operations/transactions?" in url and f"hash={oph}" in url:
            return []
        if "/v1/operations/staking?" in url and f"hash={oph}" in url:
            return [
                {
                    "hash": oph,
                    "timestamp": "2026-02-06T12:11:00Z",
                    "type": "unstake",
                    "sender": {"address": address},
                    "delegate": {"address": "tz1BAKER11111111111111111111111111111"},
                    "amount": 20_000,
                    "status": "applied",
                    "metadata": {},
                }
            ]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)
    monkeypatch.setattr(tezos, "get_baker_info", lambda rpc, baker_addr: {"alias": "Baker One"})

    item = tezos.resolve_tx_by_hash(rpc, address, oph)

    assert item is not None
    assert item.get("hash") == oph
    assert item.get("direction") == "UST"
    assert item.get("entrypoint") == "unstake"
    assert item.get("kind") == "transaction"


def test_resolve_tx_by_hash_handles_staking_action_field_for_unstake(monkeypatch):
    rpc = "https://rpc.tzkt.io/mainnet"
    address = "tz1SOURCE11111111111111111111111111111"
    oph = "op_unstake_via_staking_action"

    def _fake_urlopen(req, timeout=15, retries=2):
        url = req.full_url
        if "/v1/operations/transactions?" in url and f"hash={oph}" in url:
            return []
        if "/v1/operations/staking?" in url and f"hash={oph}" in url:
            return [
                {
                    "hash": oph,
                    "timestamp": "2026-02-06T12:11:00Z",
                    "type": "staking",
                    "action": "unstake",
                    "sender": {"address": address},
                    "staker": {"address": address},
                    "baker": {"address": "tz1BAKER11111111111111111111111111111"},
                    "amount": 20_000,
                    "status": "applied",
                    "metadata": {},
                }
            ]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)
    monkeypatch.setattr(tezos, "get_baker_info", lambda rpc, baker_addr: {"alias": "Baker One"})

    item = tezos.resolve_tx_by_hash(rpc, address, oph)

    assert item is not None
    assert item.get("hash") == oph
    assert item.get("direction") == "UST"
    assert item.get("entrypoint") == "unstake"
    assert item.get("kind") == "transaction"
