"""Tests for bounded cache helper in tezos core."""

from sassy_wallet.core.tezos import _cache_set_bounded


def test_cache_set_bounded_evicts_oldest():
    cache = {
        "a": (1.0, {}),
        "b": (2.0, {}),
    }
    _cache_set_bounded(cache, "c", (3.0, {}), max_size=2)
    assert "a" not in cache
    assert set(cache.keys()) == {"b", "c"}
