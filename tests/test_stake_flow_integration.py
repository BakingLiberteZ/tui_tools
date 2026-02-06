import asyncio
from decimal import Decimal
from types import SimpleNamespace

import sassy_wallet.ui.app as app_mod
from sassy_wallet.core.store import Account
from sassy_wallet.ui.app import StakeScreen


def test_stake_flow_double_attempt_keeps_context_and_blocks_race():
    """
    Integration-style flow test for StakeScreen:
    1) First stake attempt completes and dismisses payload.
    2) Immediate second attempt is blocked by the final pending re-check,
       and must NOT dismiss again or reset selected wallet context.
    """
    account = Account(
        name="Primary",
        address="tz1SOURCE11111111111111111111111111111",
        enc=None,
    )
    screen = StakeScreen(accounts=[account], rpc="https://rpc.tzkt.io/mainnet")
    screen.selected_account = account
    screen.balance_xtz = Decimal("10")
    screen.is_delegated = True

    dismissed_payloads: list[dict] = []
    shown_errors: list[str] = []
    confirm_calls: list[Decimal] = []
    pending_checks: list[str] = []

    async def _refresh_selected_chain_state(force_refresh=False, preserve_input=False):
        return True

    async def _confirm_pending_ops_or_abort(*, cancel_message: str, detailed: bool = False) -> bool:
        pending_checks.append(cancel_message)
        # First attempt: pass both checks.
        # Second attempt: pass first check, fail second (race right before dismiss).
        idx = len(pending_checks)
        return idx in (1, 2, 3)

    async def _confirm_stake_flow(*, amount, cancel_message, confirm_screen_factory):
        confirm_calls.append(amount)
        return object(), {"fee_mutez": 1234, "gas_limit": 2222, "storage_limit": 0}

    def _dismiss_stake_action(action: str, **kwargs):
        payload = {"action": action, **kwargs}
        dismissed_payloads.append(payload)

    def _show_error(message: str):
        shown_errors.append(message)

    screen._refresh_selected_chain_state = _refresh_selected_chain_state
    screen._has_outgoing_activity = lambda address: True
    screen._read_validated_amount = lambda **kwargs: Decimal("1")
    screen._confirm_pending_ops_or_abort = _confirm_pending_ops_or_abort
    screen._confirm_stake_flow = _confirm_stake_flow
    screen._dismiss_stake_action = _dismiss_stake_action
    screen._show_error = _show_error

    async def _run() -> None:
        await screen.stake_pressed()
        await screen.stake_pressed()

    asyncio.run(_run())

    # First attempt succeeded and dismissed payload.
    assert len(dismissed_payloads) == 1
    assert dismissed_payloads[0]["action"] == "stake"
    assert dismissed_payloads[0]["amount"] == Decimal("1")

    # Second attempt reached confirm step but was blocked before dismiss.
    assert len(confirm_calls) == 2
    assert len(pending_checks) == 4
    assert screen.selected_account.address == account.address
    assert shown_errors == []


def test_open_stake_flow_anchors_source_wallet_before_dispatch(monkeypatch):
    """When StakeScreen returns payload, app should focus source wallet before action handler runs."""
    account = Account(
        name="Source",
        address="tz1SOURCE11111111111111111111111111111",
        enc=object(),
    )

    class Dummy:
        pass

    app = Dummy()
    app.accounts = [account]
    app.rpc = "https://rpc.tzkt.io/mainnet"
    app._stake_wallet_info_cache = {}

    events: list[str] = []

    async def _push_screen_wait(_screen):
        return {"action": "stake", "account": account, "amount": Decimal("1")}

    app.push_screen_wait = _push_screen_wait
    app._focus_history_on_address = lambda address, **kwargs: events.append(f"focus:{address}")

    async def _handle_stake_action(stake_data):
        events.append(f"handle:{stake_data['account'].address}")

    app._handle_stake_action = _handle_stake_action
    app._handle_unstake_action = lambda *_args, **_kwargs: None
    app._handle_delegate_action = lambda *_args, **_kwargs: None
    app._handle_change_baker_action = lambda *_args, **_kwargs: None

    monkeypatch.setattr(app_mod, "StakeScreen", lambda **kwargs: SimpleNamespace(**kwargs))

    asyncio.run(app_mod.WalletApp._open_stake_flow(app))

    assert events == [f"focus:{account.address}", f"handle:{account.address}"]


