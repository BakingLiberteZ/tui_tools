from decimal import Decimal
from threading import RLock
from types import SimpleNamespace

import pytest

from sassy_wallet.ui.app import WalletApp


def test_add_pending_tx_scopes_history_to_source_wallet_after_selection_switch():
    """Pending shimmer row must render on the source wallet, not the previously selected one."""
    source_addr = "tz1SOURCE11111111111111111111111111111"
    other_addr = "tz1OTHER22222222222222222222222222222"

    source_history = [
        {"hash": "op_source_old", "status": "CONFIRMED", "ts": "2026-02-06T00:00:00Z"}
    ]
    other_history = [
        {"hash": "op_other_old", "status": "CONFIRMED", "ts": "2026-02-06T00:00:00Z"}
    ]

    class Dummy:
        pass

    app = Dummy()
    app._pending_ops_lock = RLock()
    app._pending_ops = {}
    app._history_cache_lock = RLock()
    app.history_limit = 20
    app.history_cache = {
        (source_addr, app.history_limit): list(source_history),
        (other_addr, app.history_limit): list(other_history),
    }
    app.selected = SimpleNamespace(address=other_addr)
    app._history_loaded_addr = other_addr
    app.history_items = list(other_history)

    app._persist_pending_ops = lambda: None
    app._set_op_entrypoint_override = lambda oph, entrypoint: None
    app._history_cache_key = lambda address: (address, app.history_limit)
    app._cache_visible_history_for_address = lambda address: WalletApp._cache_visible_history_for_address(app, address)

    def _select_account_by_address(address: str) -> None:
        app.selected = SimpleNamespace(address=address)

    app._select_account_by_address = _select_account_by_address

    merge_calls: list[tuple[list[dict], str, bool]] = []

    def _merge_history_with_pending(base_items, address, resolve_pending=False):
        merge_calls.append((list(base_items), address, resolve_pending))
        pending_items = [
            dict(item) for item in app._pending_ops.values() if item.get("address") == address
        ]
        return list(base_items) + pending_items

    app._merge_history_with_pending = _merge_history_with_pending

    rendered_items: list[dict] = []

    def _render_history(items):
        rendered_items[:] = list(items)
        app.history_items = list(items)

    app._render_history = _render_history
    app._set_history_loaded_addr = lambda address: setattr(app, "_history_loaded_addr", address)

    blink_calls: list[bool] = []
    app._set_pending_blink = lambda active: blink_calls.append(active)

    timer_calls: list[float] = []
    app.set_timer = lambda delay, cb: timer_calls.append(delay)

    WalletApp._add_pending_tx(
        app,
        address=source_addr,
        oph="op_new_stake",
        direction="STK",
        amount_xtz=Decimal("0.01"),
        counterparty="The baker",
        entrypoint="stake",
        processing_seconds=30.0,
        select_wallet=True,
    )

    assert app.selected.address == source_addr
    assert merge_calls, "Expected merge call for pending rendering."
    assert merge_calls[0][0] == source_history
    assert merge_calls[0][0] != other_history
    assert app._history_loaded_addr == source_addr
    assert any(item.get("hash") == "op_new_stake" for item in rendered_items)
    assert all(item.get("hash") != "op_other_old" for item in rendered_items)
    assert True in blink_calls
    assert timer_calls, "Expected pending verification/finalization timers."


