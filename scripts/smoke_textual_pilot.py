#!/usr/bin/env python3
"""Interactive smoke e2e using Textual Pilot.

This script drives WalletApp in a test harness and validates end-to-end flow
sequencing for:
- Send
- Stake
- Unstake
- Delegate
- Change Baker

It uses deterministic stubs (no real RPC calls) to keep the run fast/stable.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections import deque
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sassy_wallet.ui.app as app_mod
from sassy_wallet.core.store import Account


class SmokeFailure(RuntimeError):
    pass


class FakeKey:
    def __init__(self, address: str) -> None:
        self._address = address

    def public_key_hash(self) -> str:
        return self._address


async def _wait_for(predicate, *, timeout: float, label: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.05)
    raise SmokeFailure(f"Timed out waiting for: {label}")


def _status_text(app: app_mod.WalletApp) -> str:
    try:
        return str(getattr(app.query_one("#status_line", app_mod.Static), "renderable", ""))
    except Exception:
        return ""


async def _run_once() -> None:
    source = Account(name="Smoke Source", address="tz1SMOKESOURCE11111111111111111111111", enc=object())
    other = Account(name="Smoke Other", address="tz1SMOKEOTHER22222222222222222222222", enc=object())
    key = FakeKey(source.address)

    app = app_mod.WalletApp()
    app.accounts = [source, other]
    app.selected = source
    app._last_selected_addr = None
    app._history_loaded_addr = None
    app.history_items = []
    app.history_cache = {}
    app._auto_refresh_enabled = False

    # Disable unrelated background activity.
    app._autodetect_rpc = lambda: None
    app._start_auto_refresh = lambda: None
    app._start_price_indicator = lambda: None
    app._start_rpc_pulse = lambda: None
    app._request_price_refresh = lambda *args, **kwargs: None

    # Render account list from fixture (avoid store reload during on_mount).
    def _render_accounts_fixture() -> None:
        lv = app.query_one("#accounts", app_mod.ListView)
        lv.clear()
        for idx, a in enumerate(app.accounts, start=1):
            row = app_mod.Horizontal(
                app_mod.Label(f"{idx:<2} {a.name}", classes="account_name", markup=True),
                app_mod.Label("│", classes="account_sep", markup=True),
                app_mod.Label(a.address, classes="account_address", markup=True),
                app_mod.Button("⧉", id=f"copy_addr_{idx - 1}", classes="copy_addr"),
                app_mod.Label("", classes="account_marker"),
            )
            lv.append(app_mod.ListItem(row))
        lv.focus()

    app._render_accounts = _render_accounts_fixture

    # Deterministic operation timing.
    app._tx_flow_remaining_or_default = lambda *_args, **_kwargs: 0.10
    app._resolve_baked_by_label = lambda *_args, **_kwargs: "Smoke Baker"
    app._resolve_delegate_for_pending = lambda *_args, **_kwargs: None
    app._refresh_account_status_only = lambda *_args, **_kwargs: None
    app._silent_refresh_history_for = lambda *_args, **_kwargs: None
    app._ensure_working_rpc = lambda: (True, True, None)

    # Keep worker execution local/synchronous in smoke to avoid teardown hangs.
    def _run_worker_sync(fn, **_kwargs):
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        except Exception:
            pass
        return None

    app.run_worker = _run_worker_sync
    app._verify_pending_op = lambda *_args, **_kwargs: None

    # Offline deterministic stubs.
    app_mod.get_balance_mutez = lambda *_args, **_kwargs: 10_000_000_000
    app_mod.get_staking_balance = lambda *_args, **_kwargs: 5_000_000_000
    app_mod.is_revealed = lambda *_args, **_kwargs: True
    app_mod.get_xtz_history = lambda *_args, **_kwargs: []
    app_mod.resolve_tx_by_hash = lambda *_args, **_kwargs: True
    app_mod.get_wallet_chain_state = lambda *_args, **_kwargs: {
        "delegate": "tz1SMOKEBAKER33333333333333333333333",
        "staked_mutez": 5_000_000,
        "staking_active": True,
    }

    # Deterministic op hashes
    op_hashes: list[str] = []
    op_n = {"i": 0}

    def _with_rpc_fallback(*, action: str, rpc: str, **_kwargs):
        op_n["i"] += 1
        oph = f"ooSmoke{op_n['i']:04d}_{action}"
        op_hashes.append(oph)
        return rpc, oph

    app._with_rpc_fallback = _with_rpc_fallback

    busy_events: list[bool] = []
    original_set_busy = app._set_busy

    def _set_busy_trace(busy: bool) -> None:
        busy_events.append(busy)
        original_set_busy(busy)

    app._set_busy = _set_busy_trace

    stake_payloads = deque(
        [
            {
                "action": "stake",
                "account": source,
                "amount": Decimal("0.20"),
                "key": key,
                "fee_mutez": 1200,
                "gas_limit": 2000,
                "storage_limit": 0,
            },
            {
                "action": "unstake",
                "account": source,
                "amount": Decimal("0.10"),
                "key": key,
                "fee_mutez": 1200,
                "gas_limit": 2000,
                "storage_limit": 0,
                "second_confirmed": True,
            },
            {
                "action": "delegate",
                "account": source,
                "key": key,
                "fee_mutez": 1200,
                "gas_limit": 2000,
                "storage_limit": 0,
                "baker_address": "tz1SMOKEBAKER33333333333333333333333",
                "baker_name": "Smoke Baker",
            },
            {
                "action": "change_baker",
                "account": source,
                "key": key,
                "fee_mutez": 1200,
                "gas_limit": 2000,
                "storage_limit": 0,
                "baker_address": "tz1SMOKEBAKER44444444444444444444444",
                "current_baker": "tz1SMOKEBAKER33333333333333333333333",
            },
        ]
    )

    send_payload = {
        "from_account": source,
        "to_addr": "tz1TARGET55555555555555555555555555555",
        "amount": Decimal("0.09"),
        "key": key,
        "fee_mutez": 1200,
        "gas_limit": 2000,
        "storage_limit": 0,
    }

    async def _fake_push_screen_wait(screen):
        name = screen.__class__.__name__
        if name == "SendScreen":
            return send_payload
        if name == "StakeScreen":
            return stake_payloads.popleft() if stake_payloads else None
        raise SmokeFailure(f"Unexpected modal in smoke flow: {name}")

    app.push_screen_wait = _fake_push_screen_wait

    failure: str | None = None
    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause(0.1)
        app._render_accounts()
        app.selected = source
        app._last_selected_addr = source.address
        app._focus_history_on_address(source.address, ensure_loaded=False, refresh_details=True)
        await pilot.pause(0.1)

        print("[smoke-pilot] send", flush=True)
        app.action_send()
        await _wait_for(lambda: not app._send_in_progress, timeout=6.0, label="send completion")

        print("[smoke-pilot] stake", flush=True)
        await asyncio.wait_for(app._open_stake_flow(), timeout=8.0)
        await asyncio.sleep(0.25)

        print("[smoke-pilot] unstake", flush=True)
        await asyncio.wait_for(app._open_stake_flow(), timeout=8.0)
        await asyncio.sleep(0.25)

        print("[smoke-pilot] delegate", flush=True)
        await asyncio.wait_for(app._open_stake_flow(), timeout=8.0)
        await asyncio.sleep(0.25)

        print("[smoke-pilot] change baker", flush=True)
        await asyncio.wait_for(app._open_stake_flow(), timeout=8.0)
        await asyncio.sleep(0.35)

        try:
            if not app.selected or app.selected.address != source.address:
                raise SmokeFailure("Selected wallet is not source wallet after flows")

            hashes_history = {str(item.get("hash") or "") for item in app.history_items}
            hashes_pending = set(getattr(app, "_pending_ops", {}).keys())
            missing = [h for h in op_hashes if h not in hashes_history and h not in hashes_pending]
            if missing:
                raise SmokeFailure(f"Missing ops in history/pending: {missing}")

            if "Operation in progress" in _status_text(app):
                raise SmokeFailure("Status bar still shows in-progress lock")

            for bid in ("#send", "#recv", "#stake", "#refresh"):
                if app.query_one(bid, app_mod.Button).disabled:
                    raise SmokeFailure(f"Button stayed disabled: {bid}")

            if True not in busy_events or False not in busy_events:
                raise SmokeFailure("Busy state did not toggle")
        except SmokeFailure as e:
            failure = str(e)
        finally:
            app.exit()
            await pilot.pause(0.1)

    if failure:
        raise SmokeFailure(failure)


def main() -> int:
    try:
        asyncio.run(asyncio.wait_for(_run_once(), timeout=45.0))
    except Exception as e:
        print(f"[smoke-pilot] FAIL: {e}")
        return 1
    print("[smoke-pilot] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