def test_open_stake_flow_does_not_abort_when_focus_anchor_fails(monkeypatch):
    """Regression: a transient UI focus error must not stop stake dispatch."""
    account = Account(
        name="Source",
        address="tz1SOURCE11111111111111111111111111111",
        enc=object(),
    )

    class Dummy:
        pass

    app = Dummy()
    app.accounts = [account]
    app.rpc = "https://rpc.tzkt.io/mainnet"
    app._stake_wallet_info_cache = {}

    events: list[str] = []

    async def _push_screen_wait(_screen):
        return {"action": "stake", "account": account, "amount": Decimal("1")}

    app.push_screen_wait = _push_screen_wait

    def _focus_history_on_address(_address, **_kwargs):
        raise RuntimeError("transient focus failure")

    app._focus_history_on_address = _focus_history_on_address

    async def _handle_stake_action(stake_data):
        events.append(f"handle:{stake_data['account'].address}")

    app._handle_stake_action = _handle_stake_action
    app._handle_unstake_action = lambda *_args, **_kwargs: None
    app._handle_delegate_action = lambda *_args, **_kwargs: None
    app._handle_change_baker_action = lambda *_args, **_kwargs: None

    monkeypatch.setattr(app_mod, "StakeScreen", lambda **kwargs: SimpleNamespace(**kwargs))

    asyncio.run(app_mod.WalletApp._open_stake_flow(app))

    assert events == [f"handle:{account.address}"]


def test_handle_stake_action_executes_injection_after_focus(monkeypatch):
    """Regression: focusing source wallet before stake must not abort tx injection."""
    account = Account(
        name="Source",
        address="tz1SOURCE11111111111111111111111111111",
        enc=object(),
    )

    class DummyKey:
        def public_key_hash(self):
            return account.address

    class Dummy:
        pass

    app = Dummy()
    app.rpc = "https://rpc.tzkt.io/mainnet"
    app._tx_watchdog_token = None
    app._status_lock_until_refresh = False
    app._with_rpc_calls = []
    app._busy_states = []
    app._pending_hashes = []

    app._ensure_working_rpc = lambda: (True, True, None)
    app._focus_history_on_address = lambda *args, **kwargs: None
    app._ui = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    app._start_breathing_effect = lambda *args, **kwargs: None
    app._stop_breathing_effect = lambda: None
    app._set_status = lambda *args, **kwargs: None
    app._set_status_styled = lambda *args, **kwargs: None
    app._set_busy = lambda busy: app._busy_states.append(busy)
    app._start_tx_watchdog = lambda action, address: 123.0
    app._stop_tx_watchdog = lambda token: None
    app._tx_watchdog_fire = lambda *args, **kwargs: None
    app._tx_flow_remaining_or_default = lambda flow_start: 0.0
    app._schedule_after = lambda delay, cb: None
    app._refresh_account_status_only = lambda address: None
    app._silent_refresh_history_for = lambda address: None
    app._resolve_delegate_for_pending = lambda oph, addr: None
    app._resolve_baked_by_label = lambda *args, **kwargs: "The baker"
    app.run_worker = lambda fn, **kwargs: None
    app.set_timer = lambda delay, cb: cb()

    def _add_pending_tx(**kwargs):
        app._pending_hashes.append(kwargs.get("oph"))

    app._add_pending_tx = _add_pending_tx

    def _with_rpc_fallback(**kwargs):
        app._with_rpc_calls.append(kwargs.get("action"))
        return app.rpc, "opHashStake123"

    app._with_rpc_fallback = _with_rpc_fallback
    app._tx_finalize_failsafe = lambda action, address: None

    async def _to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(app_mod.asyncio, "to_thread", _to_thread)
    monkeypatch.setattr(app_mod, "get_staking_balance", lambda rpc, address: 0)

    stake_data = {
        "account": account,
        "amount": Decimal("1"),
        "key": DummyKey(),
        "fee_mutez": 1200,
        "gas_limit": 2000,
        "storage_limit": 0,
    }

    asyncio.run(app_mod.WalletApp._handle_stake_action(app, stake_data))

    assert app._with_rpc_calls == ["stake"]
    assert "opHashStake123" in app._pending_hashes
    assert app._busy_states[0] is True
    assert app._busy_states[-1] is False