def test_add_pending_tx_keeps_previous_stake_row_when_unstake_is_added():
    """Adding a new unstake pending row must not drop the previously shown stake row."""
    source_addr = "tz1SOURCE11111111111111111111111111111"

    class Dummy:
        pass

    app = Dummy()
    app._pending_ops_lock = RLock()
    app._pending_ops = {}
    app._history_cache_lock = RLock()
    app.history_limit = 20
    app.selected = SimpleNamespace(address=source_addr)
    app._history_loaded_addr = source_addr

    # Simulate that stake was already visible (fresh UI state).
    visible_stake = {"hash": "op_stake_1", "status": "CONFIRMED", "ts": "2026-02-06T00:00:00Z"}
    app.history_items = [dict(visible_stake)]
    app.history_cache = {}

    app._persist_pending_ops = lambda: None
    app._set_op_entrypoint_override = lambda oph, entrypoint: None
    app._history_cache_key = lambda address: (address, app.history_limit)
    app._cache_visible_history_for_address = lambda address: WalletApp._cache_visible_history_for_address(app, address)
    app._select_account_by_address = lambda address: None

    def _merge_history_with_pending(base_items, address, resolve_pending=False):
        pending_items = [
            dict(item) for item in app._pending_ops.values() if item.get("address") == address
        ]
        return list(base_items) + pending_items

    app._merge_history_with_pending = _merge_history_with_pending
    app._set_history_loaded_addr = lambda address: setattr(app, "_history_loaded_addr", address)
    app._set_pending_blink = lambda active: None
    app.set_timer = lambda delay, cb: None

    def _render_history(items):
        app.history_items = list(items)

    app._render_history = _render_history

    # 1) Add stake pending row and render it.
    WalletApp._add_pending_tx(
        app,
        address=source_addr,
        oph="op_stake_2",
        direction="STK",
        amount_xtz=Decimal("0.01"),
        counterparty="The baker",
        entrypoint="stake",
        processing_seconds=30.0,
        select_wallet=True,
    )
    assert any(it.get("hash") == "op_stake_1" for it in app.history_items)
    assert any(it.get("hash") == "op_stake_2" for it in app.history_items)

    # Simulate transient mismatch so next add would rely on cache path if not synced.
    app._history_loaded_addr = "tz1OTHER99999999999999999999999999999"

    # 2) Add unstake pending row. Previous stake rows must remain visible.
    WalletApp._add_pending_tx(
        app,
        address=source_addr,
        oph="op_unstake_1",
        direction="UST",
        amount_xtz=Decimal("0.01"),
        counterparty="The baker",
        entrypoint="unstake",
        processing_seconds=30.0,
        select_wallet=True,
    )

    hashes = [it.get("hash") for it in app.history_items]
    assert "op_stake_1" in hashes
    assert "op_stake_2" in hashes
    assert "op_unstake_1" in hashes


@pytest.mark.parametrize(
    "direction,entrypoint,op_hash",
    [
        ("OUT", "", "op_send_1"),
        ("STK", "stake", "op_stake_1"),
        ("UST", "unstake", "op_unstake_1"),
        ("DEL", "delegation", "op_delegate_1"),
        ("DEL", "change_baker", "op_change_baker_1"),
    ],
)
def test_add_pending_tx_keeps_existing_history_for_all_operation_types(direction, entrypoint, op_hash):
    """Any new pending op must append/merge without dropping already visible rows."""
    source_addr = "tz1SOURCE11111111111111111111111111111"

    class Dummy:
        pass

    app = Dummy()
    app._pending_ops_lock = RLock()
    app._pending_ops = {}
    app._history_cache_lock = RLock()
    app.history_limit = 20
    app.selected = SimpleNamespace(address=source_addr)
    app._history_loaded_addr = source_addr
    app.history_items = [{"hash": "op_existing", "status": "CONFIRMED", "ts": "2026-02-06T00:00:00Z"}]
    app.history_cache = {}

    app._persist_pending_ops = lambda: None
    app._set_op_entrypoint_override = lambda oph, ep: None
    app._history_cache_key = lambda address: (address, app.history_limit)
    app._cache_visible_history_for_address = lambda address: WalletApp._cache_visible_history_for_address(app, address)
    app._select_account_by_address = lambda address: None
    app._set_history_loaded_addr = lambda address: setattr(app, "_history_loaded_addr", address)
    app._set_pending_blink = lambda active: None
    app.set_timer = lambda delay, cb: None

    def _merge_history_with_pending(base_items, address, resolve_pending=False):
        pending_items = [dict(item) for item in app._pending_ops.values() if item.get("address") == address]
        return list(base_items) + pending_items

    app._merge_history_with_pending = _merge_history_with_pending
    app._render_history = lambda items: setattr(app, "history_items", list(items))

    WalletApp._add_pending_tx(
        app,
        address=source_addr,
        oph=op_hash,
        direction=direction,
        amount_xtz=Decimal("0.01") if direction != "DEL" else Decimal(0),
        counterparty="The baker" if direction != "OUT" else "tz1TARGET",
        entrypoint=entrypoint,
        processing_seconds=30.0,
        select_wallet=True,
    )

    hashes = [it.get("hash") for it in app.history_items]
    assert "op_existing" in hashes
    assert op_hash in hashes
