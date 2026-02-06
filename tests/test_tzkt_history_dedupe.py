import pytest

from sassy_wallet.core import tezos


def _mock_history_sources(
    monkeypatch,
    *,
    tx_items: list[dict],
    stake_items: list[dict] | None = None,
    unstake_items: list[dict] | None = None,
    deleg_items: list[dict] | None = None,
) -> None:
    stake_items = stake_items or []
    unstake_items = unstake_items or []
    deleg_items = deleg_items or []

    def _fake_urlopen(req, timeout=15, retries=3):
        url = req.full_url
        if "/v1/operations/transactions?" in url and "entrypoint=stake" in url:
            return stake_items
        if "/v1/operations/transactions?" in url and "entrypoint=unstake" in url:
            return unstake_items
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
