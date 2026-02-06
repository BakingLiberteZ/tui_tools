from decimal import Decimal

import pytest

from sassy_wallet.core import tezos


def _mock_history_sources(
    monkeypatch,
    *,
    tx_items: list[dict],
    stake_items: list[dict] | None = None,
    unstake_items: list[dict] | None = None,
    staking_items: list[dict] | None = None,
    deleg_items: list[dict] | None = None,
) -> None:
    stake_items = stake_items or []
    unstake_items = unstake_items or []
    staking_items = staking_items or []
    deleg_items = deleg_items or []

    def _fake_urlopen(req, timeout=15, retries=3):
        url = req.full_url
        if "/v1/operations/transactions?" in url and "entrypoint=stake" in url:
            return stake_items
        if "/v1/operations/transactions?" in url and "entrypoint=unstake" in url:
            return unstake_items
        if "/v1/operations/staking?" in url:
            return staking_items
        if "/v1/operations/delegations?" in url:
            return deleg_items
        if "/v1/operations/transactions?" in url:
            return tx_items
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)
    monkeypatch.setattr(tezos, "get_baker_info", lambda rpc, baker_addr: {"alias": "Baker One"})
    tezos.invalidate_history_cache()


def test_get_xtz_history_dedupes_same_hash_across_tx_and_delegation(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[
            {
                "timestamp": "2026-02-06T12:00:00Z",
                "sender": {"address": address},
                "target": {"address": "tz1BAKER11111111111111111111111111111"},
                "amount": 0,
                "hash": "op_change_baker_shared",
                "metadata": {},
            },
            {
                "timestamp": "2026-02-06T11:59:00Z",
                "sender": {"address": address},
                "target": {"address": address},
                "amount": 10_000,
                "hash": "op_stake_unique",
                "parameter": {"entrypoint": "stake"},
                "metadata": {
                    "operation_result": {
                        "balance_updates": [{"kind": "staking", "delegate": "tz1BAKER11111111111111111111111111111"}]
                    }
                },
            },
        ],
        deleg_items=[
            {
                "timestamp": "2026-02-06T12:00:00Z",
                "sender": {"address": address},
                "newDelegate": {
                    "address": "tz1BAKER11111111111111111111111111111",
                    "alias": "Baker One",
                },
                "hash": "op_change_baker_shared",
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=3)
    hashes = [it.get("hash") for it in items]
    assert hashes.count("op_change_baker_shared") == 1
    assert "op_stake_unique" in hashes


def test_get_xtz_history_dedupes_duplicate_hashes_inside_delegations(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[
            {
                "timestamp": "2026-02-06T12:01:00Z",
                "sender": {"address": address},
                "target": {"address": address},
                "amount": 12_000,
                "hash": "op_stake_unique",
                "parameter": {"entrypoint": "stake"},
                "metadata": {},
            }
        ],
        deleg_items=[
            {
                "timestamp": "2026-02-06T12:00:00Z",
                "sender": {"address": address},
                "newDelegate": {"address": "tz1BAKER11111111111111111111111111111"},
                "hash": "op_change_baker_dup",
            },
            {
                "timestamp": "2026-02-06T12:00:00Z",
                "sender": {"address": address},
                "newDelegate": {"address": "tz1BAKER11111111111111111111111111111"},
                "hash": "op_change_baker_dup",
            },
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=3)
    hashes = [it.get("hash") for it in items]
    assert hashes.count("op_change_baker_dup") == 1
    assert "op_stake_unique" in hashes


@pytest.mark.parametrize(
    "tx_items,deleg_items,expected_hashes",
    [
        (
            [
                {
                    "timestamp": "2026-02-06T12:03:00Z",
                    "sender": {"address": "tz1SOURCE11111111111111111111111111111"},
                    "target": {"address": "tz1TARGET11111111111111111111111111111"},
                    "amount": 1000,
                    "hash": "op_send_unique",
                    "metadata": {},
                },
                {
                    "timestamp": "2026-02-06T12:02:00Z",
                    "sender": {"address": "tz1SOURCE11111111111111111111111111111"},
                    "target": {"address": "tz1BAKER11111111111111111111111111111"},
                    "amount": 0,
                    "hash": "op_change_shared",
                    "metadata": {},
                },
            ],
            [
                {
                    "timestamp": "2026-02-06T12:02:00Z",
                    "sender": {"address": "tz1SOURCE11111111111111111111111111111"},
                    "newDelegate": {"address": "tz1BAKER11111111111111111111111111111"},
                    "hash": "op_change_shared",
                }
            ],
            {"op_send_unique", "op_change_shared"},
        ),
        (
            [
                {
                    "timestamp": "2026-02-06T12:03:00Z",
                    "sender": {"address": "tz1SRC22222222222222222222222222222"},
                    "target": {"address": "tz1SRC22222222222222222222222222222"},
                    "amount": 5000,
                    "hash": "op_stake_unique_2",
                    "parameter": {"entrypoint": "stake"},
                    "metadata": {},
                }
            ],
            [
                {
                    "timestamp": "2026-02-06T12:04:00Z",
                    "sender": {"address": "tz1SRC22222222222222222222222222222"},
                    "newDelegate": {"address": "tz1BAKER11111111111111111111111111111"},
                    "hash": "op_change_unique_2",
                }
            ],
            {"op_stake_unique_2", "op_change_unique_2"},
        ),
    ],
)
def test_get_xtz_history_mixed_combinations_keep_unique_hashes(
    monkeypatch,
    tx_items,
    deleg_items,
    expected_hashes,
):
    address = tx_items[0]["sender"]["address"]
    _mock_history_sources(
        monkeypatch,
        tx_items=tx_items,
        deleg_items=deleg_items,
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    hashes = [it.get("hash") for it in items if it.get("hash")]
    assert len(hashes) == len(set(hashes))
    assert expected_hashes.issubset(set(hashes))


def test_get_xtz_history_includes_stake_from_staking_endpoint_when_legacy_tx_missing(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[
            {
                "timestamp": "2026-02-06T12:00:00Z",
                "sender": {"address": "tz1OTHER99999999999999999999999999999"},
                "target": {"address": address},
                "amount": 10_000,
                "hash": "op_recv_unique",
                "metadata": {},
            }
        ],
        stake_items=[],
        unstake_items=[],
        staking_items=[
            {
                "timestamp": "2026-02-06T11:59:00Z",
                "type": "stake",
                "sender": {"address": address},
                "delegate": {"address": "tz1BAKER11111111111111111111111111111", "alias": "Baker One"},
                "amount": 10_000,
                "hash": "op_stake_native",
                "metadata": {},
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    hashes = {it.get("hash") for it in items}
    assert "op_stake_native" in hashes


def test_get_xtz_history_dedupes_same_hash_between_staking_and_legacy_entries(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[],
        stake_items=[
            {
                "timestamp": "2026-02-06T12:00:00Z",
                "sender": {"address": address},
                "target": {"address": address},
                "amount": 10_000,
                "hash": "op_stake_shared",
                "parameter": {"entrypoint": "stake"},
                "metadata": {},
            }
        ],
        unstake_items=[],
        staking_items=[
            {
                "timestamp": "2026-02-06T12:00:00Z",
                "type": "stake",
                "sender": {"address": address},
                "delegate": {"address": "tz1BAKER11111111111111111111111111111"},
                "amount": 10_000,
                "hash": "op_stake_shared",
                "metadata": {},
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    hashes = [it.get("hash") for it in items if it.get("hash")]
    assert hashes.count("op_stake_shared") == 1


def test_get_xtz_history_prefers_delegation_over_staking_when_hash_is_shared(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[],
        stake_items=[],
        unstake_items=[],
        staking_items=[
            {
                "timestamp": "2026-02-06T12:05:00Z",
                "type": "unstake",
                "sender": {"address": address},
                "amount": 0,
                "hash": "op_change_shared_staking",
                "metadata": {},
            }
        ],
        deleg_items=[
            {
                "timestamp": "2026-02-06T12:05:00Z",
                "sender": {"address": address},
                "newDelegate": {"address": "tz1BAKER11111111111111111111111111111", "alias": "Baker One"},
                "hash": "op_change_shared_staking",
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    item = next(it for it in items if it.get("hash") == "op_change_shared_staking")
    assert item.get("kind") == "delegation"
    assert item.get("entrypoint") == "delegation"
    assert item.get("direction") in ("DEL", "UND")


def test_get_xtz_history_keeps_nonzero_staking_when_hash_is_shared_with_delegation(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[],
        stake_items=[],
        unstake_items=[],
        staking_items=[
            {
                "timestamp": "2026-02-06T12:05:30Z",
                "type": "stake",
                "sender": {"address": address},
                "amount": 25_000,
                "hash": "op_shared_nonzero_stake",
                "metadata": {},
            }
        ],
        deleg_items=[
            {
                "timestamp": "2026-02-06T12:05:30Z",
                "sender": {"address": address},
                "newDelegate": {"address": "tz1BAKER11111111111111111111111111111", "alias": "Baker One"},
                "hash": "op_shared_nonzero_stake",
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    same_hash = [it for it in items if it.get("hash") == "op_shared_nonzero_stake"]
    directions = {it.get("direction") for it in same_hash}
    assert "STK" in directions
    assert "DEL" in directions


def test_get_xtz_history_keeps_decimal_string_stake_amount_when_hash_is_shared(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[],
        stake_items=[
            {
                "timestamp": "2026-02-06T12:05:45Z",
                "sender": {"address": address},
                "target": {"address": address},
                "amount": "0.01",
                "hash": "op_shared_decimal_stake",
                "parameter": {"entrypoint": "stake"},
                "metadata": {},
            }
        ],
        unstake_items=[],
        staking_items=[],
        deleg_items=[
            {
                "timestamp": "2026-02-06T12:05:45Z",
                "sender": {"address": address},
                "newDelegate": {"address": "tz1BAKER11111111111111111111111111111", "alias": "Baker One"},
                "hash": "op_shared_decimal_stake",
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    same_hash = [it for it in items if it.get("hash") == "op_shared_decimal_stake"]
    stake_row = next(it for it in same_hash if it.get("direction") == "STK")
    assert stake_row.get("amount_xtz") == Decimal("0.01")
    assert any(it.get("direction") == "DEL" for it in same_hash)


def test_get_xtz_history_keeps_decimal_string_unstake_amount_from_staking_endpoint(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[],
        stake_items=[],
        unstake_items=[],
        staking_items=[
            {
                "timestamp": "2026-02-06T12:06:15Z",
                "type": "unstake",
                "sender": {"address": address},
                "amount": "0.02",
                "hash": "op_shared_decimal_unstake",
                "metadata": {},
            }
        ],
        deleg_items=[
            {
                "timestamp": "2026-02-06T12:06:15Z",
                "sender": {"address": address},
                "newDelegate": {"address": "tz1BAKER11111111111111111111111111111", "alias": "Baker One"},
                "hash": "op_shared_decimal_unstake",
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    same_hash = [it for it in items if it.get("hash") == "op_shared_decimal_unstake"]
    unstake_row = next(it for it in same_hash if it.get("direction") == "UST")
    assert unstake_row.get("amount_xtz") == Decimal("0.02")
    assert any(it.get("direction") == "DEL" for it in same_hash)


def test_get_xtz_history_prefers_delegation_over_zero_tx_when_hash_is_shared(monkeypatch):
    address = "tz1SOURCE11111111111111111111111111111"
    _mock_history_sources(
        monkeypatch,
        tx_items=[
            {
                "timestamp": "2026-02-06T12:06:00Z",
                "sender": {"address": address},
                "target": {"address": "tz1BAKER11111111111111111111111111111"},
                "amount": 0,
                "hash": "op_change_shared_tx",
                "metadata": {},
            }
        ],
        stake_items=[],
        unstake_items=[],
        staking_items=[],
        deleg_items=[
            {
                "timestamp": "2026-02-06T12:06:00Z",
                "sender": {"address": address},
                "newDelegate": {"address": "tz1BAKER11111111111111111111111111111", "alias": "Baker One"},
                "hash": "op_change_shared_tx",
            }
        ],
    )

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=10)
    item = next(it for it in items if it.get("hash") == "op_change_shared_tx")
    assert item.get("kind") == "delegation"
    assert item.get("entrypoint") == "delegation"
    assert item.get("direction") in ("DEL", "UND")
