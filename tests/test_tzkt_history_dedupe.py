from sassy_wallet.core import tezos


def test_get_xtz_history_dedupes_same_hash_across_tx_and_delegation(monkeypatch):
    """
    Regression: if TzKT returns the same operation hash in both transactions
    and delegations endpoints, history must keep a single row for that hash.

    Without dedupe, duplicated change-baker rows can push stake rows out of
    the visible limit window.
    """
    address = "tz1SOURCE11111111111111111111111111111"

    tx_items = [
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
                    "balance_updates": [
                        {"kind": "staking", "delegate": "tz1BAKER11111111111111111111111111111"},
                    ]
                }
            },
        },
    ]
    deleg_items = [
        {
            "timestamp": "2026-02-06T12:00:00Z",
            "sender": {"address": address},
            "newDelegate": {
                "address": "tz1BAKER11111111111111111111111111111",
                "alias": "Baker One",
            },
            "hash": "op_change_baker_shared",
        }
    ]

    def _fake_urlopen(req, timeout=15, retries=3):
        url = req.full_url
        if "/v1/operations/transactions?" in url and "entrypoint=stake" in url:
            return []
        if "/v1/operations/transactions?" in url and "entrypoint=unstake" in url:
            return []
        if "/v1/operations/delegations?" in url:
            return deleg_items
        if "/v1/operations/transactions?" in url:
            return tx_items
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(tezos, "_urlopen_json_with_retries", _fake_urlopen)
    monkeypatch.setattr(tezos, "get_baker_info", lambda rpc, baker_addr: {"alias": "Baker One"})
    tezos.invalidate_history_cache()

    items = tezos.get_xtz_history("https://rpc.tzkt.io/mainnet", address, limit=2)

    hashes = [it.get("hash") for it in items]
    assert hashes.count("op_change_baker_shared") == 1
    assert "op_stake_unique" in hashes
