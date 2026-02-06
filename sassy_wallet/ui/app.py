from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone
import asyncio
import decimal
import re
import threading
import concurrent.futures
import queue
import os
from threading import RLock
from functools import lru_cache
import urllib.request
import urllib.error
import time
import json
import webbrowser
import logging
# Clipboard integration intentionally uses explicit OS clipboard helpers.
import subprocess  # nosec B404
import shutil
from pathlib import Path
from typing import Any, Callable, Optional
from cryptography.exceptions import InvalidTag

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.css.query import NoMatches, WrongType
from textual.widgets import Footer, ListView, ListItem, Label, Button, Input, Static, DirectoryTree, Tree
from textual.events import MouseDown, MouseUp

from sassy_wallet.core.store import (
    load_store,
    save_store,
    list_accounts,
    upsert_account,
    get_last_migration,
    ensure_private_dir,
    ensure_private_files_in_dir,
    write_private_json_atomic,
    Account,
)
from sassy_wallet.core.crypto import encrypt_secret, decrypt_secret, EncryptedBlob
from sassy_wallet.core.tezos import (
    get_balance_mutez,
    mutez_to_xtz,
    key_from_encoded_secret,
    key_from_mnemonic_ledger,
    send_xtz,
    get_xtz_history,
    resolve_tx_by_hash,
    invalidate_history_cache,
    estimate_send_xtz,
    estimate_stake,
    estimate_delegation,
    estimate_unstake,
    get_delegation_info,
    get_staking_balance,
    get_wallet_chain_state,
    get_baker_info,
    has_outgoing_tx,
    delegate_to_baker,
    stake_xtz,
    unstake_xtz,
    is_revealed,
    check_pending_operations,
)
from sassy_wallet.core.logger import (
    safe_log_exception,
    log_error,
    log_info,
    log_warning,
    log_debug,
    setup_logger,
)
from sassy_wallet.core.validation import (
    validate_baker_address,
    validate_tezos_address,
    validate_amount,
    validate_fee,
    validate_gas_limit,
    validate_storage_limit,
    sanitize_input,
    normalize_https_url,
    normalize_rpc_url,
)
from sassy_wallet.messages.bakery import get_message, SPINNER_MESSAGES, get_baker_message, get_wallet_loading_message
from sassy_wallet.messages.staking import get_staking_message
from sassy_wallet.messages.empty_wallet import get_empty_wallet_message
from sassy_wallet.messages.balance import get_balance_message
from sassy_wallet.messages.modal import get_modal_message
from sassy_wallet.messages.baker_commentary_short import get_baker_commentary_short
from sassy_wallet.messages.send_commentary import get_recipient_comment, get_amount_comment, get_confirmation_comment
from sassy_wallet.messages.send_status import get_send_baked_message
from sassy_wallet.messages.advanced_mode import get_advanced_mode_message
from sassy_wallet.ui.input_utils import (
    filter_amount_input,
    filter_base58_input,
    filter_digits_input,
    shimmer_text,
    filter_mnemonic_input,
    filter_derivation_path,
)

BACK_NAV_MARKER = "__BACK__"

_FLOW_PRECHECK_EXCEPTIONS = (
    RuntimeError,
    ValueError,
    TypeError,
    ConnectionError,
    TimeoutError,
    urllib.error.URLError,
)
_UI_CALLBACK_EXCEPTIONS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
)
_FLOW_TASK_EXCEPTIONS = _FLOW_PRECHECK_EXCEPTIONS + _UI_CALLBACK_EXCEPTIONS + (asyncio.CancelledError,)
_UI_QUERY_EXCEPTIONS = _UI_CALLBACK_EXCEPTIONS + (NoMatches, WrongType)
_LOCAL_IO_EXCEPTIONS = (OSError, PermissionError)
_NUMERIC_PARSE_EXCEPTIONS = (ValueError, TypeError, decimal.InvalidOperation)
_CRYPTO_DECODE_EXCEPTIONS = (
    InvalidTag,
    ValueError,
    TypeError,
    KeyError,
    json.JSONDecodeError,
)
_STATUS_STYLE_CLASSES = (
    "status-success",
    "status-success-dim",
    "status-warning",
    "status-warning-dim",
    "status-error",
    "status-info",
    "status-stake",
    "status-stake-dim",
    "status-unstake",
    "status-unstake-dim",
    "status-processing",
    "status-processing-dim",
)
_FEE_CHOICES = ("economy", "normal", "priority")
_FEE_LABELS = ("Economy", "Normal", "Priority")
_STAKE_FLOW_WORKER_GROUP = "stake-flow"
_IMPORT_TYPE_OPTIONS = (
    ("mnemonic12", "🧠 Import with 12 Words", "Default derivation"),
    ("mnemonic24", "🧠 Import with 24 Words", "Default derivation"),
    ("secret", "🔑 Import with Secret Key", "Full wallet - can send & receive"),
    ("watch", "👀 Watch-Only Address", "Monitor only - cannot send"),
    ("backup", "📦 From Backup File", "Restore from recipe book"),
)
_STAKE_OUTGOING_REQUIRED_MSG = (
    "⚠️ You need a positive balance and at least one outgoing transfer "
    "before you can delegate or stake."
)


# --- Configuration constants ---
class Config:
    """Application configuration constants."""
    # RPC URLs
    RPC_DEFAULT_MAINNET = "https://rpc.tzkt.io/mainnet"
    RPC_DEFAULT_GHOSTNET = "https://rpc.tzkt.io/ghostnet"

    RPC_MAINNET_CANDIDATES = [
        "https://rpc.tzkt.io/mainnet",
        "https://mainnet.smartpy.io",
        "https://mainnet.tezos.ecadinfra.com",
        # Fallbacks (may be read-only / throttled / flaky depending on policy/region):
        "https://rpc.tzbeta.net",
        "https://mainnet.api.tez.ie",
    ]

    RPC_GHOSTNET_CANDIDATES = [
        "https://ghostnet.smartpy.io",
        "https://rpc.tzkt.io/ghostnet",
        "https://ghostnet.tezos.ecadinfra.com",
    ]

    # TzKT API URLs
    TZKT_API_MAINNET = "https://api.tzkt.io"
    TZKT_API_GHOSTNET = "https://api.ghostnet.tzkt.io"

    # TzKT UI URLs (for block explorers)
    TZKT_UI_MAINNET = "https://tzkt.io"
    TZKT_UI_GHOSTNET = "https://ghostnet.tzkt.io"

    # RPC settings
    RPC_TIMEOUT = 2.5
    RPC_FETCH_TIMEOUT = 5.0
    RPC_LONG_TIMEOUT = 15.0
    RPC_RETRY_ATTEMPTS = 3
    RPC_RETRY_BACKOFF = 0.4
    # RPC selection: prefer nodes that support both simulation + injection (see choose_working_rpc).

    # History settings
    HISTORY_DEFAULT_LIMIT = 10
    HISTORY_INCREMENT = 10
    HISTORY_MAX_LIMIT = 20
    HISTORY_POLL_MAX_ATTEMPTS = 20
    HISTORY_POLL_INTERVAL = 1.0

    # Recent destinations
    RECENT_DESTINATIONS_MAX = 10

    # UI timing
    SPINNER_INTERVAL = 0.1
    ESTIMATION_PULSE_INTERVAL = 0.15
    FUN_MESSAGE_INTERVAL = 60  # ticks
    BLINK_INTERVAL = 10  # ticks
    ESTIMATE_FALLBACK_SECONDS = 1.5
    TX_BLOCK_TIME_SECONDS = 6.0
    TX_UI_GRACE_SECONDS = 1.0
    TX_FLOW_TOTAL_SECONDS = TX_BLOCK_TIME_SECONDS + TX_UI_GRACE_SECONDS
    TX_HISTORY_UPDATE_SECONDS = 2.0
    STATUS_BLINK_INTERVAL_SECONDS = 0.4
    PRICE_REFRESH_SECONDS = 60.0
    PRICE_INITIAL_DELAY_SECONDS = 5.0
    # Send keeps a dedicated failsafe to avoid leaving the UI "locked" forever.
    # Keep it >= hard RPC timeout to avoid false positives on slow injections.
    SEND_FAILSAFE_SECONDS = 180.0

    # Baker search
    BAKER_SEARCH_MAX_DEPTH = 20

    # Accounts list height
    ACCOUNTS_LIST_HEIGHT = 4

    # Logging
    LOG_FILE = "logs/wallet.log"
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    LOG_LEVEL = logging.INFO

    # Balance caching
    BALANCE_CACHE_SECONDS = 30.0

    # Auto-refresh
    AUTO_REFRESH_INTERVAL_SECONDS = 60.0

    # Pending operation timeout before marking UNKNOWN
    PENDING_TX_TIMEOUT_SECONDS = 180.0
    # Assume OK after brief delay for better UX, then verify quietly
    PENDING_TX_ASSUME_OK_SECONDS = TX_FLOW_TOTAL_SECONDS
    PENDING_TX_VERIFY_SECONDS = 60.0
    PENDING_TX_PROCESSING_SECONDS = 60.0
    # UI/network timeouts:
    # - TX_RPC_TIMEOUT_SECONDS: "soft" timeout (show a "still working" notice).
    # - TX_RPC_HARD_TIMEOUT_SECONDS: hard timeout (treat as failure for UX; op may still land later).
    TX_RPC_TIMEOUT_SECONDS = 30.0
    TX_RPC_HARD_TIMEOUT_SECONDS = 180.0

    # Backup import bounds (defense-in-depth against oversized/corrupted files).
    BACKUP_MAX_FILE_BYTES = 2 * 1024 * 1024
    BACKUP_MAX_DECRYPTED_BYTES = 4 * 1024 * 1024
    BACKUP_MAX_ACCOUNTS = 200


# --- Address validation (simple + fast) ---
_TZ_RE = re.compile(r"^tz[1-4][1-9A-HJ-NP-Za-km-z]{33}$")
_KT1_RE = re.compile(r"^KT1[1-9A-HJ-NP-Za-km-z]{33}$")


def is_tz_address(addr: str) -> bool:
    return bool(_TZ_RE.match((addr or "").strip()))


def is_kt1_address(addr: str) -> bool:
    return bool(_KT1_RE.match((addr or "").strip()))


def is_tezos_destination(addr: str) -> bool:
    a = (addr or "").strip()
    return is_tz_address(a) or is_kt1_address(a)


def _focus_with_fallback(
    owner: Any,
    *,
    primary: tuple[str, type],
    fallbacks: tuple[tuple[str, type], ...],
    primary_error: str,
    fallback_error: str,
) -> None:
    """Focus primary widget, then try fallbacks if needed."""
    primary_selector, primary_type = primary
    try:
        owner.query_one(primary_selector, primary_type).focus()
        return
    except _UI_QUERY_EXCEPTIONS as primary_exc:
        log_error(primary_error, exception=primary_exc)
    prior_exc = primary_exc
    for selector, widget_type in fallbacks:
        try:
            owner.query_one(selector, widget_type).focus()
            return
        except _UI_QUERY_EXCEPTIONS as fallback_exc:
            prior_exc = fallback_exc
    log_debug(fallback_error, exception=str(prior_exc), prior_exception=str(primary_exc))


@lru_cache(maxsize=1)
@safe_log_exception(default_return="💅 Sassy Wallet 💅", user_message="Failed to load ASCII logo")
def load_ascii_logo() -> str:
    """Load ASCII logo from file as plain text. Returns logo string."""
    logo_path = Path(__file__).parent.parent / "assets" / "logo.txt"
    if logo_path.exists():
        return logo_path.read_text(encoding="utf-8").strip()
    # Fallback if file doesn't exist
    return "💅 Sassy Wallet 💅"


def network_from_rpc(rpc: str) -> str:
    return "ghostnet" if "ghostnet" in (rpc or "").lower() else "mainnet"


def tzkt_ui_base_from_rpc(rpc: str) -> str:
    return Config.TZKT_UI_GHOSTNET if network_from_rpc(rpc) == "ghostnet" else Config.TZKT_UI_MAINNET


def tzkt_api_base_from_rpc(rpc: str) -> str:
    return Config.TZKT_API_GHOSTNET if network_from_rpc(rpc) == "ghostnet" else Config.TZKT_API_MAINNET


def _normalize_rpc_runtime(rpc: str | None, *, fallback: str) -> tuple[str, bool]:
    """
    Normalize an RPC URL for runtime usage.

    Returns:
        (normalized_rpc, was_replaced)
    """
    candidate = (rpc or "").strip()
    try:
        normalized = normalize_rpc_url(candidate)
    except ValueError:
        return fallback, bool(candidate)
    return normalized, normalized != candidate


def _xtz_to_mutez(x: Decimal) -> int:
    return int((x * Decimal(1_000_000)).to_integral_value())


def setup_logging() -> None:
    """Configure application logging with rotation."""
    wallet_logger = setup_logger(name="wallet", log_file=Config.LOG_FILE, level=Config.LOG_LEVEL)

    # Keep root logger aligned so direct `logging.info(...)` calls in this module
    # follow the same file rotation policy as core logger helpers.
    logger = logging.getLogger()
    logger.setLevel(Config.LOG_LEVEL)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    for handler in wallet_logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False

    logging.info("=" * 60)
    logging.info("💅 Sassy Wallet started")
    logging.info("=" * 60)


def format_xtz(amount: Decimal) -> str:
    """Format XTZ amount with thousands separators and max 4 decimals.

    Examples:
        12345.678000 -> "12,345.678"
        1000.000000 -> "1,000"
        0.123456 -> "0.1235" (rounded to 4 decimals)
        0.12 -> "0.12"
    """
    # Format with 4 decimals and thousands separators
    formatted = f"{amount:,.4f}"
    # Remove trailing zeros after decimal point
    if '.' in formatted:
        formatted = formatted.rstrip('0').rstrip('.')
    return formatted


def format_xtz_precise(amount: Decimal, *, min_decimals: int = 3, max_decimals: int = 6) -> str:
    """Format XTZ with a stable number of decimals for tiny balances (e.g. stake display in lists)."""
    try:
        if min_decimals < 0:
            min_decimals = 0
        if max_decimals < min_decimals:
            max_decimals = min_decimals
        formatted = f"{amount:,.{max_decimals}f}"
    except _NUMERIC_PARSE_EXCEPTIONS:
        # Fallback to existing formatter
        return format_xtz(amount)
    if "." not in formatted:
        return formatted
    whole, frac = formatted.split(".", 1)
    frac = frac.rstrip("0")
    if len(frac) < min_decimals:
        frac = frac.ljust(min_decimals, "0")
    if frac:
        return f"{whole}.{frac}"
    return whole


def _fee_choice_from_index(index: int, default: str = "normal") -> str:
    if 0 <= index < len(_FEE_CHOICES):
        return _FEE_CHOICES[index]
    return default if default in _FEE_CHOICES else "normal"


def _fee_index_from_choice(choice: str) -> int:
    try:
        return _FEE_CHOICES.index(choice)
    except ValueError:
        return 1


def _selected_option_id(index: Optional[int], options: tuple[tuple[str, str, str], ...]) -> Optional[str]:
    if index is None or index < 0 or index >= len(options):
        return None
    return options[index][0]


def _selected_value_by_index(index: Optional[int], options: list[str], default: str) -> str:
    if index is None or index < 0 or index >= len(options):
        return default
    return options[index]


def _build_fee_rows_text(
    fee_choice: str,
    *,
    estimate: Optional[dict],
    estimating: bool = False,
    err: str = "",
    value_prefix: str = "",
    selected_mark: str = "● ",
    unselected_mark: str = "○ ",
) -> list[str]:
    if estimating:
        return [f"  {label} — estimating…" for label in _FEE_LABELS]

    if err or not estimate:
        return [f"  {label} — unavailable" for label in _FEE_LABELS]

    fee_opts = estimate.get("fee_options") or {}
    rows: list[str] = []
    for choice, label in zip(_FEE_CHOICES, _FEE_LABELS):
        opt = fee_opts.get(choice) or {}
        fee_total = opt.get("total_fee_xtz")
        fee_text = format_xtz(fee_total) if fee_total else "0"
        mark = selected_mark if fee_choice == choice else unselected_mark
        rows.append(f"{mark}{label} — {value_prefix}{fee_text} XTZ")
    return rows


def _fee_selection_payload(estimate: Optional[dict], fee_choice: str) -> dict[str, Optional[int]]:
    if not estimate:
        return {"fee_mutez": None, "gas_limit": None, "storage_limit": None}
    fee_opts = estimate.get("fee_options") or {}
    chosen = fee_opts.get(fee_choice) or {}
    return {
        "fee_mutez": chosen.get("tx_fee_mutez"),
        "gas_limit": chosen.get("gas_limit"),
        "storage_limit": chosen.get("storage_limit"),
    }


def _tx_fee_mutez_from_choice(estimate: Optional[dict], fee_choice: str) -> Optional[int]:
    tx_fee = _fee_selection_payload(estimate, fee_choice).get("fee_mutez")
    try:
        return int(tx_fee) if tx_fee is not None else None
    except _NUMERIC_PARSE_EXCEPTIONS as e:
        log_error("Failed to parse tx fee from fee choice", exception=e, tx_fee=tx_fee)
        return None


def _enable_action_button(owner: Any, button_id: str, debug_context: str) -> None:
    try:
        btn = owner.query_one(button_id, Button)
        btn.disabled = False
        btn.focus()
    except _UI_QUERY_EXCEPTIONS as e:
        log_debug(debug_context, exception=str(e))


def _start_estimation_pulse(owner: Any) -> None:
    owner._estimating = True
    owner._est_i = 0
    if owner._est_timer is None:
        owner._est_timer = owner.set_interval(Config.ESTIMATION_PULSE_INTERVAL, owner._tick_est_pulse)


def _stop_estimation_pulse(owner: Any) -> None:
    owner._estimating = False
    if owner._est_timer is not None:
        owner._est_timer.stop()
        owner._est_timer = None


def _tick_estimation_pulse(owner: Any) -> None:
    if not owner._estimating:
        return
    owner._est_i += 1
    owner._render_summary(estimating=True)
    owner._update_fee_list(estimating=True)


def _init_fee_rows(owner: Any) -> None:
    """Create the 3 fixed fee rows once, keeping Label refs for fast updates."""
    lv = owner.query_one("#fee_list", ListView)
    lv.clear()
    owner._fee_labels = []
    for _ in range(3):
        lbl = Label("")
        owner._fee_labels.append(lbl)
        lv.append(ListItem(lbl))


def _update_fee_title(owner: Any, *, estimating: bool, debug_context: str) -> None:
    try:
        fee_title = owner.query_one("#fee_title", Static)
        if estimating:
            shimmer = shimmer_text("Estimating...", owner._est_i, span=2, pingpong=True)
            fee_title.update(f"[b]Fee[/b] — {shimmer} [dim](↑/↓ to choose)[/dim]")
        else:
            fee_title.update("[b]Fee[/b] (↑/↓ to choose)")
    except _UI_QUERY_EXCEPTIONS as e:
        log_debug(debug_context, exception=str(e))


def _handle_fee_selection(
    owner: Any,
    event: ListView.Selected,
    *,
    render_requires_estimate: bool = False,
) -> None:
    idx = event.list_view.index
    if idx is None:
        return
    owner._fee_choice = _fee_choice_from_index(idx, owner._fee_choice)
    owner._update_fee_list(estimating=False)
    if render_requires_estimate and not owner._estimate:
        return
    owner._render_summary(estimating=False)


def _apply_basic_estimate_fallback(owner: Any, *, enable_action: Callable[[], None]) -> None:
    if not owner._estimating or owner._estimate is not None:
        return
    owner._stop_est_pulse()
    owner._render_summary(err="")
    owner._update_fee_list(estimating=False)
    enable_action()


def _focus_cancel_button(owner: Any, *, context: str, fallbacks: tuple[tuple[str, type], ...] = ()) -> None:
    _focus_with_fallback(
        owner,
        primary=("#cancel", Button),
        fallbacks=fallbacks,
        primary_error=f"Failed to focus cancel button in {context}",
        fallback_error=f"Failed to focus fallback buttons in {context}",
    )


def _move_focus_in_button_row(
    focused: Any,
    key: str,
    *,
    include_hidden: bool = True,
    require_visible: bool = False,
) -> bool:
    if key not in ("left", "right") or not isinstance(focused, Button):
        return False
    parent = focused.parent
    if not isinstance(parent, Horizontal):
        return False

    focusables: list[Button] = []
    for child in parent.children:
        if not isinstance(child, Button):
            continue
        if not include_hidden and child.has_class("hidden"):
            continue
        if require_visible and not getattr(child, "visible", True):
            continue
        focusables.append(child)

    if focused not in focusables:
        return False

    idx = focusables.index(focused)
    if key == "left" and idx > 0:
        focusables[idx - 1].focus()
        return True
    if key == "right" and idx < len(focusables) - 1:
        focusables[idx + 1].focus()
        return True
    return False


def _handle_input_escape_focus_cancel(
    owner: Any,
    event: Any,
    key: str,
    *,
    context: str,
    fallbacks: tuple[tuple[str, type], ...] = (),
) -> bool:
    """Return True when focus is in Input and caller should early-return."""
    if not isinstance(owner.app.focused, Input):
        return False
    if key == "escape":
        _focus_cancel_button(owner, context=context, fallbacks=fallbacks)
        event.stop()
    return True


def _handle_backspace_escape(
    owner: Any,
    event: Any,
    key: str,
    *,
    back_handler: Callable[[], None],
    cancel_handler: Callable[[], None],
    back_enabled: bool,
) -> bool:
    if key == "backspace" and back_enabled:
        back_handler()
        event.stop()
        return True
    if key == "escape":
        cancel_handler()
        event.stop()
        return True
    return False


def _handle_tx_confirm_key(
    owner: Any,
    event: Any,
    key: str,
    *,
    context: str,
    action_handler: Callable[[], None],
) -> bool:
    # Let Input/ListView handle keys naturally, but allow escape to blur first.
    if isinstance(owner.app.focused, (Input, ListView)):
        if key == "escape" and isinstance(owner.app.focused, Input):
            _focus_cancel_button(
                owner,
                context=context,
                fallbacks=(("#toggle", Button), ("#send", Button), ("#delegate", Button)),
            )
            event.stop()
        return True

    if _handle_backspace_escape(
        owner,
        event,
        key,
        back_handler=owner.back_pressed,
        cancel_handler=owner.cancel_pressed,
        back_enabled=bool(getattr(owner, "show_back_button", False)),
    ):
        return True

    if key != "enter":
        return False
    try:
        if owner.query_one("#toggle", Button).has_focus:
            owner._toggle_advanced()
            return True
        if owner.query_one("#cancel", Button).has_focus:
            owner.cancel_pressed()
            return True
    except _UI_QUERY_EXCEPTIONS as e:
        log_error("Failed to check tx confirm button focus", exception=e)
    action_handler()
    return True


def _parse_tx_overrides(
    owner: Any,
    *,
    fee_input_id: str = "#fee_xtz",
    gas_input_id: str = "#gas_limit",
    storage_input_id: str = "#storage_limit",
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse optional manual fee/gas/storage overrides from screen inputs."""
    fee_xtz_s = sanitize_input(owner.query_one(fee_input_id, Input).value or "")
    gas_s = sanitize_input(owner.query_one(gas_input_id, Input).value or "")
    storage_s = sanitize_input(owner.query_one(storage_input_id, Input).value or "")

    fee_mutez: Optional[int] = None
    gas: Optional[int] = None
    storage: Optional[int] = None

    if fee_xtz_s:
        is_valid, error_msg, fee_xtz = validate_fee(fee_xtz_s)
        if not is_valid:
            raise ValueError(f"Invalid fee: {error_msg}")
        fee_mutez = _xtz_to_mutez(fee_xtz)

    if gas_s:
        is_valid, error_msg, gas = validate_gas_limit(gas_s)
        if not is_valid:
            raise ValueError(f"Invalid gas limit: {error_msg}")

    if storage_s:
        is_valid, error_msg, storage = validate_storage_limit(storage_s)
        if not is_valid:
            raise ValueError(f"Invalid storage limit: {error_msg}")

    return fee_mutez, gas, storage


def _tx_modal_result(
    *,
    ok: bool,
    fee_mutez: Optional[int] = None,
    gas_limit: Optional[int] = None,
    storage_limit: Optional[int] = None,
    back: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "fee_mutez": fee_mutez,
        "gas_limit": gas_limit,
        "storage_limit": storage_limit,
    }
    if back:
        payload[BACK_NAV_MARKER] = True
    return payload


def format_relative_time(timestamp_iso: str) -> str:
    """Format ISO timestamp as relative time (e.g., '5 min ago', '2 hours ago').

    Args:
        timestamp_iso: ISO 8601 timestamp string

    Returns:
        Relative time string or original timestamp if parsing fails
    """
    try:
        # Parse ISO timestamp (handle both with and without timezone)
        if timestamp_iso.endswith('Z'):
            dt = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
        elif '+' in timestamp_iso or timestamp_iso.count('-') > 2:
            dt = datetime.fromisoformat(timestamp_iso)
        else:
            # Assume UTC if no timezone
            dt = datetime.fromisoformat(timestamp_iso).replace(tzinfo=timezone.utc)

        # Calculate difference
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:  # < 1 hour
            minutes = int(seconds / 60)
            return f"{minutes} min ago" if minutes > 1 else "1 min ago"
        elif seconds < 86400:  # < 1 day
            hours = int(seconds / 3600)
            return f"{hours} hr ago" if hours > 1 else "1 hr ago"
        elif seconds < 604800:  # < 1 week
            days = int(seconds / 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"
        elif seconds < 2592000:  # < 30 days
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif seconds < 31536000:  # < 1 year
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = int(seconds / 31536000)
            return f"{years} year{'s' if years > 1 else ''} ago"

    except (ValueError, TypeError, OverflowError) as e:
        log_error("Failed to parse relative time", exception=e, timestamp=timestamp_iso)
        # Fallback: return first 10 chars (date part)
        return timestamp_iso[:10] if len(timestamp_iso) >= 10 else timestamp_iso


# --- RPC capability probing (public RPCs can be read-only / restricted) ---
# We probe for two endpoints:
# - /injection/operation (needed to broadcast operations)
# - /chains/main/blocks/head/helpers/scripts/run_operation (needed for simulation/autofill)
#
# We intentionally treat 405/415 as "exists" because those endpoints typically require POST.

_OK_CODES = {200, 400, 405, 415}

# Candidates ordered by preference. We will probe them at runtime and pick the first
# one that supports BOTH simulation (run_operation) and injection.
# Use Config constants instead of module-level variables
_MAINNET_RPC_CANDIDATES = Config.RPC_MAINNET_CANDIDATES
_GHOSTNET_RPC_CANDIDATES = Config.RPC_GHOSTNET_CANDIDATES


def _http_code(
    url: str,
    *,
    timeout_s: float = Config.RPC_TIMEOUT,
    method: str = "GET",
    data: bytes | None = None,
    headers: Optional[dict] = None,
) -> int:
    """Return HTTP status code for a simple GET, or 0 on network error."""
    try:
        safe_url = normalize_https_url(url, allow_query=True, allow_fragment=False)
    except ValueError as e:
        log_warning("Blocked unsafe URL in HTTP probe", url=url, reason=str(e))
        return 0

    try:
        req = urllib.request.Request(
            safe_url,
            data=data,
            method=method,
            headers=headers
            or {
                "User-Agent": "tui-tezos-wallet/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec B310
            return int(getattr(resp, "status", 0) or 0)
    except urllib.error.HTTPError as e:
        try:
            return int(getattr(e, "code", 0) or 0)
        except (TypeError, ValueError) as ex:
            log_error("Failed to extract HTTP error code", exception=ex)
            return 0
    except _FLOW_PRECHECK_EXCEPTIONS + (OSError,) as e:
        log_error("HTTP code check failed", exception=e, url=url)
        return 0




def _fetch_json(url: str, timeout_s: float = Config.RPC_FETCH_TIMEOUT) -> Any:
    """Fetch JSON from URL (GET)."""
    safe_url = normalize_https_url(url, allow_query=True, allow_fragment=False)
    req = urllib.request.Request(
        safe_url,
        method="GET",
        headers={
            "User-Agent": "tui-tezos-wallet/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec B310
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _fetch_tzkt_head_level(net: str) -> Optional[int]:
    rpc_base = Config.RPC_DEFAULT_MAINNET
    rpc_url = f"{rpc_base}/chains/main/blocks/head/header"
    try:
        data = _fetch_json(rpc_url, timeout_s=Config.RPC_FETCH_TIMEOUT)
        if isinstance(data, dict) and "level" in data:
            return int(data.get("level") or 0)
    except _FLOW_PRECHECK_EXCEPTIONS as e:
        log_error("Failed to fetch block header from TzKT RPC", exception=e, url=rpc_url)

    api_base = Config.TZKT_API_MAINNET
    urls = [
        f"{api_base}/v1/head",
        f"{api_base}/v1/blocks/head",
    ]
    for url in urls:
        try:
            data = _fetch_json(url, timeout_s=Config.RPC_FETCH_TIMEOUT)
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_error("Failed to fetch TzKT head", exception=e, url=url)
            continue
        if isinstance(data, dict) and "level" in data:
            try:
                return int(data.get("level") or 0)
            except (TypeError, ValueError):
                continue
    return None


def _fetch_xtz_price_usd() -> Optional[float]:
    url = "https://api.coingecko.com/api/v3/simple/price?ids=tezos&vs_currencies=usd"
    try:
        data = _fetch_json(url, timeout_s=Config.RPC_FETCH_TIMEOUT)
    except _FLOW_PRECHECK_EXCEPTIONS as e:
        log_error("Failed to fetch XTZ price", exception=e, url=url)
        return None
    try:
        price = data.get("tezos", {}).get("usd")
        return float(price) if price is not None else None
    except (TypeError, ValueError):
        return None


def find_baker_for_operation(rpc: str, oph: str, max_depth: int = Config.BAKER_SEARCH_MAX_DEPTH) -> Optional[str]:
    """Best-effort: find the baker of the block that included operation hash `oph`.

    Scans head, head~1, ... head~max_depth using `operation_hashes` (cheap),
    then reads the block header to get `baker`.
    """
    try:
        rpc = normalize_rpc_url(rpc)
    except ValueError as e:
        log_warning("Invalid RPC for baker lookup", rpc=rpc, reason=str(e))
        return None
    oph = (oph or "").strip()
    if not rpc or not oph:
        return None

    for i in range(max_depth + 1):
        block_id = "head" if i == 0 else f"head~{i}"
        try:
            op_hashes = _fetch_json(
                f"{rpc}/chains/main/blocks/{block_id}/operation_hashes",
                timeout_s=Config.RPC_LONG_TIMEOUT,
            )
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_error("Failed to fetch operation hashes", exception=e, block_id=block_id)
            continue

        try:
            if any(oph == h for vp in op_hashes for h in vp):
                try:
                    header = _fetch_json(
                        f"{rpc}/chains/main/blocks/{block_id}/header",
                        timeout_s=Config.RPC_LONG_TIMEOUT,
                    )
                    baker = header.get("baker")
                    if isinstance(baker, str) and baker.startswith("tz"):
                        return baker
                except _FLOW_PRECHECK_EXCEPTIONS as e:
                    log_error("Failed to fetch block header for baker", exception=e, block_id=block_id)
                    return None
                return None
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_error("Failed to search for operation in block", exception=e, block_id=block_id)
            continue

    # Fallback via TzKT indexer (op -> block -> baker)
    try:
        api_base = tzkt_api_base_from_rpc(rpc)
        ops = _fetch_json(f"{api_base}/v1/operations/transactions?hash={oph}&limit=1")
        if isinstance(ops, list) and ops:
            block_id = ops[0].get("block")
            if block_id:
                block = _fetch_json(f"{api_base}/v1/blocks/{block_id}")
                baker = block.get("baker") if isinstance(block, dict) else None
                if isinstance(baker, dict):
                    baker = baker.get("address")
                if isinstance(baker, str) and baker.startswith("tz"):
                    return baker
    except _FLOW_PRECHECK_EXCEPTIONS as e:
        log_error("Failed to resolve baker via TzKT", exception=e, oph=oph)

    return None
def rpc_supports_send(rpc: str) -> bool:
    try:
        rpc = normalize_rpc_url(rpc)
    except ValueError as e:
        log_warning("Invalid RPC for send capability probe", rpc=rpc, reason=str(e))
        return False
    url = f"{rpc}/injection/operation"
    code = _http_code(url)
    if code in _OK_CODES:
        return True
    # Some RPCs return 404 on GET; probe with POST and a dummy JSON body.
    code = _http_code(
        url,
        method="POST",
        data=b'""',
        headers={
            "User-Agent": "tui-tezos-wallet/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout_s=Config.RPC_TIMEOUT,
    )
    return code in _OK_CODES


def rpc_supports_simulation(rpc: str) -> bool:
    try:
        rpc = normalize_rpc_url(rpc)
    except ValueError as e:
        log_warning("Invalid RPC for simulation capability probe", rpc=rpc, reason=str(e))
        return False
    url = f"{rpc}/chains/main/blocks/head/helpers/scripts/run_operation"
    code = _http_code(url)
    if code in _OK_CODES:
        return True
    # Probe with POST to avoid false negatives on GET.
    code = _http_code(
        url,
        method="POST",
        data=b"{}",
        headers={
            "User-Agent": "tui-tezos-wallet/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout_s=Config.RPC_TIMEOUT,
    )
    return code in _OK_CODES


def rpc_supports_stake(rpc: str, source_address: str) -> bool:
    """Check if the RPC supports stake/unstake via legacy transaction entrypoint."""
    try:
        rpc = normalize_rpc_url(rpc)
        head = _fetch_json(f"{rpc}/chains/main/blocks/head/hash")
        if not isinstance(head, str) or not head:
            return False

        payload = {
            "branch": head,
            "contents": [
                {
                    "kind": "transaction",
                    "source": source_address,
                    "destination": source_address,
                    "fee": "0",
                    "counter": "1",
                    "gas_limit": "0",
                    "storage_limit": "0",
                    "amount": "0",
                    "parameters": {"entrypoint": "stake", "value": {"prim": "Unit"}},
                }
            ],
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{rpc}/chains/main/blocks/head/helpers/forge/operations",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=Config.RPC_LONG_TIMEOUT) as resp:  # nosec B310
            return int(getattr(resp, "status", 0) or 0) == 200
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            body = str(e)
        if "No case matched" in body and "At /kind" in body:
            return False
        log_warning("Stake support probe failed", exception=e, rpc=rpc)
        return False
    except _FLOW_PRECHECK_EXCEPTIONS + (OSError,) as e:
        log_warning("Stake support probe failed", exception=e, rpc=rpc)
        return False


def choose_working_rpc(current_rpc: str) -> tuple[str, bool, bool]:
    """Pick the first RPC that supports injection and (ideally) simulation.

    Returns (rpc, supports_send, supports_simulation).
    """
    fallback_rpc = Config.RPC_DEFAULT_GHOSTNET if network_from_rpc(current_rpc) == "ghostnet" else Config.RPC_DEFAULT_MAINNET
    current_rpc, _ = _normalize_rpc_runtime(current_rpc, fallback=fallback_rpc)

    net = network_from_rpc(current_rpc)
    candidates = _MAINNET_RPC_CANDIDATES if net == "mainnet" else _GHOSTNET_RPC_CANDIDATES

    # Prefer candidates order; only try current if it's not already listed.
    ordered_raw = candidates + ([current_rpc] if current_rpc not in candidates else [])
    ordered: list[str] = []
    for candidate in ordered_raw:
        try:
            normalized = normalize_rpc_url(candidate)
        except ValueError as e:
            log_warning("Skipping invalid RPC candidate", rpc=candidate, reason=str(e))
            continue
        if normalized not in ordered:
            ordered.append(normalized)

    if not ordered:
        ordered = [current_rpc]

    best_send_only: str | None = None

    for rpc in ordered:
        s = rpc_supports_send(rpc)
        sim = rpc_supports_simulation(rpc)
        if s and sim:
            return rpc, True, True
        if s and best_send_only is None:
            best_send_only = rpc

    if best_send_only is not None:
        return best_send_only, True, False

    # Nothing supports injection; keep current.
    return current_rpc, rpc_supports_send(current_rpc), rpc_supports_simulation(current_rpc)


def is_stale_branch_error(err: Exception) -> bool:
    """Detect stale branch / old block injection errors that warrant RPC fallback."""
    msg = str(err).lower()
    if "async_injection_failed" in msg and "too old" in msg:
        return True
    if "branched on either" in msg and "block" in msg:
        return True
    if "block" in msg and "too old" in msg:
        return True
    return False


def is_gas_exhausted_error(err: Exception) -> bool:
    """Detect gas exhausted errors to allow safe autofill fallback."""
    msg = str(err).lower()
    return "gas_exhausted" in msg and "operation" in msg


class ConfirmScreen(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    CSS = """
    ConfirmScreen {
        align: center middle;
    }

    ConfirmScreen > Vertical {
        width: 66;
        min-width: 66;
        max-width: 66;
        height: auto;
        min-height: 10;
        max-height: 24;
        overflow-y: hidden;
        background: $surface;
        border: heavy #ef4444;
        padding: 1 2;
    }

    ConfirmScreen #confirm_message {
        max-height: 12;
        overflow-y: auto;
    }

    ConfirmScreen Static {
        margin-bottom: 0;
    }

    ConfirmScreen Horizontal {
        align: center bottom;
        margin-top: 1;
    }

    ConfirmScreen Horizontal > Button {
        margin: 0 1;
    }

    ConfirmScreen Button {
        border: none;
        background: #1f2937;
        color: #e5e7eb;
    }

    ConfirmScreen Button:focus {
        background: #3b82f6;
        color: #f8fafc;
        text-style: bold;
    }
    """

    def __init__(self, message: str, title: str = "Confirm", yes_label: str = "Yes", no_label: str = "No"):
        super().__init__()
        self.message = message
        self.title = title
        self.yes_label = yes_label
        self.no_label = no_label

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self.title}[/b]\n{self.message}", id="confirm_message", markup=True)
            with Horizontal():
                yield Button(self.yes_label, id="yes", variant="error")
                yield Button(self.no_label, id="no", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#yes", Button).focus()

    @on(Button.Pressed, "#yes")
    def yes_pressed(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def no_pressed(self) -> None:
        self.dismiss(False)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.dismiss(False)
            event.stop()
            return
        if key in ("left", "right", "tab"):
            try:
                if key == "left":
                    if self.query_one("#yes", Button).has_focus:
                        event.stop()
                        return
                    self.screen.focus_previous()
                else:
                    if self.query_one("#no", Button).has_focus:
                        event.stop()
                        return
                    self.screen.focus_next()
            except _UI_QUERY_EXCEPTIONS:
                self.screen.focus_next()
            event.stop()
            return
        if key == "enter":
            try:
                if self.query_one("#no", Button).has_focus:
                    self.dismiss(False)
                else:
                    self.dismiss(True)
            except _UI_QUERY_EXCEPTIONS:
                self.dismiss(True)
            event.stop()


class ExitConfirmScreen(ConfirmScreen):
    """Dedicated exit confirmation dialog."""

    CSS = """
    ExitConfirmScreen {
        align: center middle;
    }

    ExitConfirmScreen > Vertical {
        width: 56;
        min-width: 56;
        max-width: 56;
        height: auto;
        min-height: 8;
        max-height: 18;
        overflow-y: hidden;
        background: $surface;
        border: heavy #ef4444;
        padding: 1 2;
    }

    ExitConfirmScreen #confirm_message {
        max-height: 10;
        overflow-y: auto;
    }

    ExitConfirmScreen Static {
        margin-bottom: 0;
    }

    ExitConfirmScreen Horizontal {
        align: center bottom;
        margin-top: 1;
    }

    ExitConfirmScreen Horizontal > Button {
        margin: 0 1;
    }

    ExitConfirmScreen Button {
        border: none;
        background: #1f2937;
        color: #e5e7eb;
    }

    ExitConfirmScreen Button:focus {
        background: #3b82f6;
        color: #f8fafc;
        text-style: bold;
    }
    """

class PromptScreen(ModalScreen[str]):
    CSS = """
    PromptScreen {
        align: center middle;
    }

    PromptScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #3b82f6;
        padding: 1 2;
    }

    PromptScreen Static {
        margin-bottom: 0;
    }

    PromptScreen #title {
        margin-bottom: 1;
    }

    PromptScreen #wallet_info {
        color: $accent;
        margin-top: 0;
        margin-bottom: 2;
        padding: 0;
    }

    PromptScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0;
        min-height: 2;
    }

    PromptScreen #inp {
        margin-top: 1;
        margin-bottom: 0;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    PromptScreen #inp:focus {
        border: solid #10b981;
    }

    PromptScreen Horizontal {
        align: center middle;
    }

    PromptScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        title: str,
        placeholder: str = "",
        password: bool = False,
        wallet_info: str = "",
        ok_label: str = "OK",
        fun_note: str = "",
        show_back_button: bool = False,
        initial_value: str = ""
    ):
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._password = password
        self._wallet_info = wallet_info
        self._ok_label = ok_label
        self._fun_note = fun_note
        self._show_back_button = show_back_button
        self._initial_value = initial_value

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self._title}[/b]", id="title", markup=True)
            if self._wallet_info:
                yield Static(f"{self._wallet_info}", id="wallet_info", markup=True)
            yield Input(placeholder=self._placeholder, password=self._password, id="inp", value=self._initial_value)
            if self._fun_note:
                yield Static(f"💡 {self._fun_note}", id="fun_note", markup=True)
            with Horizontal():
                if self._show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button(self._ok_label, id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        inp = self.query_one("#inp", Input)
        inp.focus()

    @on(Input.Submitted)
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed) -> None:

        if event.button.id == "ok":
            inp = self.query_one("#inp", Input)
            value = inp.value
            self.dismiss(value)
        elif event.button.id == "back":
            self.dismiss(BACK_NAV_MARKER)
        else:
            self.dismiss("")

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)

        # 🚫 If focus is on the Input widget, let it handle keys naturally
        # Only intercept Escape for cancel functionality
        if isinstance(self.app.focused, Input):
            if key == "ctrl+b" and self._show_back_button:
                self.dismiss(BACK_NAV_MARKER)
                event.stop()
                return
            if key == "escape":
                _focus_cancel_button(self, context="passphrase screen", fallbacks=(("#ok", Button),))
                event.stop()
                return
            # For all other keys, let Input handle them naturally (NO event.stop())
            return


        if key == "ctrl+b" and self._show_back_button:
            self.dismiss(BACK_NAV_MARKER)
            event.stop()
            return
        if key == "backspace" and self._show_back_button:
            self.dismiss(BACK_NAV_MARKER)
            event.stop()
            return
        if key == "escape":
            self.dismiss("")
            event.stop()

    def dismiss(self, result=None) -> None:
        return super().dismiss(result)


class SendAmountScreen(PromptScreen):
    """Prompt screen for entering send amount - Green border to match SEND button."""
    CSS = """
    SendAmountScreen {
        align: center middle;
    }

    SendAmountScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #10b981;
        padding: 1 2;
    }

    SendAmountScreen Static {
        margin-bottom: 0;
    }

    SendAmountScreen #wallet_info {
        color: $accent;
        margin-bottom: 0;
    }

    SendAmountScreen #inp {
        margin-bottom: 0;
    }

    SendAmountScreen #amount_comment {
        margin-top: 1;
        margin-bottom: 0;
        color: #fbbf24;
        text-style: italic;
        min-height: 2;
    }

    SendAmountScreen Horizontal {
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self._title}[/b]", markup=True)
            if self._wallet_info:
                yield Static(f"[dim]{self._wallet_info}[/dim]", id="wallet_info", markup=True)
            if self._fun_note:
                yield Static(f"💡 {self._fun_note}", id="fun_note", markup=True)
            yield Input(placeholder=self._placeholder, password=self._password, id="inp", value=self._initial_value)
            yield Static("", id="amount_comment", markup=True)
            with Horizontal():
                if self._show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button(self._ok_label, id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    @on(Input.Changed, "#inp")
    def on_amount_changed(self, event: Input.Changed) -> None:
        """Show sassy comment based on amount entered."""
        # Get comment widget
        comment_widget = self.query_one("#amount_comment", Static)

        # Try to parse amount
        try:
            inp = self.query_one("#inp", Input)
            filtered = filter_amount_input(event.value)
            if filtered != event.value:
                inp.value = filtered
            value = sanitize_input(filtered)
            if not value:
                comment_widget.update("")
                return

            amount = Decimal(value)
            if amount < 0:
                comment_widget.update("")
                return

            # Show sassy comment based on amount
            comment = get_amount_comment(amount)
            comment_widget.update(f"[dim italic]{comment}[/dim italic]")
        except (ValueError, decimal.InvalidOperation):
            comment_widget.update("")


class SendPassphraseScreen(PromptScreen):
    """Prompt screen for entering passphrase for send - Green border to match SEND button."""
    def __init__(self, *args, error_note: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._error_note = error_note

    CSS = """
    SendPassphraseScreen {
        align: center middle;
    }

    SendPassphraseScreen > Vertical {
        width: 72;
        min-width: 72;
        max-width: 72;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #10b981;
        padding: 1 2;
    }

    SendPassphraseScreen Static {
        margin-bottom: 0;
    }

    SendPassphraseScreen #title {
        color: #fbbf24;
    }

    SendPassphraseScreen #wallet_info {
        color: $accent;
        margin-bottom: 0;
    }

    SendPassphraseScreen #inp {
        margin-top: 1;
        margin-bottom: 1;
    }

    SendPassphraseScreen #error_note {
        margin-top: 0;
        margin-bottom: 1;
        color: #ef4444;
        text-style: bold;
    }

    SendPassphraseScreen Horizontal {
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self._title}[/b]", id="title", markup=True)
            if self._wallet_info:
                yield Static(f"{self._wallet_info}", id="wallet_info", markup=True)
            yield Input(placeholder=self._placeholder, password=self._password, id="inp", value=self._initial_value)
            if self._error_note:
                yield Static(self._error_note, id="error_note", markup=True)
            if self._fun_note:
                yield Static(f"💡 {self._fun_note}", id="fun_note", markup=True)
            with Horizontal():
                if self._show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button(self._ok_label, id="ok", variant="primary")
                yield Button("Cancel", id="cancel")


class BackupConfirmPassphraseScreen(PromptScreen):
    """Prompt screen for confirming backup encryption password (yellow confirm button)."""
    CSS = """
    BackupConfirmPassphraseScreen #ok {
        background: #f97316;
        color: white;
    }

    BackupConfirmPassphraseScreen #ok:hover {
        background: #ea580c;
        color: white;
    }
    """


class BackupPassphraseScreen(ModalScreen[Optional[dict]]):
    """Single-step backup encryption password + confirm."""

    CSS = """
    BackupPassphraseScreen {
        align: center middle;
    }

    BackupPassphraseScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    BackupPassphraseScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    BackupPassphraseScreen #inp_pass,
    BackupPassphraseScreen #inp_confirm {
        margin-top: 1;
        margin-bottom: 1;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    BackupPassphraseScreen #inp_pass:focus,
    BackupPassphraseScreen #inp_confirm:focus {
        border: solid #10b981;
    }

    BackupPassphraseScreen #hint {
        margin-top: 1;
        margin-bottom: 1;
        color: #fbbf24;
        text-style: italic;
        min-height: 2;
    }

    BackupPassphraseScreen Horizontal {
        align: center middle;
    }

    BackupPassphraseScreen Horizontal > Button {
        margin: 0 1;
    }

    BackupPassphraseScreen #ok {
        background: #f97316;
        color: white;
    }

    BackupPassphraseScreen #ok:hover {
        background: #ea580c;
        color: white;
    }
    """

    def __init__(self, hint: str):
        super().__init__()
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]🔐 Backup Encryption Password[/b]", id="title", markup=True)
            yield Input(placeholder="Create encryption password", password=True, id="inp_pass")
            yield Input(placeholder="Confirm encryption password", password=True, id="inp_confirm")
            yield Static(self._hint, id="hint", markup=True)
            with Horizontal():
                yield Button("← Back", id="back", variant="default")
                yield Button("🔒 Encrypt Backup", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#inp_pass", Input).focus()

    def _get_values(self) -> tuple[str, str]:
        p1 = self.query_one("#inp_pass", Input).value
        p2 = self.query_one("#inp_confirm", Input).value
        return p1, p2

    @on(Button.Pressed, "#ok")
    def ok_pressed(self) -> None:
        p1, p2 = self._get_values()
        self.dismiss({"passphrase": p1, "confirm": p2})

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss({BACK_NAV_MARKER: True})

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if isinstance(self.app.focused, Input):
            if key == "enter":
                p1, p2 = self._get_values()
                self.dismiss({"passphrase": p1, "confirm": p2})
                event.stop()
                return
            if key == "escape":
                _focus_cancel_button(self, context="passphrase confirmation", fallbacks=(("#ok", Button),))
                event.stop()
                return
            return
        if key == "escape":
            self.dismiss(None)
            event.stop()
            return
        if _move_focus_in_button_row(self.app.focused, key):
            event.stop()
            return
        if key == "backspace":
            self.dismiss({BACK_NAV_MARKER: True})
            event.stop()
            return


class StakeAmountScreen(PromptScreen):
    """Prompt screen for entering stake amount - Purple border for staking."""
    CSS = """
    StakeAmountScreen {
        align: center middle;
    }

    StakeAmountScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #8b5cf6;
        padding: 1 2;
    }

    StakeAmountScreen Static {
        margin-bottom: 0;
    }

    StakeAmountScreen #wallet_info {
        color: $accent;
        margin-bottom: 0;
    }

    StakeAmountScreen #inp {
        margin-bottom: 0;
    }

    StakeAmountScreen #amount_comment {
        margin-top: 1;
        margin-bottom: 0;
        color: #fbbf24;
        text-style: italic;
        min-height: 2;
    }

    StakeAmountScreen Horizontal {
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self._title}[/b]", markup=True)
            if self._wallet_info:
                yield Static(f"[dim]{self._wallet_info}[/dim]", id="wallet_info", markup=True)
            if self._fun_note:
                yield Static(f"💡 {self._fun_note}", id="fun_note", markup=True)
            yield Input(placeholder=self._placeholder, password=self._password, id="inp", value=self._initial_value)
            yield Static("", id="amount_comment", markup=True)
            with Horizontal():
                if self._show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button(self._ok_label, id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    @on(Input.Changed, "#inp")
    def on_amount_changed(self, event: Input.Changed) -> None:
        """Show comment based on stake amount entered."""
        # Get comment widget
        comment_widget = self.query_one("#amount_comment", Static)

        # Try to parse amount
        try:
            value = sanitize_input(event.value)
            if not value:
                comment_widget.update("")
                return

            amount = Decimal(value)
            if amount < 0:
                comment_widget.update("")
                return

            # Show comment based on amount
            comment = get_amount_comment(amount)
            comment_widget.update(f"[dim italic]{comment}[/dim italic]")
        except (ValueError, decimal.InvalidOperation):
            comment_widget.update("")


class StakePassphraseScreen(PromptScreen):
    """Prompt screen for entering passphrase for stake - Purple border for staking."""
    def __init__(self, *args, error_note: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._error_note = error_note

    CSS = """
    StakePassphraseScreen {
        align: center middle;
    }

    StakePassphraseScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #8b5cf6;
        padding: 1 2;
    }

    StakePassphraseScreen Static {
        margin-bottom: 0;
    }

    StakePassphraseScreen #title {
        color: #fbbf24;
    }

    StakePassphraseScreen #wallet_info {
        color: $accent;
        margin-bottom: 0;
    }

    StakePassphraseScreen #inp {
        margin-top: 1;
        margin-bottom: 1;
    }

    StakePassphraseScreen #error_note {
        margin-top: 0;
        margin-bottom: 1;
        color: #ef4444;
        text-style: bold;
    }

    StakePassphraseScreen Horizontal {
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self._title}[/b]", id="title", markup=True)
            if self._wallet_info:
                yield Static(f"{self._wallet_info}", id="wallet_info", markup=True)
            yield Input(placeholder=self._placeholder, password=self._password, id="inp", value=self._initial_value)
            if self._error_note:
                yield Static(self._error_note, id="error_note", markup=True)
            if self._fun_note:
                yield Static(f"💡 {self._fun_note}", id="fun_note", markup=True)
            with Horizontal():
                if self._show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button(self._ok_label, id="ok", variant="primary")
                yield Button("Cancel", id="cancel")


class WarningPassphraseScreen(StakePassphraseScreen):
    """Prompt screen for passphrase where the flow is 'warning' themed (delegate / change baker)."""

    CSS = """
    WarningPassphraseScreen {
        align: center middle;
    }

    WarningPassphraseScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #eab308;
        padding: 1 2;
    }

    WarningPassphraseScreen Static {
        margin-bottom: 0;
    }

    WarningPassphraseScreen #title {
        color: #fbbf24;
    }

    WarningPassphraseScreen #wallet_info {
        color: $accent;
        margin-bottom: 0;
    }

    WarningPassphraseScreen #inp {
        margin-top: 1;
        margin-bottom: 1;
    }

    WarningPassphraseScreen #error_note {
        margin-top: 0;
        margin-bottom: 1;
        color: #ef4444;
        text-style: bold;
    }

    WarningPassphraseScreen Horizontal {
        align: center middle;
    }
    """


class ConfirmStakeScreen(ModalScreen[dict]):
    """
    Confirmation screen for staking with fee estimation.
    Similar to ConfirmSendScreen but for stake operations.

    Returns dict:
      {
        "ok": bool,
        "fee_mutez": Optional[int],
        "gas_limit": Optional[int],
        "storage_limit": Optional[int],
      }
    """
    CSS = """
    ConfirmStakeScreen {
        align: center middle;
    }

    ConfirmStakeScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #8b5cf6;
        padding: 1 2;
    }

    ConfirmStakeScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ConfirmStakeScreen #summary {
        margin-bottom: 0;
    }

    ConfirmStakeScreen #confirm_comment {
        margin-top: 1;
        margin-bottom: 0;
        color: #fbbf24;
        text-style: italic;
        min-height: 2;
    }

    ConfirmStakeScreen #fee_title {
        margin-bottom: 0;
        color: $accent;
    }

    ConfirmStakeScreen #fee_list {
        height: 4;
        margin-bottom: 1;
    }

    ConfirmStakeScreen #fee_list > ListItem {
        padding: 0 0 0 2;
    }

    ConfirmStakeScreen Horizontal {
        align: center middle;
    }

    ConfirmStakeScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, rpc: str, key, address: str, amount: Decimal, show_back_button: bool = False):
        super().__init__()
        self.rpc = rpc
        self.key = key
        self.address = address
        self.amount = amount
        self.show_back_button = show_back_button
        self._baker_label = self._resolve_baker_label()

        self._estimate: Optional[dict] = None
        self._fee_choice: str = "normal"   # economy|normal|priority
        self._fee_labels: list[Label] = []

        # Estimation pulse
        self._est_timer = None
        self._est_i: int = 0
        self._estimating: bool = False

    def _resolve_baker_label(self) -> str:
        state = get_wallet_chain_state(self.rpc, self.address, force_refresh=True, prefer_rpc=True)
        baker_addr = state.get("delegate") or ""
        if not baker_addr:
            return "—"
        info = get_baker_info(self.rpc, baker_addr, force_refresh=True)
        alias = info.get("alias") if info else None
        if alias:
            return f"{alias} [dim]({baker_addr})[/dim]"
        return baker_addr

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Confirm Stake[/b]", id="title", markup=True)
            yield Static("", id="summary", markup=True)

            yield Static("[b]Fee[/b] (↑/↓ to choose)", id="fee_title", markup=True)
            yield ListView(id="fee_list")

            # Confirmation comment appears here, right before buttons
            yield Static("", id="confirm_comment", markup=True)

            with Horizontal():
                if self.show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button("💎 STAKE", id="stake", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        # Show confirmation comment based on amount
        comment_widget = self.query_one("#confirm_comment", Static)
        confirmation_msg = get_confirmation_comment(self.amount)
        comment_widget.update(f"[dim italic]{confirmation_msg}[/dim italic]")

        self._start_est_pulse()
        self._render_summary(estimating=True)
        self._init_fee_list()
        self._update_fee_list(estimating=True)

        stake_btn = self.query_one("#stake", Button)
        stake_btn.disabled = True
        stake_btn.focus()
        self._estimate_worker()
        self.set_timer(Config.ESTIMATE_FALLBACK_SECONDS, self._apply_estimate_fallback)

    def on_unmount(self) -> None:
        self._stop_est_pulse()

    def _start_est_pulse(self) -> None:
        _start_estimation_pulse(self)

    def _stop_est_pulse(self) -> None:
        _stop_estimation_pulse(self)

    def _tick_est_pulse(self) -> None:
        _tick_estimation_pulse(self)

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)

        if estimating:
            lines = [
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b #fdba74]Address:[/b #fdba74]   {self.address}",
                "",
                f"[b #8b5cf6]To:[/b #8b5cf6]        {self._baker_label}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
            ]
        elif err:
            lines = [
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b #fdba74]Address:[/b #fdba74]   {self.address}",
                "",
                f"[b #8b5cf6]To:[/b #8b5cf6]        {self._baker_label}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
                "",
                f"[red]Fee estimate failed:[/red] {err}",
                "",
                "You can still STAKE (autofill).",
            ]
        else:
            lines = [
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b #fdba74]Address:[/b #fdba74]   {self.address}",
                "",
                f"[b #8b5cf6]To:[/b #8b5cf6]        {self._baker_label}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))

    def _init_fee_list(self) -> None:
        _init_fee_rows(self)

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        """Update fee rows text + checkmark."""
        if not self._fee_labels:
            self._init_fee_list()

        _update_fee_title(self, estimating=estimating, debug_context="Failed to update fee title in stake confirm")

        texts = _build_fee_rows_text(
            self._fee_choice,
            estimate=self._estimate,
            estimating=estimating,
            err=err,
        )

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

        lv = self.query_one("#fee_list", ListView)
        lv.index = _fee_index_from_choice(self._fee_choice)

    @work(exclusive=True, thread=True)
    def _estimate_worker(self) -> None:
        """Estimate stake operation in background thread."""
        try:
            est_result = estimate_stake(self.rpc, self.key, self.amount)
            self.app._ui(self._on_estimate_success, est_result)
        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Stake estimation failed", exception=e)
            self.app._ui(self._on_estimate_error, str(e))

    def _on_estimate_success(self, est_result: dict) -> None:
        self._estimate = est_result
        self._stop_est_pulse()
        self._render_summary()
        self._update_fee_list()
        self._enable_stake_button()

    def _on_estimate_error(self, error_msg: str) -> None:
        self._stop_est_pulse()
        self._render_summary(err=error_msg)
        self._update_fee_list(err=error_msg)

    def _enable_stake_button(self) -> None:
        _enable_action_button(self, "#stake", "Failed to enable stake button in stake confirm")

    def _apply_estimate_fallback(self) -> None:
        _apply_basic_estimate_fallback(self, enable_action=self._enable_stake_button)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        _handle_fee_selection(self, event)

    @on(Button.Pressed, "#stake")
    def stake_pressed(self) -> None:
        """User confirmed stake operation."""
        result = {"ok": True}

        result.update(_fee_selection_payload(self._estimate, self._fee_choice))

        self.dismiss(result)

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss({BACK_NAV_MARKER: True})

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        _handle_backspace_escape(
            self,
            event,
            key,
            back_handler=self.back_pressed,
            cancel_handler=self.cancel_pressed,
            back_enabled=self.show_back_button,
        )


class ConfirmUnstakeScreen(ModalScreen[dict]):
    """
    Confirmation screen for unstaking with fee estimation.
    Similar to ConfirmStakeScreen but for unstake operations.

    Returns dict:
      {
        "ok": bool,
        "fee_mutez": Optional[int],
        "gas_limit": Optional[int],
        "storage_limit": Optional[int],
      }
    """
    CSS = """
    ConfirmUnstakeScreen {
        align: center middle;
    }

    ConfirmUnstakeScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #8b5cf6;
        padding: 1 2;
    }

    ConfirmUnstakeScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ConfirmUnstakeScreen #summary {
        margin-bottom: 0;
    }

    ConfirmUnstakeScreen #confirm_comment {
        margin-top: 1;
        margin-bottom: 0;
        color: #fbbf24;
        text-style: italic;
        min-height: 2;
    }

    ConfirmUnstakeScreen #fee_title {
        margin-bottom: 0;
        color: $accent;
    }

    ConfirmUnstakeScreen #fee_list {
        height: 4;
        margin-bottom: 1;
    }

    ConfirmUnstakeScreen #fee_list > ListItem {
        padding: 0 0 0 2;
    }

    ConfirmUnstakeScreen Horizontal {
        align: center middle;
    }

    ConfirmUnstakeScreen Horizontal > Button {
        margin: 0 1;
    }

    ConfirmUnstakeScreen #unstake {
        background: #8b5cf6;
        color: #f8fafc;
    }

    ConfirmUnstakeScreen #unstake:hover {
        background: #7c3aed;
        color: #f8fafc;
    }

    ConfirmUnstakeScreen #unstake:focus {
        background: #6d28d9;
        color: #f8fafc;
    }
    """

    def __init__(self, rpc: str, key, address: str, amount: Decimal, show_back_button: bool = False):
        super().__init__()
        self.rpc = rpc
        self.key = key
        self.address = address
        self.amount = amount
        self.show_back_button = show_back_button

        self._estimate: Optional[dict] = None
        self._fee_choice: str = "normal"
        self._fee_labels: list[Label] = []

        self._est_timer = None
        self._est_i: int = 0
        self._estimating: bool = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Confirm Unstake[/b]", id="title", markup=True)
            yield Static("", id="summary", markup=True)

            yield Static("[b]Fee[/b] (↑/↓ to choose)", id="fee_title", markup=True)
            yield ListView(id="fee_list")

            yield Static("", id="confirm_comment", markup=True)

            with Horizontal():
                if self.show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button("🔓 UNSTAKE", id="unstake", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        comment_widget = self.query_one("#confirm_comment", Static)
        confirmation_msg = get_confirmation_comment(self.amount)
        comment_widget.update(f"[dim italic]{confirmation_msg}[/dim italic]")

        self._start_est_pulse()
        self._render_summary(estimating=True)
        self._init_fee_list()
        self._update_fee_list(estimating=True)

        unstake_btn = self.query_one("#unstake", Button)
        unstake_btn.disabled = True
        unstake_btn.focus()
        self._estimate_worker()
        self.set_timer(Config.ESTIMATE_FALLBACK_SECONDS, self._apply_estimate_fallback)

    def on_unmount(self) -> None:
        self._stop_est_pulse()

    def _start_est_pulse(self) -> None:
        _start_estimation_pulse(self)

    def _stop_est_pulse(self) -> None:
        _stop_estimation_pulse(self)

    def _tick_est_pulse(self) -> None:
        _tick_estimation_pulse(self)

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)

        if estimating:
            lines = [
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b cyan]Address:[/b cyan]   {self.address}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
            ]
        elif err:
            lines = [
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b cyan]Address:[/b cyan]   {self.address}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
                "",
                f"[red]Fee estimate failed:[/red] {err}",
                "",
                "You can still UNSTAKE (autofill).",
            ]
        else:
            lines = [
                "[b]Confirm Unstake Operation[/b]",
                "",
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b cyan]Address:[/b cyan]   {self.address}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))

    def _init_fee_list(self) -> None:
        _init_fee_rows(self)

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        if not self._fee_labels:
            self._init_fee_list()

        _update_fee_title(self, estimating=estimating, debug_context="Failed to update fee title in unstake confirm")

        texts = _build_fee_rows_text(
            self._fee_choice,
            estimate=self._estimate,
            estimating=estimating,
            err=err,
        )

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

        lv = self.query_one("#fee_list", ListView)
        lv.index = _fee_index_from_choice(self._fee_choice)

    @work(exclusive=True, thread=True)
    def _estimate_worker(self) -> None:
        try:
            est_result = estimate_unstake(self.rpc, self.key, self.amount)
            self.app._ui(self._on_estimate_success, est_result)
        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Unstake estimation failed", exception=e)
            self.app._ui(self._on_estimate_error, str(e))

    def _on_estimate_success(self, est_result: dict) -> None:
        self._estimate = est_result
        self._stop_est_pulse()
        self._render_summary()
        self._update_fee_list()
        self._enable_unstake_button()

    def _on_estimate_error(self, error_msg: str) -> None:
        self._stop_est_pulse()
        self._render_summary(err=error_msg)
        self._update_fee_list(err=error_msg)

    def _enable_unstake_button(self) -> None:
        _enable_action_button(self, "#unstake", "Failed to enable unstake button in unstake confirm")

    def _apply_estimate_fallback(self) -> None:
        _apply_basic_estimate_fallback(self, enable_action=self._enable_unstake_button)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        _handle_fee_selection(self, event)

    @on(Button.Pressed, "#unstake")
    def unstake_pressed(self) -> None:
        result = {"ok": True}

        result.update(_fee_selection_payload(self._estimate, self._fee_choice))

        self.dismiss(result)

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss({BACK_NAV_MARKER: True})

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        _handle_backspace_escape(
            self,
            event,
            key,
            back_handler=self.back_pressed,
            cancel_handler=self.cancel_pressed,
            back_enabled=self.show_back_button,
        )


class NetworkPickerScreen(ModalScreen[str]):
    """Picker para elegir red sin escribir (↑/↓ + Enter o click)."""

    CSS = """
    NetworkPickerScreen {
        align: center middle;
    }

    NetworkPickerScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    NetworkPickerScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    NetworkPickerScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    NetworkPickerScreen #networks {
        height: auto;
        max-height: 7;
        margin-bottom: 1;
    }

    NetworkPickerScreen #networks > ListItem {
        padding: 0 0 0 2;
    }

    NetworkPickerScreen Horizontal {
        align: center middle;
    }

    NetworkPickerScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, current: str):
        super().__init__()
        self.current = current  # "mainnet" / "ghostnet"
        self.options = ["mainnet", "ghostnet"]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Select Network[/b]\nChoose which network to connect to", id="title", markup=True)
            yield ListView(id="networks")
            yield Static(get_modal_message("network"), id="fun_note", markup=True)
            with Horizontal():
                yield Button("Select", id="select")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#networks", ListView)
        lv.clear()

        options = [
            ("mainnet", "Mainnet — https://rpc.tzkt.io/mainnet"),
            ("ghostnet", "Ghostnet — https://rpc.tzkt.io/ghostnet"),
        ]

        for key, desc in options:
            if key == self.current:
                text = f"✓ [black on #3b82f6] CURRENT [/black on #3b82f6]  {desc}"
            else:
                text = f"  {desc}"
            lv.append(ListItem(Label(text, markup=True)))

        try:
            lv.index = 0 if self.current == "mainnet" else 1
        except ValueError as e:
            log_error("Failed to set network selection index", exception=e)

        lv.focus()

    @on(ListView.Selected)
    def choose_with_enter(self, event: ListView.Selected) -> None:
        # Selection should not auto-apply; wait for explicit Select/Enter.
        return

    @on(Button.Pressed, "#select")
    def select_pressed(self) -> None:
        lv = self.query_one("#networks", ListView)
        self.dismiss(_selected_value_by_index(lv.index, self.options, self.current))

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss("")

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return
        if key == "enter":
            if isinstance(self.app.focused, ListView):
                lv = self.query_one("#networks", ListView)
                self.dismiss(_selected_value_by_index(lv.index, self.options, self.current))
                event.stop()


class RpcPickerScreen(ModalScreen[str]):
    """Picker para elegir RPC sin escribir (↑/↓ + Enter o click)."""

    CSS = """
    RpcPickerScreen {
        align: center middle;
    }

    RpcPickerScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    RpcPickerScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    RpcPickerScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    RpcPickerScreen #rpcs {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }

    RpcPickerScreen #rpcs > ListItem {
        padding: 0 0 0 2;
    }

    RpcPickerScreen Horizontal {
        align: center middle;
    }

    RpcPickerScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, current_rpc: str):
        super().__init__()
        self.current_rpc = current_rpc
        self.options: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Select RPC[/b]\nChoose a node to use", id="title", markup=True)
            yield ListView(id="rpcs")
            yield Static(get_modal_message("network"), id="fun_note", markup=True)
            with Horizontal():
                yield Button("Select", id="select")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#rpcs", ListView)
        lv.clear()

        net = network_from_rpc(self.current_rpc)
        candidates = (
            Config.RPC_MAINNET_CANDIDATES
            if net == "mainnet"
            else Config.RPC_GHOSTNET_CANDIDATES
        )

        ordered = candidates[:]
        if self.current_rpc not in ordered:
            ordered = [self.current_rpc] + ordered

        self.options = ordered

        for rpc in ordered:
            if rpc == self.current_rpc:
                text = f"✓ [black on #3b82f6] CURRENT [/black on #3b82f6]  {rpc}"
            else:
                text = f"  {rpc}"
            lv.append(ListItem(Label(text, markup=True)))

        try:
            lv.index = ordered.index(self.current_rpc)
        except ValueError as e:
            log_error("Failed to set RPC selection index", exception=e)

        lv.focus()

    @on(ListView.Selected)
    def choose_with_enter(self, event: ListView.Selected) -> None:
        # Selection should not auto-apply; wait for explicit Select/Enter.
        return

    @on(Button.Pressed, "#select")
    def select_pressed(self) -> None:
        lv = self.query_one("#rpcs", ListView)
        self.dismiss(_selected_value_by_index(lv.index, self.options, self.current_rpc))

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss("")

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return
        if key == "enter":
            if isinstance(self.app.focused, ListView):
                lv = self.query_one("#rpcs", ListView)
                self.dismiss(_selected_value_by_index(lv.index, self.options, self.current_rpc))
                event.stop()


class AddressDetailScreen(ModalScreen[None]):
    """Modal to display full wallet address with copy functionality."""

    CSS = """
    AddressDetailScreen {
        align: center middle;
    }

    AddressDetailScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    AddressDetailScreen #addr_info {
        margin-bottom: 0;
    }

    AddressDetailScreen #addr_full {
        background: $boost;
        padding: 1;
        margin-bottom: 0;
        border: solid $accent;
    }

    AddressDetailScreen Horizontal {
        align: center middle;
    }

    AddressDetailScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, wallet_name: str, address: str):
        super().__init__()
        self.wallet_name = wallet_name
        self.address = address

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                f"[b]Wallet Address Details[/b]\n"
                f"Wallet name: [b]{self.wallet_name}[/b]",
                id="addr_info",
                markup=True
            )
            yield Static(
                f"[b]{self.address}[/b]",
                id="addr_full",
                markup=True
            )
            with Horizontal():
                yield Button("Copy to Clipboard", id="copy", variant="primary")
                yield Button("Close", id="close")

    @on(Button.Pressed, "#copy")
    def copy_pressed(self) -> None:
        try:
            self.app.copy_to_clipboard(self.address)  # type: ignore[attr-defined]
            self.app._status_lock_until_refresh = False  # type: ignore[attr-defined]
            self.app._set_status(f"✅ Address copied: {self.address}")  # type: ignore[attr-defined]
        except (RuntimeError, OSError, ValueError, ImportError) as e:
            log_warning("Clipboard copy failed", exception=e, address=self.address)
            self.app._set_status(f"❌ Copy failed. Address: {self.address}")  # type: ignore[attr-defined]

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "backspace":
            self.dismiss({BACK_NAV_MARKER: True})
            event.stop()
            return
        if key == "escape":
            self.close_pressed()
            event.stop()


class ImportWizardScreen(ModalScreen[Optional[dict]]):
    """Multi-step import flow (type -> details -> optional file pick/passphrase)."""

    CSS = """
    ImportWizardScreen {
        align: center middle;
    }

    ImportWizardScreen > Vertical {
        width: auto;
        min-width: 80;
        max-width: 100;
        height: auto;
        max-height: 44;
        overflow-y: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    ImportWizardScreen .hidden {
        display: none;
    }

    ImportWizardScreen #title {
        margin-top: 0;
        margin-bottom: 1;
        color: $accent;
        padding-left: 1;
    }

    ImportWizardScreen #hint {
        margin-top: 0;
        margin-bottom: 1;
        color: #fbbf24;
        text-style: italic;
        min-height: 1;
        padding-left: 1;
    }

    ImportWizardScreen #mnemonic_hint,
    ImportWizardScreen #secret_hint {
        margin-top: 0;
        margin-bottom: 1;
        color: #94a3b8;
        padding-left: 1;
    }

    ImportWizardScreen #mnemonic_store_hint {
        margin-top: 0;
        margin-bottom: 1;
        color: #fbbf24;
        padding-left: 1;
    }

    ImportWizardScreen #mnemonic_options {
        margin-top: 0;
        max-height: 2;
    }

    ImportWizardScreen #mnemonic_options > ListItem {
        padding: 0 0 0 1;
    }

    ImportWizardScreen #error {
        margin-top: 0;
        margin-bottom: 1;
        color: #f87171;
        min-height: 1;
        padding-left: 1;
    }

    ImportWizardScreen #import_types {
        margin-bottom: 1;
        max-height: 16;
        min-height: 10;
    }

    ImportWizardScreen Input {
        margin-top: 0;
        margin-bottom: 1;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    ImportWizardScreen Input:focus {
        border: solid #10b981;
    }

    ImportWizardScreen #inp_mnemonic {
        height: 3;
        min-height: 3;
    }

    ImportWizardScreen #file_picker {
        height: 12;
        margin-top: 1;
        margin-bottom: 1;
    }

    ImportWizardScreen #browse_row,
    ImportWizardScreen #backup_path_row {
        align: left middle;
    }

    ImportWizardScreen #backup_path_row Input {
        width: 1fr;
        margin-top: 0;
    }

    ImportWizardScreen Horizontal {
        align: center middle;
    }

    ImportWizardScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self._step = "type"
        self._mode: str | None = None
        self._mnemonic_expected = 12
        self._mnemonic_option_selected: set[int] = set()
        self._mnemonic_option_labels: list[Label] = []
        self._mnemonic_option_texts: list[str] = []
        self._backup_data: dict | None = None
        self._backup_encrypted: dict | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="title", markup=True)
            yield Static("", id="error", markup=True)
            yield ListView(id="import_types")
            yield Static("", id="hint", markup=True)
            yield Input(placeholder="Wallet name (e.g., Savings)", id="inp_name")
            yield Input(placeholder="Secret key (edsk... or edesk...)", id="inp_secret", password=True)
            yield Input(
                placeholder="Passphrase for encrypted secret (edesk, if applicable)",
                id="inp_secret_pass",
                password=True,
            )
            yield Input(
                placeholder="12-word mnemonic (space separated)",
                id="inp_mnemonic",
            )
            yield Input(
                placeholder="Derivation path (m/44'/1729'/0'/0') — leave blank for default",
                id="inp_mnemonic_path",
            )
            yield Input(placeholder="BIP39 passphrase (optional)", id="inp_mnemonic_pass", password=True)
            yield Input(placeholder="Password to encrypt wallet", id="inp_passphrase", password=True)
            yield Static(
                "[yellow]Password encrypts keys (AES-256-GCM + scrypt).[/yellow]",
                id="secret_hint",
                markup=True,
            )
            yield Static(
                "[yellow]Password encrypts keys (AES-256-GCM + scrypt).[/yellow]",
                id="mnemonic_store_hint",
                markup=True,
            )
            yield ListView(id="mnemonic_options")
            yield Input(placeholder="Wallet name (e.g., Watcher)", id="inp_watch_name")
            yield Input(placeholder="Public address (tz1...)", id="inp_watch_addr")
            with Vertical(id="backup_path_block"):
                with Horizontal(id="backup_path_row"):
                    yield Input(placeholder="Backup file path", id="inp_backup_path")
                    yield Button("Browse", id="browse", variant="primary")
                yield Static(
                    "[dim]Bulk backups will restore all wallets.[/dim]",
                    id="bulk_hint",
                    markup=True,
                )
            yield Input(placeholder="Backup encryption password", id="inp_backup_pass", password=True)
            yield DirectoryTree(path=Path.home(), id="file_picker")
            with Horizontal(id="browse_row"):
                yield Button("Select", id="select_file", variant="primary")
            with Horizontal():
                yield Button("← Back", id="back", variant="default")
                yield Button("Next", id="next", variant="primary")
                yield Button("Import", id="import", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#import_types", ListView)
        lv.clear()
        for _type_id, title, desc in _IMPORT_TYPE_OPTIONS:
            label_text = f"[b]{title}[/b]\n[dim]{desc}[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))
        lv.index = 0
        options_lv = self.query_one("#mnemonic_options", ListView)
        options_lv.clear()
        self._mnemonic_option_labels.clear()
        self._mnemonic_option_texts = [
            "Use custom derivation path [dim](25 word)[/dim]",
            "Use BIP39 passphrase (25th word) [dim](25 word)[/dim]",
        ]
        for text in self._mnemonic_option_texts:
            lbl = Label(f"[dim]□[/dim] {text}", markup=True)
            self._mnemonic_option_labels.append(lbl)
            options_lv.append(ListItem(lbl))
        self._apply_step()

    def _set_hidden(self, widget, hidden: bool) -> None:
        if hidden:
            widget.add_class("hidden")
        else:
            widget.remove_class("hidden")

    @on(Input.Changed, "#inp_secret")
    def secret_changed(self, event: Input.Changed) -> None:
        inp = self.query_one("#inp_secret", Input)
        filtered = filter_base58_input(event.value)
        if filtered != event.value:
            inp.value = filtered

    @on(Input.Changed, "#inp_secret_pass")
    def secret_pass_changed(self, event: Input.Changed) -> None:
        secret = self.query_one("#inp_secret", Input).value.strip()
        if not secret.startswith("edesk"):
            return
        enc_pass = self.query_one("#inp_passphrase", Input)
        if not enc_pass.value.strip():
            enc_pass.value = event.value

    @on(Input.Changed, "#inp_watch_addr")
    def watch_addr_changed(self, event: Input.Changed) -> None:
        inp = self.query_one("#inp_watch_addr", Input)
        filtered = filter_base58_input(event.value)
        if filtered != event.value:
            inp.value = filtered
        if self._step != "watch":
            return
        if not filtered:
            self._set_error("")
            return
        if len(filtered) < 36:
            self._set_error(f"[dim]Address length: {len(filtered)}/36[/dim]")
            return
        ok, err = validate_tezos_address(filtered, allow_kt1=False)
        if not ok:
            self._set_error(f"[red]✗ {err}[/red]")
        else:
            self._set_error("[#34d399]✓ Address looks valid[/#34d399]")

    @on(Input.Changed, "#inp_mnemonic")
    def mnemonic_changed(self, event: Input.Changed) -> None:
        inp = self.query_one("#inp_mnemonic", Input)
        filtered = filter_mnemonic_input(event.value)
        if filtered != event.value:
            inp.value = filtered

    @on(Input.Changed, "#inp_mnemonic_path")
    def mnemonic_path_changed(self, event: Input.Changed) -> None:
        inp = self.query_one("#inp_mnemonic_path", Input)
        filtered = filter_derivation_path(event.value)
        if filtered != event.value:
            inp.value = filtered

    def _apply_step(self) -> None:
        title = self.query_one("#title", Static)
        hint = self.query_one("#hint", Static)
        error = self.query_one("#error", Static)
        lv = self.query_one("#import_types", ListView)

        inp_name = self.query_one("#inp_name", Input)
        inp_secret = self.query_one("#inp_secret", Input)
        inp_secret_pass = self.query_one("#inp_secret_pass", Input)
        inp_passphrase = self.query_one("#inp_passphrase", Input)
        secret_hint = self.query_one("#secret_hint", Static)
        inp_mnemonic = self.query_one("#inp_mnemonic", Input)
        inp_mnemonic_pass = self.query_one("#inp_mnemonic_pass", Input)
        inp_mnemonic_path = self.query_one("#inp_mnemonic_path", Input)
        mnemonic_store_hint = self.query_one("#mnemonic_store_hint", Static)
        mnemonic_options = self.query_one("#mnemonic_options", ListView)
        inp_watch_name = self.query_one("#inp_watch_name", Input)
        inp_watch_addr = self.query_one("#inp_watch_addr", Input)
        inp_backup_path = self.query_one("#inp_backup_path", Input)
        inp_backup_pass = self.query_one("#inp_backup_pass", Input)
        file_picker = self.query_one("#file_picker", DirectoryTree)
        bulk_hint = self.query_one("#bulk_hint", Static)

        back_btn = self.query_one("#back", Button)
        next_btn = self.query_one("#next", Button)
        browse_btn = self.query_one("#browse", Button)
        select_btn = self.query_one("#select_file", Button)
        import_btn = self.query_one("#import", Button)
        cancel_btn = self.query_one("#cancel", Button)
        browse_row = self.query_one("#browse_row", Horizontal)
        backup_path_row = self.query_one("#backup_path_row", Horizontal)

        error.update("")

        # Hide everything by default
        for w in (
            lv,
            inp_name,
            inp_secret,
            inp_secret_pass,
            inp_passphrase,
            secret_hint,
            inp_mnemonic,
            inp_mnemonic_pass,
            inp_mnemonic_path,
            mnemonic_store_hint,
            mnemonic_options,
            inp_watch_name,
            inp_watch_addr,
            inp_backup_path,
            inp_backup_pass,
            bulk_hint,
            file_picker,
        ):
            self._set_hidden(w, True)

        for b in (back_btn, next_btn, browse_btn, select_btn, import_btn, cancel_btn, browse_row, backup_path_row):
            self._set_hidden(b, True)

        if self._step == "type":
            title.update("[b]🎯 Choose Import Method[/b]\n\nHow would you like to add your wallet?")
            hint.update("Welcome in — this is where the magic starts.")
            self._set_hidden(lv, False)
            self._set_hidden(next_btn, False)
            self._set_hidden(cancel_btn, False)
            lv.focus()
        elif self._step == "secret":
            title.update("[b]🔑 Import with Secret Key[/b]")
            hint.update("We'll derive your address and encrypt your key.")
            self._set_hidden(inp_name, False)
            self._set_hidden(inp_secret, False)
            self._set_hidden(inp_secret_pass, False)
            self._set_hidden(inp_passphrase, False)
            self._set_hidden(secret_hint, False)
            self._set_hidden(back_btn, False)
            self._set_hidden(import_btn, False)
            self._set_hidden(cancel_btn, False)
            inp_name.focus()
        elif self._step == "mnemonic":
            title.update(f"[b]🧠 Import with {self._mnemonic_expected} Words[/b]")
            hint.update(
                f"Paste your {self._mnemonic_expected}-word mnemonic. We'll derive the default account."
            )
            self._set_hidden(inp_name, False)
            self._set_hidden(inp_mnemonic, False)
            self._set_hidden(inp_mnemonic_path, False)
            self._set_hidden(mnemonic_store_hint, False)
            self._set_hidden(inp_mnemonic_pass, False)
            self._set_hidden(inp_passphrase, False)
            self._set_hidden(mnemonic_options, False)
            self._set_hidden(back_btn, False)
            self._set_hidden(import_btn, False)
            self._set_hidden(cancel_btn, False)
            inp_mnemonic.placeholder = (
                f"{self._mnemonic_expected}-word mnemonic (space separated)"
            )
            inp_name.focus()
            self._refresh_mnemonic_options()
            if 0 not in self._mnemonic_option_selected:
                self._set_hidden(inp_mnemonic_path, True)
            if 1 not in self._mnemonic_option_selected:
                self._set_hidden(inp_mnemonic_pass, True)
        elif self._step == "watch":
            title.update("[b]👀 Watch-Only Address[/b]")
            hint.update("Monitor only - no spending keys here.")
            self._set_hidden(inp_watch_name, False)
            self._set_hidden(inp_watch_addr, False)
            self._set_hidden(back_btn, False)
            self._set_hidden(import_btn, False)
            self._set_hidden(cancel_btn, False)
            inp_watch_name.focus()
        elif self._step == "backup":
            title.update("[b]📦 Import from Backup[/b]")
            hint.update("Pick a backup file or browse your disk.")
            self._set_hidden(backup_path_row, False)
            self._set_hidden(inp_backup_path, False)
            self._set_hidden(bulk_hint, False)
            self._set_hidden(back_btn, False)
            self._set_hidden(import_btn, False)
            self._set_hidden(browse_row, False)
            self._set_hidden(browse_btn, False)
            self._set_hidden(cancel_btn, False)
            inp_backup_path.focus()
        elif self._step == "picker":
            title.update("[b]📂 Pick a Backup File[/b]")
            hint.update("Navigate and press Enter to select a file.")
            self._set_hidden(file_picker, False)
            self._set_hidden(back_btn, False)
            self._set_hidden(browse_row, False)
            self._set_hidden(select_btn, False)
            self._set_hidden(cancel_btn, False)
            file_picker.focus()
        elif self._step == "backup_pass":
            title.update("[b]🔐 Backup Encryption Password[/b]")
            hint.update("Unlock the recipe book.")
            self._set_hidden(inp_backup_pass, False)
            self._set_hidden(back_btn, False)
            self._set_hidden(import_btn, False)
            self._set_hidden(cancel_btn, False)
            inp_backup_pass.focus()

    def _get_selected_type(self) -> Optional[str]:
        lv = self.query_one("#import_types", ListView)
        return _selected_option_id(lv.index, _IMPORT_TYPE_OPTIONS)

    def _set_error(self, message: str) -> None:
        self.query_one("#error", Static).update(message)

    def _load_backup_file(self, path: Path) -> Optional[dict]:
        try:
            size_bytes = path.stat().st_size
        except FileNotFoundError:
            self._set_error("❌ Backup file not found.")
            return None
        except _LOCAL_IO_EXCEPTIONS as e:
            self._set_error(f"❌ Failed to read backup metadata: {e}")
            return None
        if size_bytes > Config.BACKUP_MAX_FILE_BYTES:
            self._set_error(
                f"❌ Backup file too large ({size_bytes // 1024} KB). "
                f"Max allowed is {Config.BACKUP_MAX_FILE_BYTES // 1024} KB."
            )
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            self._set_error("❌ Backup file not found.")
            return None
        except json.JSONDecodeError:
            self._set_error("❌ Invalid backup file format.")
            return None
        except _LOCAL_IO_EXCEPTIONS as e:
            self._set_error(f"❌ Failed to read backup: {e}")
            return None
        if not isinstance(data, dict):
            self._set_error("❌ Backup file is not valid.")
            return None
        return data

    @on(Button.Pressed, "#next")
    def next_pressed(self) -> None:
        type_id = self._get_selected_type()
        if not type_id:
            self._set_error("⚠️ Choose an import type first.")
            return
        self._mode = type_id
        if type_id == "mnemonic12":
            self._mnemonic_expected = 12
            self._step = "mnemonic"
        elif type_id == "mnemonic24":
            self._mnemonic_expected = 24
            self._step = "mnemonic"
        elif type_id == "secret":
            self._step = "secret"
        elif type_id == "watch":
            self._step = "watch"
        else:
            self._step = "backup"
        self._apply_step()

    def _refresh_mnemonic_options(self) -> None:
        for idx, lbl in enumerate(self._mnemonic_option_labels):
            mark = "[#3b82f6]■[/#3b82f6]" if idx in self._mnemonic_option_selected else "[dim]□[/dim]"
            text = self._mnemonic_option_texts[idx] if idx < len(self._mnemonic_option_texts) else ""
            lbl.update(f"{mark} {text}")

    def _toggle_mnemonic_option(self, idx: int) -> None:
        if idx in self._mnemonic_option_selected:
            self._mnemonic_option_selected.remove(idx)
        else:
            self._mnemonic_option_selected.add(idx)
        self._refresh_mnemonic_options()
        inp_mnemonic_path = self.query_one("#inp_mnemonic_path", Input)
        inp_mnemonic_pass = self.query_one("#inp_mnemonic_pass", Input)
        if idx == 0:
            if 0 in self._mnemonic_option_selected:
                self._set_hidden(inp_mnemonic_path, False)
                inp_mnemonic_path.focus()
            else:
                inp_mnemonic_path.value = ""
                self._set_hidden(inp_mnemonic_path, True)
        if idx == 1:
            if 1 in self._mnemonic_option_selected:
                self._set_hidden(inp_mnemonic_pass, False)
                inp_mnemonic_pass.focus()
            else:
                inp_mnemonic_pass.value = ""
                self._set_hidden(inp_mnemonic_pass, True)

    @on(ListView.Selected, "#mnemonic_options")
    def mnemonic_option_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        self._toggle_mnemonic_option(idx)

    @on(ListView.Highlighted, "#mnemonic_options")
    def mnemonic_option_highlighted(self, event: ListView.Highlighted) -> None:
        return

    @on(Button.Pressed, "#browse")
    def browse_pressed(self) -> None:
        self._step = "picker"
        self._apply_step()

    @on(Button.Pressed, "#select_file")
    def select_file_pressed(self) -> None:
        tree = self.query_one("#file_picker", DirectoryTree)
        node = tree.cursor_node
        if not node or not node.data:
            self._set_error("⚠️ Select a file first.")
            return
        path = node.data.path
        if path.is_dir():
            return
        self.query_one("#inp_backup_path", Input).value = str(path)
        self._step = "backup"
        self._apply_step()

    @on(DirectoryTree.FileSelected)
    def file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.query_one("#inp_backup_path", Input).value = str(event.path)
        # Keep picker open; user must confirm with Select File.

    @on(Tree.NodeHighlighted, "#file_picker")
    def file_picker_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node = event.node
        entry = getattr(node, "data", None)
        path = getattr(entry, "path", None)
        if not path:
            return
        if path.is_dir():
            return
        self.query_one("#inp_backup_path", Input).value = str(path)

    @on(Button.Pressed, "#import")
    def import_pressed(self) -> None:
        if self._step == "secret":
            name = self.query_one("#inp_name", Input).value.strip()
            secret = self.query_one("#inp_secret", Input).value.strip()
            secret_passphrase = self.query_one("#inp_secret_pass", Input).value.strip()
            passphrase = self.query_one("#inp_passphrase", Input).value.strip()
            if not name or not secret or not passphrase:
                self._set_error("⚠️ Fill all fields to continue.")
                return
            if secret.startswith("edesk") and not secret_passphrase:
                self._set_error("⚠️ Passphrase required for encrypted secret key.")
                return
            self.dismiss(
                {
                    "mode": "secret",
                    "name": name,
                    "secret": secret,
                    "secret_passphrase": secret_passphrase,
                    "passphrase": passphrase,
                }
            )
            return
        if self._step == "watch":
            name = self.query_one("#inp_watch_name", Input).value.strip()
            address = self.query_one("#inp_watch_addr", Input).value.strip()
            if not name or not address:
                self._set_error("⚠️ Name and address required.")
                return
            self.dismiss({"mode": "watch", "name": name, "address": address})
            return
        if self._step == "mnemonic":
            name = self.query_one("#inp_name", Input).value.strip()
            enc_passphrase = self.query_one("#inp_passphrase", Input).value.strip()
            use_path = 0 in self._mnemonic_option_selected
            use_bip39 = 1 in self._mnemonic_option_selected
            bip39_passphrase = (
                self.query_one("#inp_mnemonic_pass", Input).value.strip() if use_bip39 else ""
            )
            derivation_path = (
                self.query_one("#inp_mnemonic_path", Input).value.strip() if use_path else ""
            )
            if not name or not enc_passphrase:
                self._set_error("⚠️ Name and password required.")
                return
            mnemonic = self.query_one("#inp_mnemonic", Input).value.strip()
            if not mnemonic:
                self._set_error("⚠️ Mnemonic required.")
                return
            self.dismiss(
                {
                    "mode": "mnemonic",
                    "name": name,
                    "mnemonic": mnemonic,
                    "bip39_passphrase": bip39_passphrase,
                    "derivation_path": derivation_path,
                    "passphrase": enc_passphrase,
                    "words": self._mnemonic_expected,
                }
            )
            return
        if self._step == "backup":
            path_str = self.query_one("#inp_backup_path", Input).value.strip()
            if not path_str:
                self._set_error("⚠️ Provide a backup file path.")
                return
            backup_path = Path(path_str).expanduser()
            if not backup_path.exists() or not backup_path.is_file():
                self._set_error("❌ Backup file not found.")
                return
            data = self._load_backup_file(backup_path)
            if not data:
                return
            if data.get("encrypted"):
                self._backup_encrypted = data
                self._step = "backup_pass"
                self._apply_step()
                return
            self.dismiss({"mode": "backup", "backup_data": data})
            return
        if self._step == "backup_pass":
            passphrase = self.query_one("#inp_backup_pass", Input).value.strip()
            if not passphrase:
                self._set_error("⚠️ Encryption password required.")
                return
            try:
                backup_type = (self._backup_encrypted or {}).get("backup_type")
                blob_dict = (self._backup_encrypted or {}).get("blob") or {}
                blob = EncryptedBlob(
                    salt_b64=blob_dict.get("salt_b64", ""),
                    nonce_b64=blob_dict.get("nonce_b64", ""),
                    ct_b64=blob_dict.get("ct_b64", ""),
                )
                payload_json = decrypt_secret(blob, passphrase)
                if len(payload_json.encode("utf-8")) > Config.BACKUP_MAX_DECRYPTED_BYTES:
                    self._set_error("❌ Decrypted backup payload is too large.")
                    return
                data = json.loads(payload_json)
                if not isinstance(data, dict):
                    self._set_error("❌ Backup payload is malformed.")
                    return
                if backup_type and not data.get("backup_type"):
                    data["backup_type"] = backup_type
            except _CRYPTO_DECODE_EXCEPTIONS + _LOCAL_IO_EXCEPTIONS:
                self._set_error("❌ Wrong encryption password or corrupted backup.")
                return
            self.dismiss({"mode": "backup", "backup_data": data})

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        if self._step in ("secret", "watch", "backup", "mnemonic"):
            self._step = "type"
        elif self._step == "picker":
            self._step = "backup"
        elif self._step == "backup_pass":
            self._step = "backup"
        self._apply_step()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(DirectoryTree.DirectorySelected, "#backup_dir_picker")
    def backup_dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self._backup_dir = event.path
        self.query_one("#inp_backup_dir", Input).value = str(event.path)

    @on(DirectoryTree.FileSelected, "#backup_dir_picker")
    def backup_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        parent = event.path.parent
        self._backup_dir = parent
        self.query_one("#inp_backup_dir", Input).value = str(parent)

    @on(Tree.NodeHighlighted, "#backup_dir_picker")
    def backup_dir_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node = event.node
        entry = getattr(node, "data", None)
        path = getattr(entry, "path", None)
        if not path:
            return
        use_path = path if path.is_dir() else path.parent
        self._backup_dir = use_path
        self.query_one("#inp_backup_dir", Input).value = str(use_path)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return
        if key == "space" and self._step == "mnemonic":
            lv = self.query_one("#mnemonic_options", ListView)
            if lv.has_focus:
                idx = lv.index
                if idx is not None:
                    self._toggle_mnemonic_option(idx)
                    event.stop()
                    return
        if key == "enter" and self._step == "type":
            self.next_pressed()
            event.stop()
            return
        if key == "enter" and self._step in ("backup", "backup_pass", "secret", "watch"):
            self.import_pressed()
            event.stop()
            return
        if key == "enter" and self._step == "mnemonic":
            self.import_pressed()
            event.stop()
            return


class ImportTypeSelectorScreen(ModalScreen[Optional[str]]):
    """Modal to choose the type of wallet import."""

    CSS = """
    ImportTypeSelectorScreen {
        align: center middle;
    }

    ImportTypeSelectorScreen > Vertical {
        width: auto;
        min-width: 58;
        max-width: 72;
        height: auto;
        max-height: 22;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    ImportTypeSelectorScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ImportTypeSelectorScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    ImportTypeSelectorScreen #import_types {
        margin-bottom: 1;
        height: auto;
    }

    ImportTypeSelectorScreen #import_types > ListItem {
        padding: 0 0 0 2;
        height: auto;
    }

    ImportTypeSelectorScreen #import_types > ListItem Label {
        height: auto;
    }

    ImportTypeSelectorScreen Horizontal {
        align: center middle;
    }

    ImportTypeSelectorScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]🎯 Choose Import Method[/b]\nHow would you like to add your wallet?", id="title", markup=True)
            yield ListView(id="import_types")
            yield Static(get_modal_message("import"), id="fun_note", markup=True)
            with Horizontal():
                yield Button("Continue", id="select", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#import_types", ListView)
        lv.clear()

        for type_id, title, description in _IMPORT_TYPE_OPTIONS:
            label_text = f"[b]{title}[/b]\n[dim]{description}[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))

        lv.index = 0
        lv.focus()

    def _get_selected_type(self) -> Optional[str]:
        lv = self.query_one("#import_types", ListView)
        return _selected_option_id(lv.index, _IMPORT_TYPE_OPTIONS)

    @on(Button.Pressed, "#select")
    def select_pressed(self) -> None:
        type_id = self._get_selected_type()
        if type_id:
            self.dismiss(type_id)

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "backspace":
            self.dismiss({BACK_NAV_MARKER: True})
            event.stop()
            return
        if key == "escape":
            self.dismiss(None)
            event.stop()


class ImportSecretScreen(ModalScreen[Optional[dict]]):
    """Modal to import a wallet with secret key in one step."""

    CSS = """
    ImportSecretScreen {
        align: center middle;
    }

    ImportSecretScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    ImportSecretScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ImportSecretScreen #inp_name,
    ImportSecretScreen #inp_secret,
    ImportSecretScreen #inp_secret_pass,
    ImportSecretScreen #inp_passphrase {
        margin-top: 1;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    ImportSecretScreen #inp_passphrase {
        margin-bottom: 1;
    }

    ImportSecretScreen #inp_name:focus,
    ImportSecretScreen #inp_secret:focus,
    ImportSecretScreen #inp_secret_pass:focus,
    ImportSecretScreen #inp_passphrase:focus {
        border: solid #10b981;
    }

    ImportSecretScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    ImportSecretScreen #secret_hint {
        margin-top: 0;
        margin-bottom: 0;
        color: #fbbf24;
    }

    ImportSecretScreen Horizontal {
        align: center middle;
    }

    ImportSecretScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]🔑 Import with Secret Key[/b]\nEnter all fields to add your wallet.", id="title", markup=True)
            yield Input(placeholder="Wallet name (e.g., Savings)", id="inp_name")
            yield Input(placeholder="Secret key (edsk... or edesk...)", id="inp_secret", password=True)
            yield Input(placeholder="Passphrase for encrypted secret (edesk, if applicable)", id="inp_secret_pass", password=True)
            yield Input(placeholder="Password to encrypt wallet", id="inp_passphrase", password=True)
            yield Static(
                "[yellow]Password encrypts keys (AES-256-GCM + scrypt).[/yellow]",
                id="secret_hint",
                markup=True,
            )
            yield Static("💡 We'll derive your address and encrypt your key.", id="fun_note", markup=True)
            with Horizontal():
                yield Button("← Back", id="back", variant="default")
                yield Button("🥖 Import!", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#inp_name", Input).focus()

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            name = self.query_one("#inp_name", Input).value
            secret = self.query_one("#inp_secret", Input).value
            secret_passphrase = self.query_one("#inp_secret_pass", Input).value
            passphrase = self.query_one("#inp_passphrase", Input).value
            self.dismiss({
                "name": name,
                "secret": secret,
                "secret_passphrase": secret_passphrase,
                "passphrase": passphrase,
            })
        elif event.button.id == "back":
            self.dismiss({BACK_NAV_MARKER: True})
        else:
            self.dismiss(None)

    @on(Input.Changed, "#inp_secret_pass")
    def secret_pass_changed(self, event: Input.Changed) -> None:
        secret = self.query_one("#inp_secret", Input).value.strip()
        if not secret.startswith("edesk"):
            return
        enc_pass = self.query_one("#inp_passphrase", Input)
        if not enc_pass.value.strip():
            enc_pass.value = event.value

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if _handle_input_escape_focus_cancel(
            self,
            event,
            key,
            context="import secret screen",
            fallbacks=(("#ok", Button),),
        ):
            return
        if key == "escape":
            self.dismiss(None)
            event.stop()


class ImportWatchScreen(ModalScreen[Optional[dict]]):
    """Modal to import a watch-only wallet in one step."""

    CSS = """
    ImportWatchScreen {
        align: center middle;
    }

    ImportWatchScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    ImportWatchScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ImportWatchScreen #inp_name,
    ImportWatchScreen #inp_address {
        margin-top: 1;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    ImportWatchScreen #inp_name:focus,
    ImportWatchScreen #inp_address:focus {
        border: solid #10b981;
    }

    ImportWatchScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    ImportWatchScreen Horizontal {
        align: center middle;
    }

    ImportWatchScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]👀 Import Watch-Only[/b]\nAdd a wallet address to monitor.", id="title", markup=True)
            yield Input(placeholder="Wallet name (e.g., Cold Storage)", id="inp_name")
            yield Input(placeholder="Tezos address (tz1/2/3/4...)", id="inp_address")
            yield Static("💡 Watch-only means no sending. Just observing.", id="fun_note", markup=True)
            with Horizontal():
                yield Button("← Back", id="back", variant="default")
                yield Button("🥖 Import!", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#inp_name", Input).focus()

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            name = self.query_one("#inp_name", Input).value
            address = self.query_one("#inp_address", Input).value
            self.dismiss({
                "name": name,
                "address": address,
            })
        elif event.button.id == "back":
            self.dismiss({BACK_NAV_MARKER: True})
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if _handle_input_escape_focus_cancel(
            self,
            event,
            key,
            context="import watch screen",
            fallbacks=(("#ok", Button),),
        ):
            return
        if key == "escape":
            self.dismiss(None)
            event.stop()


class WalletSelectorScreen(ModalScreen[Optional["Account"]]):
    """Modal to select a wallet from the available accounts."""

    CSS = """
    WalletSelectorScreen {
        align: center middle;
    }

    WalletSelectorScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    WalletSelectorScreen #title {
        margin-bottom: 0;
        color: $accent;
    }

    WalletSelectorScreen #wallets_list {
        max-height: 7;
        margin-bottom: 0;
    }

    WalletSelectorScreen #wallets_list > ListItem {
        padding: 0 0 0 2;
    }

    WalletSelectorScreen Horizontal {
        align: center middle;
    }

    WalletSelectorScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, accounts: list, title: str = "Select Wallet", message: str = "Choose a wallet:", button_label: str = "Select", button_variant: str = "primary"):
        super().__init__()
        self.accounts = accounts
        self.title_text = title
        self.message_text = message
        self.button_label = button_label
        self.button_variant = button_variant
        self.selected_account: Optional[Account] = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self.title_text}[/b]\n{self.message_text}", id="title", markup=True)
            yield ListView(id="wallets_list")
            with Horizontal():
                yield Button(self.button_label, id="select", variant=self.button_variant)
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#wallets_list", ListView)
        lv.clear()

        if not self.accounts:
            lv.append(ListItem(Label("[dim]No wallets available[/dim]", markup=True)))
            self.query_one("#select", Button).disabled = True
            return

        for acc in self.accounts:
            tag = " (watch)" if acc.enc is None else ""
            addr_short = acc.address[:10] + "…" + acc.address[-8:]
            label_text = f"[b]{acc.name}[/b]{tag}\n[dim]{addr_short}[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))

        lv.index = 0
        lv.focus()

    def _get_selected_account(self) -> Optional["Account"]:
        lv = self.query_one("#wallets_list", ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self.accounts):
            return None
        return self.accounts[idx]

    @on(Button.Pressed, "#select")
    def select_pressed(self) -> None:
        account = self._get_selected_account()
        if account:
            self.dismiss(account)

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.cancel_pressed()
            event.stop()


class BackupWalletSelectorScreen(WalletSelectorScreen):
    """Wallet selector for backup operation - Yellow border to match backup button."""

    CSS = """
    BackupWalletSelectorScreen {
        align: center middle;
    }

    BackupWalletSelectorScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #f97316;
        padding: 1 2;
    }

    BackupWalletSelectorScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    BackupWalletSelectorScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    BackupWalletSelectorScreen #wallets_list {
        max-height: 7;
        margin-bottom: 1;
    }

    BackupWalletSelectorScreen #wallets_list > ListItem {
        padding: 0 0 0 2;
    }

    BackupWalletSelectorScreen #select {
        background: #f97316;
        color: white;
    }

    BackupWalletSelectorScreen #select:hover {
        background: #ea580c;
        color: white;
    }

    BackupWalletSelectorScreen Horizontal {
        align: center middle;
    }

    BackupWalletSelectorScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self.title_text}[/b]\n{self.message_text}", id="title", markup=True)
            yield ListView(id="wallets_list")
            yield Static(get_modal_message("backup"), id="fun_note", markup=True)
            with Horizontal():
                yield Button(self.button_label, id="select", variant=self.button_variant)
                yield Button("Cancel", id="cancel")


class BackupMultiSelectorScreen(ModalScreen[Optional[dict]]):
    """Modal to select multiple wallets for backup (multi-step)."""

    CSS = """
    BackupMultiSelectorScreen {
        align: center middle;
    }

    BackupMultiSelectorScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 36;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    BackupMultiSelectorScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    BackupMultiSelectorScreen #hint {
        margin-bottom: -1;
        color: #fbbf24;
        text-style: italic;
    }

    BackupMultiSelectorScreen #wallets {
        max-height: 10;
        margin-bottom: 1;
    }

    BackupMultiSelectorScreen #wallets > ListItem {
        padding: 0 0 0 2;
    }

    BackupMultiSelectorScreen #wallets_row {
        align: left top;
        margin-bottom: 1;
    }

    BackupMultiSelectorScreen Horizontal {
        align: center middle;
    }

    BackupMultiSelectorScreen Horizontal > Button {
        margin: 0 1;
    }

    BackupMultiSelectorScreen .hidden {
        display: none;
    }

    BackupMultiSelectorScreen #backup_selected {
        background: #f97316;
        color: white;
    }

    BackupMultiSelectorScreen #backup_selected:hover {
        background: #ea580c;
        color: white;
    }

    BackupMultiSelectorScreen #inp_pass,
    BackupMultiSelectorScreen #inp_confirm {
        margin-top: 1;
        margin-bottom: 1;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    BackupMultiSelectorScreen #inp_pass:focus,
    BackupMultiSelectorScreen #inp_confirm:focus {
        border: solid #10b981;
    }

    BackupMultiSelectorScreen #inp_backup_dir {
        margin-top: 0;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    BackupMultiSelectorScreen #inp_backup_dir:focus {
        border: solid #10b981;
    }

    BackupMultiSelectorScreen #backup_dir_picker {
        height: 8;
        margin-top: 1;
        margin-bottom: 1;
    }

    BackupMultiSelectorScreen .dimmed {
        opacity: 0.6;
    }

    BackupMultiSelectorScreen #backup_path_row {
        align: left middle;
        margin-top: 0;
        margin-bottom: 0;
    }

    BackupMultiSelectorScreen #backup_path_row Input {
        width: 1fr;
        margin-top: 0;
    }
    """

    def __init__(self, accounts: list["Account"]):
        super().__init__()
        self.accounts = accounts
        self._selected: set[int] = set()
        self._labels: list[Label] = []
        self._step: str = "select"
        self._mode: str | None = None
        self._backup_hint: str = ""
        self._backup_dir: Path = Path("data/backups")
        self._browse_open: bool = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="title", markup=True)
            yield Static("", id="hint", markup=True)
            with Horizontal(id="wallets_row"):
                yield ListView(id="wallets")
            with Horizontal(id="backup_path_row"):
                yield Input(placeholder="Backup folder", id="inp_backup_dir")
                yield Button("Browse", id="browse_dir", variant="warning")
            yield DirectoryTree(path=Path.home(), id="backup_dir_picker")
            yield Input(placeholder="Create encryption password", password=True, id="inp_pass")
            yield Input(placeholder="Confirm encryption password", password=True, id="inp_confirm")
            yield Static("", id="pass_hint", markup=True)
            with Horizontal():
                yield Button("Back", id="back", variant="default")
                yield Button("Select all", id="select_all")
                yield Button("Backup Selected", id="backup_selected", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#wallets", ListView)
        lv.clear()
        self._labels.clear()
        for acc in self.accounts:
            tag = " (watch)" if acc.enc is None else ""
            addr_short = acc.address[:10] + "…" + acc.address[-8:]
            text = f"[dim]□[/dim] {acc.name}{tag} — {addr_short}"
            lbl = Label(text, markup=True)
            self._labels.append(lbl)
            lv.append(ListItem(lbl))
        if self.accounts:
            lv.index = 0
            lv.focus()
        self._update_buttons()
        self._apply_dir_mode()
        self._apply_step()

    def _apply_step(self) -> None:
        title = self.query_one("#title", Static)
        hint = self.query_one("#hint", Static)
        wallets = self.query_one("#wallets", ListView)
        wallets_row = self.query_one("#wallets_row", Horizontal)
        backup_path_row = self.query_one("#backup_path_row", Horizontal)
        inp_backup_dir = self.query_one("#inp_backup_dir", Input)
        backup_dir_picker = self.query_one("#backup_dir_picker", DirectoryTree)
        browse_dir = self.query_one("#browse_dir", Button)
        inp_pass = self.query_one("#inp_pass", Input)
        inp_confirm = self.query_one("#inp_confirm", Input)
        pass_hint = self.query_one("#pass_hint", Static)
        backup_selected = self.query_one("#backup_selected", Button)
        back_btn = self.query_one("#back", Button)
        select_all = self.query_one("#select_all", Button)

        if self._step == "select":
            title.update("[b]Backup Wallets[/b]\nSelect one or many wallets")
            hint.update("Tip: Space/Enter to toggle. Use Select all for bulk backup.")
            self._backup_hint = ""
            pass_hint.update("")
            self._browse_open = False
            wallets.remove_class("hidden")
            wallets_row.remove_class("hidden")
            backup_path_row.add_class("hidden")
            inp_backup_dir.add_class("hidden")
            backup_dir_picker.add_class("hidden")
            inp_pass.add_class("hidden")
            inp_confirm.add_class("hidden")
            pass_hint.add_class("hidden")
            pass_hint.update("")
            backup_selected.label = "Backup Selected"
            backup_selected.remove_class("hidden")
            back_btn.add_class("hidden")
            select_all.remove_class("hidden")
            wallets.focus()
        else:
            title.update("[b]🔐 Backup Encryption Password[/b]")
            hint.update("Pick a folder and set an encryption password to protect your file with AES-256-GCM + scrypt.")
            pass_hint.remove_class("hidden")
            pass_hint.update(self._backup_hint or "[dim]Encryption: AES-256-GCM + scrypt.[/dim]")
            wallets.add_class("hidden")
            wallets_row.add_class("hidden")
            backup_path_row.remove_class("hidden")
            inp_backup_dir.remove_class("hidden")
            backup_dir_picker.remove_class("hidden")
            inp_pass.remove_class("hidden")
            inp_confirm.remove_class("hidden")
            backup_selected.label = "Back up"
            backup_selected.disabled = False
            backup_selected.remove_class("hidden")
            back_btn.remove_class("hidden")
            select_all.add_class("hidden")
            inp_backup_dir.value = str(self._backup_dir)
            self._apply_dir_mode()
            browse_dir.focus()

    def _apply_dir_mode(self) -> None:
        inp_backup_dir = self.query_one("#inp_backup_dir", Input)
        backup_dir_picker = self.query_one("#backup_dir_picker", DirectoryTree)
        inp_backup_dir.value = str(self._backup_dir)
        inp_backup_dir.disabled = False
        inp_backup_dir.remove_class("dimmed")
        backup_dir_picker.disabled = False
        backup_dir_picker.remove_class("dimmed")
        if self._browse_open:
            backup_dir_picker.remove_class("hidden")
        else:
            backup_dir_picker.add_class("hidden")

    def _toggle_index(self, idx: int) -> None:
        if idx in self._selected:
            self._selected.remove(idx)
        else:
            self._selected.add(idx)
        self._refresh_labels()
        self._update_buttons()

    def _refresh_labels(self) -> None:
        for i, acc in enumerate(self.accounts):
            mark = "[#eab308]■[/#eab308]" if i in self._selected else "[dim]□[/dim]"
            tag = " (watch)" if acc.enc is None else ""
            addr_short = acc.address[:10] + "…" + acc.address[-8:]
            self._labels[i].update(f"{mark} {acc.name}{tag} — {addr_short}")

    def _update_buttons(self) -> None:
        btn = self.query_one("#backup_selected", Button)
        select_all = self.query_one("#select_all", Button)
        if self._step == "select":
            btn.disabled = not self._selected
            if not self.accounts:
                select_all.disabled = True
            else:
                select_all.disabled = False
                if len(self._selected) == len(self.accounts):
                    select_all.label = "Clear all"
                else:
                    select_all.label = "Select all"
        else:
            btn.disabled = False

    def _toggle_select_all(self) -> None:
        if not self.accounts:
            return
        if len(self._selected) == len(self.accounts):
            self._selected.clear()
        else:
            self._selected = set(range(len(self.accounts)))
        self._refresh_labels()
        self._update_buttons()

    @on(ListView.Selected, "#wallets")
    def list_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        self._toggle_index(idx)

    @on(Button.Pressed, "#backup_selected")
    def backup_selected_pressed(self) -> None:
        if self._step == "passphrase":
            self._submit_backup()
            return
        if not self._selected:
            return
        self._mode = "selected"
        self._step = "passphrase"
        self._apply_step()

    @on(Button.Pressed, "#select_all")
    def select_all_pressed(self) -> None:
        if not self.accounts:
            return
        self._toggle_select_all()

    def _submit_backup(self) -> None:
        inp_backup_dir = self.query_one("#inp_backup_dir", Input)
        inp_pass = self.query_one("#inp_pass", Input)
        inp_confirm = self.query_one("#inp_confirm", Input)
        backup_dir = (inp_backup_dir.value or "").strip()
        passphrase = (inp_pass.value or "").strip()
        confirm_passphrase = (inp_confirm.value or "").strip()
        pass_hint = self.query_one("#pass_hint", Static)
        if not backup_dir:
            self._backup_hint = "⚠️ Choose a backup folder."
            pass_hint.update(self._backup_hint)
            inp_backup_dir.focus()
            return
        if not passphrase or not confirm_passphrase:
            self._backup_hint = "⚠️ Both fields are required."
            pass_hint.update(self._backup_hint)
            inp_pass.focus()
            return
        if confirm_passphrase != passphrase:
            self._backup_hint = "⚠️ Hey, this is serious stuff. Pay attention — both encryption passwords must match. 😅"
            pass_hint.update(self._backup_hint)
            inp_pass.focus()
            return
        self._backup_dir = Path(backup_dir).expanduser()
        accounts = [self.accounts[i] for i in sorted(self._selected)]
        if len(accounts) == len(self.accounts):
            self.dismiss({
                "mode": "all",
                "passphrase": passphrase,
                "confirm": confirm_passphrase,
                "backup_dir": str(self._backup_dir),
            })
            return
        self.dismiss({
            "mode": "selected",
            "accounts": accounts,
            "passphrase": passphrase,
            "confirm": confirm_passphrase,
            "backup_dir": str(self._backup_dir),
        })

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self._step = "select"
        self._apply_step()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(DirectoryTree.DirectorySelected, "#backup_dir_picker")
    def backup_dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self._backup_dir = event.path
        self.query_one("#inp_backup_dir", Input).value = str(event.path)

    @on(DirectoryTree.FileSelected, "#backup_dir_picker")
    def backup_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        parent = event.path.parent
        self._backup_dir = parent
        self.query_one("#inp_backup_dir", Input).value = str(parent)

    @on(Tree.NodeHighlighted, "#backup_dir_picker")
    def backup_dir_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node = event.node
        entry = getattr(node, "data", None)
        path = getattr(entry, "path", None)
        if not path:
            return
        use_path = path if path.is_dir() else path.parent
        self._backup_dir = use_path
        self.query_one("#inp_backup_dir", Input).value = str(use_path)

    @on(Tree.NodeSelected, "#backup_dir_picker")
    def backup_dir_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        entry = getattr(node, "data", None)
        path = getattr(entry, "path", None)
        if not path:
            return
        use_path = path if path.is_dir() else path.parent
        self._backup_dir = use_path
        self.query_one("#inp_backup_dir", Input).value = str(use_path)

    @on(Button.Pressed, "#browse_dir")
    def browse_dir_pressed(self) -> None:
        self._browse_open = not self._browse_open
        self._apply_dir_mode()
        if self._browse_open:
            self.query_one("#backup_dir_picker", DirectoryTree).focus()

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return
        if key == "enter" and self._step == "passphrase":
            focused = self.app.focused
            if isinstance(focused, Input) and focused.id in ("inp_pass", "inp_confirm"):
                self._submit_backup()
                event.stop()
                return
        if _move_focus_in_button_row(self.app.focused, key):
            event.stop()
            return
        if key in ("enter", "space"):
            if isinstance(self.app.focused, ListView):
                lv = self.query_one("#wallets", ListView)
                idx = lv.index
                if idx is not None:
                    if idx == 0:
                        self._toggle_select_all()
                    else:
                        self._toggle_index(idx - 1)
                    event.stop()
class DeleteWalletSelectorScreen(WalletSelectorScreen):
    """Wallet selector for delete operation - Red border to match delete button."""

    CSS = """
    DeleteWalletSelectorScreen {
        align: center middle;
    }

    DeleteWalletSelectorScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #ef4444;
        padding: 1 2;
    }

    DeleteWalletSelectorScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    DeleteWalletSelectorScreen #fun_note {
        color: #f87171;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    DeleteWalletSelectorScreen #wallets_list {
        max-height: 7;
        margin-bottom: 1;
    }

    DeleteWalletSelectorScreen #wallets_list > ListItem {
        padding: 0 0 0 2;
    }

    DeleteWalletSelectorScreen #select {
        background: #ef4444;
        color: white;
    }

    DeleteWalletSelectorScreen #select:hover {
        background: #dc2626;
        color: white;
    }

    DeleteWalletSelectorScreen Horizontal {
        align: center middle;
    }

    DeleteWalletSelectorScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self.title_text}[/b]\n{self.message_text}", id="title", markup=True)
            yield ListView(id="wallets_list")
            yield Static(get_modal_message("delete"), id="fun_note", markup=True)
            with Horizontal():
                yield Button(self.button_label, id="select", variant=self.button_variant)
                yield Button("Cancel", id="cancel")


class ReceiveScreen(ModalScreen[None]):
    CSS = """
    ReceiveScreen {
        align: center middle;
    }

    ReceiveScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #374151;
        padding: 1 2;
    }

    ReceiveScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ReceiveScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 0;
        margin-bottom: 0;
        height: 1;
        padding: 0;
        background: $panel;
    }

    ReceiveScreen #wallet_selector_label {
        margin-bottom: 1;
        color: $accent;
    }

    ReceiveScreen #wallet_selector {
        margin-bottom: 1;
        min-height: 6;
        max-height: 6;
    }

    ReceiveScreen #wallet_selector > ListItem {
        padding: 0 0 0 2;
    }

    ReceiveScreen #address_box {
        margin-bottom: 1;
        padding: 1;
        background: $boost;
        border: solid #10b981;
        align: left middle;
        height: auto;
        min-height: 3;
    }

    ReceiveScreen #address_text {
        width: 1fr;
        text-align: left;
        height: auto;
    }

    ReceiveScreen #status_msg {
        margin-bottom: 0;
        height: 1;
        text-align: center;
    }

    ReceiveScreen Horizontal {
        align: center middle;
    }

    ReceiveScreen Horizontal > Button {
        margin: 0 1;
    }

    ReceiveScreen #copy {
        background: #374151;
        color: white;
    }

    ReceiveScreen #copy:hover {
        background: #1f2937;
        color: white;
    }
    """

    RECEIVE_MESSAGES = [
        "🥖 Time to get some bread!",
        "🍞 Fresh dough incoming?",
        "💰 Ready to fill the breadbasket?",
        "🥐 Someone wants to butter you up!",
        "🎂 Let the cake come to you!",
        "🧁 Sweet XTZ incoming!",
        "🥯 Bagel delivery address below!",
        "🫓 Flatbread funds? We're ready!",
        "🥨 Twist and receive!",
        "🧇 Waffle wallet activated!",
    ]

    def __init__(self, address: str, accounts: list["Account"]):
        super().__init__()
        self.address = address
        self.accounts = accounts
        import secrets
        self._fun_message = secrets.choice(self.RECEIVE_MESSAGES)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]💸 Receive XTZ[/b]\nCopy this address to receive funds", id="title", markup=True)
            yield Static("[b]Choose Wallet:[/b]", id="wallet_selector_label", markup=True)
            yield ListView(id="wallet_selector")
            with Horizontal(id="address_box"):
                yield Static(
                    f"[b]{self.address}[/b]\n[dim]👆 Share this address to receive XTZ[/dim]",
                    id="address_text",
                    markup=True,
                )
                yield Button("Copy", id="copy", variant="primary")
            yield Static(self._fun_message, id="fun_note", markup=True)
            yield Static("", id="status_msg", markup=True)
            with Horizontal():
                yield Button("Done", id="done", variant="default")

    def on_mount(self) -> None:
        lv = self.query_one("#wallet_selector", ListView)
        lv.clear()
        for acc in self.accounts:
            tag = " (watch)" if acc.enc is None else ""
            addr_short = acc.address[:10] + "…" + acc.address[-8:]
            label_text = f"[b]{acc.name}[/b]{tag}\n[dim]{addr_short}[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))

        # Preselect the current address if possible
        idx = next((i for i, acc in enumerate(self.accounts) if acc.address == self.address), 0)
        lv.index = idx
        if self.accounts and lv.index is not None:
            self._set_address(self.accounts[lv.index].address)

    def _set_address(self, address: str) -> None:
        self.address = address
        try:
            self.query_one("#address_text", Static).update(
                f"[b]{self.address}[/b]\n[dim]👆 Share this address to receive XTZ[/dim]"
            )
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to update receive address text", exception=str(e), address=address)

    @on(ListView.Selected, "#wallet_selector")
    def wallet_selected(self, event: ListView.Selected) -> None:
        if event.list_view.index is None:
            return
        idx = event.list_view.index
        if 0 <= idx < len(self.accounts):
            self._set_address(self.accounts[idx].address)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.cancel_pressed()
            event.stop()

    @on(Button.Pressed, "#copy")
    def copy_pressed(self) -> None:
        try:
            self.app.copy_to_clipboard(self.address)  # type: ignore[attr-defined]
            self.app._set_status(f"✅ Address copied: {self.address}")  # type: ignore[attr-defined]
        except (RuntimeError, OSError, ValueError, ImportError) as e:
            log_warning("Clipboard copy failed", exception=e, address=self.address)
            self.app._set_status(f"❌ Copy failed. Address: {self.address}")  # type: ignore[attr-defined]

    @on(Button.Pressed, "#done")
    def done_pressed(self) -> None:
        self.dismiss(None)


class DeleteMultiSelectorScreen(ModalScreen[Optional[list["Account"]]]):
    """Modal to select multiple wallets for deletion."""

    CSS = """
    DeleteMultiSelectorScreen {
        align: center middle;
    }

    DeleteMultiSelectorScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 42;
        background: $surface;
        border: heavy #ef4444;
        padding: 1 2;
    }

    DeleteMultiSelectorScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    DeleteMultiSelectorScreen #hint {
        margin-bottom: 1;
        color: #f87171;
        text-style: italic;
    }

    DeleteMultiSelectorScreen #wallets {
        max-height: 12;
        margin-bottom: 1;
    }

    DeleteMultiSelectorScreen #wallets > ListItem {
        padding: 0 0 0 2;
    }

    DeleteMultiSelectorScreen Horizontal {
        align: center middle;
    }

    DeleteMultiSelectorScreen Horizontal > Button {
        margin: 0 1;
    }

    DeleteMultiSelectorScreen #delete_selected {
        background: #ef4444;
        color: white;
    }

    DeleteMultiSelectorScreen #delete_selected:hover {
        background: #dc2626;
        color: white;
    }
    """

    def __init__(self, accounts: list["Account"]):
        super().__init__()
        self.accounts = accounts
        self._selected: set[int] = set()
        self._labels: list[Label] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Delete Wallets[/b]\nSelect one or many wallets", id="title", markup=True)
            yield Static("Careful: this burns wallets out of the app. 🔥", id="hint", markup=True)
            yield ListView(id="wallets")
            with Horizontal():
                yield Button("Select all", id="select_all")
                yield Button("Delete selected", id="delete_selected", variant="error")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        lv = self.query_one("#wallets", ListView)
        lv.clear()
        self._labels.clear()
        for acc in self.accounts:
            tag = " (watch)" if acc.enc is None else ""
            addr_short = acc.address[:10] + "…" + acc.address[-8:]
            text = f"[dim]□[/dim] {acc.name}{tag} — {addr_short}"
            lbl = Label(text, markup=True)
            self._labels.append(lbl)
            lv.append(ListItem(lbl))
        if self.accounts:
            lv.index = 0
            lv.focus()
        self._update_buttons()

    def _toggle_index(self, idx: int) -> None:
        if idx in self._selected:
            self._selected.remove(idx)
        else:
            self._selected.add(idx)
        self._refresh_labels()
        self._update_buttons()

    def _refresh_labels(self) -> None:
        for i, acc in enumerate(self.accounts):
            mark = "[#ef4444]■[/#ef4444]" if i in self._selected else "[dim]□[/dim]"
            tag = " (watch)" if acc.enc is None else ""
            addr_short = acc.address[:10] + "…" + acc.address[-8:]
            self._labels[i].update(f"{mark} {acc.name}{tag} — {addr_short}")

    def _update_buttons(self) -> None:
        btn = self.query_one("#delete_selected", Button)
        btn.disabled = not self._selected
        select_all = self.query_one("#select_all", Button)
        if not self.accounts:
            select_all.disabled = True
            return
        select_all.disabled = False
        if len(self._selected) == len(self.accounts):
            select_all.label = "Clear all"
        else:
            select_all.label = "Select all"

    @on(ListView.Selected, "#wallets")
    def list_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        self._toggle_index(idx)

    @on(Button.Pressed, "#delete_selected")
    def delete_selected_pressed(self) -> None:
        if not self._selected:
            return
        accounts = [self.accounts[i] for i in sorted(self._selected)]
        self.dismiss(accounts)

    @on(Button.Pressed, "#select_all")
    def select_all_pressed(self) -> None:
        if not self.accounts:
            return
        if len(self._selected) == len(self.accounts):
            self._selected.clear()
        else:
            self._selected = set(range(len(self.accounts)))
        self._refresh_labels()
        self._update_buttons()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.dismiss(None)
            event.stop()
            return
        if key in ("enter", "space"):
            if isinstance(self.app.focused, ListView):
                lv = self.query_one("#wallets", ListView)
                idx = lv.index
                if idx is not None:
                    self._toggle_index(idx)
                    event.stop()
            return


class StakeScreen(ModalScreen[Optional[dict]]):
    """Modal for Delegation and Staking operations. Returns action data or None if cancelled."""

    CSS = """
    StakeScreen {
        align: center middle;
    }

    StakeScreen #stake_root.hidden {
        display: none;
    }

    StakeScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        overflow-y: auto;
        background: $surface;
        border: heavy #8b5cf6;
        padding: 1 2;
    }

    StakeScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    StakeScreen #wallet_selector_label {
        margin-bottom: 1;
    }

    StakeScreen #wallet_selector {
        margin-bottom: 1;
        max-height: 8;
    }

    StakeScreen #wallet_selector > ListItem {
        padding: 0 0 0 2;
    }

    StakeScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    StakeScreen #info_row {
        margin-bottom: 1;
        padding: 1 2;
        height: auto;
        background: $panel;
        border: solid #374151;
        display: none;
        text-align: left;
    }

    StakeScreen #info_box {
        width: 1fr;
    }

    StakeScreen #change_baker_btn {
        margin-left: 2;
        background: #2563eb;
        color: #f8fafc;
    }

    StakeScreen #change_baker_btn:hover {
        background: #1d4ed8;
        color: #f8fafc;
    }

    StakeScreen #input_container {
        margin-bottom: 1;
        display: none;
    }

    StakeScreen #input_label {
        margin-bottom: 1;
    }

    StakeScreen #input_hint {
        margin-top: 1;
        margin-bottom: 1;
        height: auto;
    }

    StakeScreen #amount_comment {
        margin-top: 0;
        margin-bottom: 1;
        color: #fbbf24;
        text-style: italic;
        min-height: 1;
    }

    StakeScreen Input {
        margin-top: 0;
        margin-bottom: 0;
        border: solid #4b5563;
        background: transparent;
        padding: 0 1;
    }

    StakeScreen Input:focus {
        border: solid #10b981;
    }

    StakeScreen #status_msg {
        margin-bottom: 1;
        height: auto;
        text-align: center;
    }

    StakeScreen Horizontal {
        align: center middle;
    }

    StakeScreen Horizontal > Button {
        margin: 0 1;
        border: none;
    }

    StakeScreen .hidden {
        display: none;
    }

    StakeScreen #delegate_btn {
        background: #f59e0b;
        color: white;
    }

    StakeScreen #delegate_btn:hover {
        background: #d97706;
        color: white;
    }

    StakeScreen #stake_btn {
        background: #8b5cf6;
        color: white;
    }

    StakeScreen #stake_btn:hover {
        background: #7c3aed;
        color: white;
    }

    StakeScreen #unstake_btn {
        background: #8b5cf6;
        color: white;
    }

    StakeScreen #unstake_btn:hover {
        background: #7c3aed;
        color: white;
    }

    StakeScreen #select_wallet_btn {
        background: #10b981;
        color: white;
    }

    StakeScreen #select_wallet_btn:hover {
        background: #059669;
        color: white;
    }
    """

    def __init__(
        self,
        accounts: list["Account"],
        rpc: str,
        wallet_info_cache: Optional[dict[str, dict]] = None,
        initial_ctx: Optional[dict] = None,
    ):
        super().__init__()
        # Filter only accounts with secret keys (not watch-only)
        self.accounts = [acc for acc in accounts if acc.enc is not None]
        self.rpc = rpc
        self.selected_account: Optional["Account"] = None
        self.balance_xtz: Decimal = Decimal(0)
        self.delegate_addr: Optional[str] = None
        self.staked_mutez: int = 0
        self.unstaked_mutez: int = 0
        self.staking_active: bool = False
        self.is_delegated: bool = False
        self._delegation_pending: bool = False
        self._change_baker_mode: bool = False
        self._polling_timer = None
        self._blocked_new_wallet: bool = False
        # Cache wallet info to avoid re-fetching when selecting
        self._wallet_info_cache: dict[str, dict] = wallet_info_cache if wallet_info_cache is not None else {}
        self._initial_ctx = initial_ctx or {}
        self._wallet_selector_target_index: int = 0
        self._stake_status_grace_seconds: float = 180.0
        self._stake_action_in_progress: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="stake_root"):
            yield Static("[b]⚡ Stake Manager[/b]", id="title", markup=True)

            # Wallet selector
            yield Static("[b]Choose Wallet:[/b]", id="wallet_selector_label", markup=True)
            yield ListView(id="wallet_selector")
            yield Static("💡 Who’s the lucky wallet becoming a staking CHAD today? Let’s lock in some XTZ! 💪", id="fun_note", markup=True)

            # Info row (hidden initially, shown after wallet selection)
            with Horizontal(id="info_row"):
                yield Static("", id="info_box", markup=True)
                # Inline "Change Baker" to avoid changing modal size
                yield Button("Change Baker", id="change_baker_btn", variant="default")

            # Input container (hidden initially)
            with Vertical(id="input_container"):
                yield Static("", id="input_label", markup=True)
                yield Input(placeholder="", id="input_field")
                yield Static("", id="input_hint", markup=True)
                yield Static("", id="amount_comment", markup=True)

            yield Static("", id="status_msg", markup=True)

            # Buttons
            with Horizontal(id="button_container"):
                yield Button("◀ Back", id="back_btn", variant="default", classes="hidden")
                yield Button("Select", id="select_wallet_btn", variant="primary")
                yield Button("Delegate", id="delegate_btn", variant="warning", classes="hidden")
                yield Button("Stake", id="stake_btn", variant="primary", classes="hidden")
                yield Button("Unstake", id="unstake_btn", variant="warning", classes="hidden")
                yield Button("Cancel", id="cancel")

    def _stake_selector_delegation_tag(self, delegate_addr: Optional[str]) -> str:
        if delegate_addr:
            return "[yellow]Delegated[/yellow]"
        return "[red]Not Delegated[/red]"

    def _format_stake_selector_row(
        self,
        *,
        account_name: str,
        address: str,
        balance_mutez: int,
        staked_mutez: int,
        delegate_addr: Optional[str],
    ) -> str:
        addr_short = address[:10] + "…" + address[-8:]
        balance_xtz = mutez_to_xtz(max(0, int(balance_mutez or 0)))
        staked_xtz = mutez_to_xtz(max(0, int(staked_mutez or 0)))
        balance_tag = f"[#34d399]{format_xtz(balance_xtz)} ꜩ[/#34d399]"
        staked_tag = f"[#8b5cf6]{format_xtz_precise(staked_xtz)} Staked[/#8b5cf6]"
        delegation_tag = self._stake_selector_delegation_tag(delegate_addr)
        return f"[b]{account_name}[/b] {balance_tag} {staked_tag}\n[dim]{addr_short}[/dim] {delegation_tag}"

    def on_mount(self) -> None:
        """Populate wallet selector with delegation/staking status."""
        lv = self.query_one("#wallet_selector", ListView)
        lv.clear()

        if not self.accounts:
            label_text = "[dim]No wallets with secret keys available[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))
        else:
            # Render cached info immediately when available to avoid flicker
            for acc in self.accounts:
                addr_short = acc.address[:10] + "…" + acc.address[-8:]
                cached_info = self._wallet_info_cache.get(acc.address)
                if cached_info:
                    delegate_addr = cached_info.get("delegate_addr")
                    balance_mutez = cached_info.get("balance_mutez", 0)
                    staked_mutez = cached_info.get("staked_mutez", 0)
                    label_text = self._format_stake_selector_row(
                        account_name=acc.name,
                        address=acc.address,
                        balance_mutez=int(balance_mutez or 0),
                        staked_mutez=int(staked_mutez or 0),
                        delegate_addr=delegate_addr,
                    )
                else:
                    label_text = f"[b]{acc.name}[/b] [dim]Loading... ꜩ[/dim] [dim]STK ...[/dim]\n[dim]{addr_short}[/dim]"
                lv.append(ListItem(Label(label_text, markup=True)))

            lv.index = 0

            # Refresh data asynchronously without blocking UI
            self.run_worker(self._load_wallet_statuses, exclusive=False, thread=True)

        self._wallet_selector_target_index = 0
        self.set_timer(0.01, self._apply_wallet_selector_index)
        self.call_later(self._apply_initial_ctx)

    def _apply_initial_ctx(self) -> None:
        """Restore a previous selection/amount when returning from Back."""
        if not self._initial_ctx or not self.accounts:
            return

        account = self._initial_ctx.get("account")
        amount = self._initial_ctx.get("amount")
        if not account:
            return

        idx = None
        for i, acc in enumerate(self.accounts):
            if acc.address == getattr(account, "address", None):
                idx = i
                break
        if idx is None:
            return

        try:
            lv = self.query_one("#wallet_selector", ListView)
            lv.index = idx
            self._wallet_selector_target_index = idx
            self.set_timer(0.01, self._apply_wallet_selector_index)
            self._select_wallet(idx)
            if amount is not None:
                input_field = self.query_one("#input_field", Input)
                input_field.value = str(amount)
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to restore stake context", exception=e)

    def _apply_wallet_selector_index(self) -> None:
        try:
            lv = self.query_one("#wallet_selector", ListView)
            if not lv.children:
                return
            idx = max(0, min(self._wallet_selector_target_index, len(lv.children) - 1))
            lv.index = idx
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to reset wallet selector index", exception=e)

    def _load_wallet_statuses(self) -> None:
        """Load wallet statuses without blocking UI (threaded)."""
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        for idx, acc in enumerate(self.accounts):
            try:
                addr_short = acc.address[:10] + "…" + acc.address[-8:]
                spin = spinner[idx % len(spinner)]
                self.app._ui(
                    self._update_wallet_selector_row,
                    idx,
                    f"{spin} [b]{acc.name}[/b] [dim]Loading... ꜩ[/dim] [dim]STK ...[/dim]\n[dim]{addr_short}[/dim]",
                )

                # Fetch delegation + staking from a single on-chain snapshot (prefer RPC),
                # forced refresh to reduce stale reads after external wallet actions.
                state = get_wallet_chain_state(
                    self.rpc,
                    acc.address,
                    force_refresh=True,
                    prefer_rpc=True,
                )
                delegate_addr = state.get("delegate")
                staked_mutez = int(state.get("staked_mutez") or 0)
                unstaked_mutez = int(state.get("unstaked_mutez") or 0)
                staking_active = bool(state.get("staking_active"))
                balance_mutez = int(state.get("balance_mutez") or 0)
                if balance_mutez <= 0:
                    balance_mutez = get_balance_mutez(self.rpc, acc.address)

                # If stake recently existed, don't immediately downgrade to 0 (TzKT can lag right after a baker change).
                prev = self._wallet_info_cache.get(acc.address) or {}
                now_ts = time.time()
                prev_staked = int(prev.get("staked_mutez") or 0)
                prev_seen = prev.get("staked_seen_at")
                if (
                    prev_staked > 0
                    and staked_mutez == 0
                    and unstaked_mutez <= 0
                    and isinstance(prev_seen, (int, float))
                ):
                    if now_ts - float(prev_seen) < self._stake_status_grace_seconds:
                        staked_mutez = prev_staked
                        staking_active = True

                # Cache the info for instant access when selecting
                self._wallet_info_cache[acc.address] = {
                    "delegate_addr": delegate_addr,
                    "staked_mutez": staked_mutez,
                    "unstaked_mutez": unstaked_mutez,
                    "staking_active": staking_active,
                    "balance_mutez": balance_mutez,
                    "fetched_at": time.time(),
                    "staked_seen_at": time.time() if staked_mutez > 0 else prev.get("staked_seen_at"),
                }

                label_text = self._format_stake_selector_row(
                    account_name=acc.name,
                    address=acc.address,
                    balance_mutez=balance_mutez,
                    staked_mutez=staked_mutez,
                    delegate_addr=delegate_addr,
                )

            except _FLOW_TASK_EXCEPTIONS as e:
                log_error(f"Failed to fetch status for {acc.name}", exception=e)
                label_text = f"[b]{acc.name}[/b] [red]⚠️ Error loading status[/red]\n[dim]{addr_short}[/dim]"

            # Update the list item with loaded data
            self.app._ui(self._update_wallet_selector_row, idx, label_text)

    def _update_wallet_selector_row(self, idx: int, label_text: str) -> None:
        """Update a wallet row in the selector (UI thread)."""
        try:
            lv = self.query_one("#wallet_selector", ListView)
            list_items = list(lv.children)
            if idx < len(list_items):
                item = list_items[idx]
                label = item.query_one(Label)
                label.update(label_text)
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update wallet selector row", exception=e)

    async def _push_hidden_screen(self, screen) -> Any:
        """Push a modal screen while hiding the StakeScreen root to avoid flashes."""
        root = None
        try:
            root = self.query_one("#stake_root", Vertical)
            root.add_class("hidden")
        except _UI_QUERY_EXCEPTIONS:
            root = None
        try:
            return await self.app.push_screen_wait(screen)  # type: ignore[attr-defined]
        finally:
            if root is not None:
                try:
                    root.remove_class("hidden")
                except _UI_QUERY_EXCEPTIONS as e:
                    log_debug("Failed to restore stake root visibility", exception=str(e))

    def on_key(self, event) -> None:
        # Only handle keys when this screen is the active/top screen.
        # Prevents accidental key handling while other modals (passphrase/confirm) are open.
        if self.app.screen is not self:
            return

        key = getattr(event, "key", None)

        # 🚫 If focus is on an Input widget, let it handle keys naturally
        # Only intercept Escape for cancel functionality
        if _handle_input_escape_focus_cancel(
            self,
            event,
            key,
            context="stake screen",
            fallbacks=(("#select_wallet_btn", Button),),
        ):
            # For all other keys, let Input handle them naturally (NO event.stop())
            return

        # Valid navigation from here

        if key == "escape":
            self.cancel_pressed()
            return
        # Avoid accidental reset to wallet selector from buffered backspace events
        # after nested modal transitions (passphrase/confirm screens).
        if key == "ctrl+b" and self.selected_account:
            self._go_back_to_selector()
            event.stop()
            return

    @on(Button.Pressed, "#select_wallet_btn")
    def select_wallet_pressed(self) -> None:
        """Handle Select button - confirm wallet selection."""
        try:
            lv = self.query_one("#wallet_selector", ListView)
            if lv.index is not None and lv.index >= 0:
                account = self.accounts[lv.index]
                cached_info = self._wallet_info_cache.get(account.address) or {}
                balance_mutez = cached_info.get("balance_mutez")
                if balance_mutez is None:
                    balance_mutez = get_balance_mutez(self.rpc, account.address)
                has_outgoing = self._has_outgoing_activity(account.address)
                if balance_mutez <= 0 or not has_outgoing:
                    self.query_one("#fun_note", Static).update(
                        f"[red]{_STAKE_OUTGOING_REQUIRED_MSG}[/red]"
                    )
                    return
                self._select_wallet(lv.index)
        except _UI_QUERY_EXCEPTIONS + _FLOW_TASK_EXCEPTIONS as e:
            log_error("Failed to select wallet", exception=e)

    def _select_wallet(self, index: int) -> None:
        """Select wallet and update view with its info (uses cached data)."""
        if index < 0 or index >= len(self.accounts):
            return

        self.selected_account = self.accounts[index]
        self._blocked_new_wallet = False

        # Use cached wallet info for instant transition
        try:
            cached_info = self._wallet_info_cache.get(self.selected_account.address)

            if cached_info:
                # Use cached data - instant, no lag!
                self.balance_xtz = mutez_to_xtz(cached_info["balance_mutez"])
                self.delegate_addr = cached_info["delegate_addr"]
                self.staked_mutez = cached_info["staked_mutez"]
                self.unstaked_mutez = int(cached_info.get("unstaked_mutez") or 0)
                self.staking_active = bool(cached_info.get("staking_active")) or self.staked_mutez > 0
                self.is_delegated = bool(self.delegate_addr)
            else:
                # Fallback: fetch if cache miss (shouldn't happen normally)
                state = get_wallet_chain_state(
                    self.rpc,
                    self.selected_account.address,
                    force_refresh=True,
                    prefer_rpc=True,
                )
                balance_mutez = int(state.get("balance_mutez") or 0)
                self.balance_xtz = mutez_to_xtz(balance_mutez)
                self.delegate_addr = state.get("delegate")
                self.staked_mutez = int(state.get("staked_mutez") or 0)
                self.unstaked_mutez = int(state.get("unstaked_mutez") or 0)
                self.staking_active = bool(state.get("staking_active")) or self.staked_mutez > 0
                self.is_delegated = bool(self.delegate_addr)

            has_outgoing = self._has_outgoing_activity(self.selected_account.address)
            if self.balance_xtz <= 0 or not has_outgoing:
                self._blocked_new_wallet = True

            self._update_view()
        except _UI_QUERY_EXCEPTIONS + _FLOW_TASK_EXCEPTIONS as e:
            log_error("Failed to fetch wallet info", exception=e)
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update(f"[red]❌ Failed to fetch wallet info: {str(e)}[/red]")

    def _go_back_to_selector(self) -> None:
        """Go back to wallet selector screen."""
        log_warning(
            "StakeScreen switching back to wallet selector",
            selected_address=getattr(self.selected_account, "address", ""),
        )
        # Reset state
        self.selected_account = None
        self.balance_xtz = Decimal(0)
        self.delegate_addr = None
        self.staked_mutez = 0
        self.unstaked_mutez = 0
        self.staking_active = False
        self.is_delegated = False
        self._delegation_pending = False
        self._change_baker_mode = False

        # Note: Don't clear cache - keep it for fast re-selection
        # Cache will be refreshed when modal is reopened

        # Stop polling if active
        if self._polling_timer:
            self._polling_timer.stop()
            self._polling_timer = None

        # Stop spinner if active
        self.app._ui(self.app._stop_spinner)  # type: ignore[attr-defined]

        # Show wallet selector
        try:
            self.query_one("#wallet_selector", ListView).display = True
            self.query_one("#wallet_selector_label", Static).display = True
            self.query_one("#fun_note", Static).display = True
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to show wallet selector", exception=e)
        self._wallet_selector_target_index = 0
        self.set_timer(0.01, self._apply_wallet_selector_index)

        # Show Select button
        try:
            self.query_one("#select_wallet_btn", Button).display = True
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to show select button", exception=e)

        # Clear and hide info box
        try:
            info_widget = self.query_one("#info_box", Static)
            info_widget.update("")
            self.query_one("#info_row", Horizontal).display = False
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to clear info box", exception=e)

        # Hide and clear input container
        try:
            self.query_one("#input_container", Vertical).display = False
            self.query_one("#input_label", Static).update("")
            self.query_one("#input_field", Input).value = ""
            self.query_one("#input_field", Input).placeholder = ""
            self.query_one("#input_hint", Static).update("")
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to hide/clear input container", exception=e)

        # Clear status
        try:
            self.query_one("#status_msg", Static).update("")
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to clear status", exception=e)

        # Reset buttons - hide all action buttons
        def reset_buttons():
            try:
                # Show select wallet button
                select_btn = self.query_one("#select_wallet_btn", Button)
                select_btn.display = True

                # Hide all action buttons
                self.query_one("#back_btn", Button).display = False
                self.query_one("#delegate_btn", Button).display = False
                self.query_one("#stake_btn", Button).display = False
                self.query_one("#unstake_btn", Button).display = False
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to reset buttons", exception=e)

        self.call_later(reset_buttons)

    def _update_view(self) -> None:
        """Update the view with selected wallet info."""
        if not self.selected_account:
            return

        try:
            # Hide wallet selector and Select button
            try:
                self.query_one("#wallet_selector", ListView).display = False
                self.query_one("#wallet_selector_label", Static).display = False
                self.query_one("#fun_note", Static).display = False
                self.query_one("#select_wallet_btn", Button).add_class("hidden")
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to hide wallet selector", exception=e)

            # Show input container and prepare input field
            try:
                input_container = self.query_one("#input_container", Vertical)
                input_container.display = True

                # Pre-configure input field
                input_field = self.query_one("#input_field", Input)
                input_field.disabled = False
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to show input container", exception=e)

            # Update info box - ALWAYS show wallet details
            staked_xtz = format_xtz(mutez_to_xtz(self.staked_mutez))
            info_widget = self.query_one("#info_box", Static)

            # Build detailed wallet info
            addr = self.selected_account.address

            available_xtz = format_xtz(self.balance_xtz)
            unstaked_xtz = format_xtz(mutez_to_xtz(self.unstaked_mutez))

            delegate_label = "[dim]Not delegated[/dim]"
            if self.is_delegated and self.delegate_addr:
                delegate_short = self.delegate_addr[:10] + "…" + self.delegate_addr[-6:] if len(self.delegate_addr) > 16 else self.delegate_addr
                info = get_baker_info(self.rpc, self.delegate_addr)
                alias = info.get("alias") if info else None
                if alias:
                    delegate_label = f"{alias} [dim]({delegate_short})[/dim]"
                else:
                    delegate_label = delegate_short

            if self.balance_xtz <= 0:
                info_lines = [
                    f"[b]Wallet name:[/b] {self.selected_account.name}",
                    f"[dim]{addr}[/dim]",
                    "",
                    "[cyan]Balance[/cyan] 0 XTZ — time to grab some ꜩ and start the journey. 🥐",
                ]
            else:
                info_lines = [
                    f"[b]Wallet name:[/b] {self.selected_account.name}",
                    f"[dim]{addr}[/dim]",
                    "",
                    f"[cyan]Available[/cyan] {available_xtz} XTZ   [#8b5cf6]Staked[/#8b5cf6] {staked_xtz} XTZ",
                    f"[yellow]Delegated to[/yellow] {delegate_label}",
                ]
                if self.unstaked_mutez > 0:
                    info_lines.append(
                        f"[yellow]Pending unstake[/yellow] {unstaked_xtz} XTZ (must finalize before new stake)"
                    )

            info_text = "\n".join(info_lines)
            info_widget.update(info_text)
            self.query_one("#info_row", Horizontal).display = True

            # Update input container
            input_label = self.query_one("#input_label", Static)
            input_field = self.query_one("#input_field", Input)
            input_hint = self.query_one("#input_hint", Static)

            # Always clear the input field when updating view
            input_field.value = ""

            if self._delegation_pending:
                # Delegation pending - show waiting message
                input_label.update("[b]⏳ Waiting for confirmation...[/b]")
                input_field.placeholder = "Please wait..."
                input_field.disabled = True
                input_hint.update("[dim]Processing delegation (30-60 seconds)...[/dim]")
                self.query_one("#amount_comment", Static).update("")
            elif self._change_baker_mode:
                # Delegated, but user wants to switch baker
                input_label.update("[b]Enter New Baker Address:[/b]")
                input_field.placeholder = "tz1... or tz2... or tz3... or tz4..."
                input_field.disabled = False
                input_hint.update("[dim]Paste the new baker address (you can find bakers on tzkt.io).[/dim]")
                self.query_one("#amount_comment", Static).update("")
            elif not self.is_delegated:
                # Not delegated - show baker input
                input_label.update("[b]Enter Baker Address:[/b]")
                input_field.placeholder = "tz1... or tz2... or tz3... or tz4..."
                input_field.disabled = False
                input_hint.update("[dim]Must delegate before staking. Find bakers at baking-bad.org or tzkt.io[/dim]")
                self.query_one("#amount_comment", Static).update("")
            else:
                # Delegated - show amount input
                input_label.update("[b]Enter Amount (XTZ):[/b]")
                input_field.placeholder = "Example: 10.5"
                input_field.disabled = False
                if self.unstaked_mutez > 0 and self.staked_mutez <= 0:
                    input_hint.update(
                        "[yellow]⏳ Pending unstake detected after baker change. "
                        "You can stake again after finalization (~4 cycles).[/yellow]"
                    )
                else:
                    input_hint.update("")
                self.query_one("#amount_comment", Static).update("")

            # Update buttons - simplified show/hide approach
            def update_buttons():
                try:
                    # Hide select wallet button
                    select_btn = self.query_one("#select_wallet_btn", Button)
                    select_btn.display = False

                    # Show back button
                    back_btn = self.query_one("#back_btn", Button)
                    back_btn.display = True

                    # Get buttons
                    delegate_btn = self.query_one("#delegate_btn", Button)
                    stake_btn = self.query_one("#stake_btn", Button)
                    unstake_btn = self.query_one("#unstake_btn", Button)
                    change_baker_btn = self.query_one("#change_baker_btn", Button)

                    # Hide all action buttons first
                    delegate_btn.display = False
                    stake_btn.display = False
                    unstake_btn.display = False
                    change_baker_btn.display = False

                    # Show/configure buttons based on state
                    stake_locked_by_pending_unstake = self.unstaked_mutez > 0 and self.staked_mutez <= 0

                    if self._delegation_pending:
                        # Delegation pending
                        delegate_btn.display = True
                        delegate_btn.disabled = True
                        delegate_btn.label = "Delegating..."
                    elif self._change_baker_mode:
                        delegate_btn.display = True
                        # Only enable when the new baker address is valid.
                        try:
                            current_val = sanitize_input(self.query_one("#input_field", Input).value)
                            is_valid, _ = validate_baker_address(current_val)
                            delegate_btn.disabled = not is_valid
                        except _UI_QUERY_EXCEPTIONS:
                            delegate_btn.disabled = True
                        delegate_btn.label = "Change Baker"

                        # Hide the toggle button while in change-baker mode; the modal Back button
                        # is enough and avoids redundant controls.
                        change_baker_btn.display = False
                    elif not self.is_delegated:
                        # Not delegated - show Delegate button
                        delegate_btn.display = True
                        delegate_btn.disabled = False
                        delegate_btn.label = "Delegate"
                    elif self.staking_active:
                        # Already staking - show Stake and Unstake
                        change_baker_btn.display = True
                        change_baker_btn.disabled = False
                        change_baker_btn.label = "Change Baker"

                        stake_btn.display = True
                        stake_btn.disabled = stake_locked_by_pending_unstake
                        unstake_btn.display = True
                        unstake_btn.disabled = False
                    else:
                        # Delegated but not staking - show Stake button
                        change_baker_btn.display = True
                        change_baker_btn.disabled = False
                        change_baker_btn.label = "Change Baker"

                        stake_btn.display = True
                        stake_btn.disabled = stake_locked_by_pending_unstake

                except _UI_QUERY_EXCEPTIONS as e:
                    log_error("Failed to update buttons", exception=e)

            self.call_later(update_buttons)

            # Focus input field after everything is ready - simple and direct
            def focus_input():
                try:
                    input_field = self.query_one("#input_field", Input)
                    if not input_field.disabled:
                        input_field.focus()
                except _UI_QUERY_EXCEPTIONS as e:
                    log_error("Failed to focus input field", exception=e)

            # Use set_timer to ensure DOM is fully rendered
            self.set_timer(0.1, focus_input)

        except _UI_QUERY_EXCEPTIONS + _FLOW_TASK_EXCEPTIONS as e:
            log_error("Failed to update view", exception=e)
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update(f"[red]❌ Error updating view: {str(e)}[/red]")

    @on(Input.Changed, "#input_field")
    def on_input_changed(self, event: Input.Changed) -> None:
        """Validate input in real-time and provide visual feedback."""
        if not self.selected_account:
            return

        input_field = self.query_one("#input_field", Input)
        value = event.value
        expects_amount = self.is_delegated and not self._change_baker_mode and not self._delegation_pending
        if expects_amount:
            filtered = filter_amount_input(value)
            if filtered != value:
                input_field.value = filtered
            value = filtered
        elif not self._delegation_pending:
            filtered = filter_base58_input(value)
            if filtered != value:
                input_field.value = filtered
            value = filtered
        value = sanitize_input(value)
        input_hint = self.query_one("#input_hint", Static)

        # If input is empty, show default hint
        if not value:
            if self._change_baker_mode and not self._delegation_pending:
                input_hint.update("[dim]Paste the new baker address (tz1.../tz2.../tz3.../tz4...).[/dim]")
            elif not expects_amount and not self._delegation_pending:
                input_hint.update("[dim]Must delegate before staking. Find bakers at baking-bad.org or tzkt.io[/dim]")
            elif not self._delegation_pending:
                input_hint.update("")
                self.query_one("#amount_comment", Static).update("")
            return

        # Validate based on current state
        if not expects_amount and not self._delegation_pending:
            # Validating baker address
            is_valid, error_msg = validate_baker_address(value)
            if is_valid:
                input_hint.update("[#34d399]✓ Valid baker address[/#34d399]")
            else:
                # Only show error if the address looks complete (36 chars)
                if len(value) < 36:
                    input_hint.update(f"[dim]Address length: {len(value)}/36[/dim]")
                elif len(value) >= 36:
                    input_hint.update(f"[red]✗ {error_msg}[/red]")
                else:
                    input_hint.update("[dim]Enter complete baker address (36 characters)[/dim]")
            # In change-baker mode, only enable the action button when the address is valid
            if self._change_baker_mode:
                try:
                    btn = self.query_one("#delegate_btn", Button)
                    btn.disabled = not is_valid
                except _UI_QUERY_EXCEPTIONS as e:
                    log_debug("Failed to toggle delegate button state", exception=str(e))
        elif not self._delegation_pending:
            # Validating amount
            is_valid, error_msg, amount = validate_amount(value, min_value=Decimal("0"))

            if is_valid and amount:
                # Check against balance
                if amount <= self.balance_xtz:
                    input_hint.update("[#34d399]✓ Valid amount[/#34d399]")
                    comment_widget = self.query_one("#amount_comment", Static)
                    if self.balance_xtz > 0:
                        pct = amount / self.balance_xtz
                        if pct < Decimal("0.05"):
                            comment = "Not much, huh? 👀"
                        elif pct < Decimal("0.2"):
                            comment = "Playing it safe? We'll take it. 😉"
                        elif pct < Decimal("0.5"):
                            comment = "Solid bite. Respect. 🥖"
                        elif pct < Decimal("0.8"):
                            comment = "Wow! This is the way. Full conviction, baby. 🚀"
                        else:
                            comment = "All-in energy. Chad vibes only. 💪🔥"
                        comment_widget.update(f"[dim italic]{comment}[/dim italic]")
                    else:
                        comment_widget.update("")
                else:
                    input_hint.update(f"[red]✗ Exceeds available balance[/red]")
                    self.query_one("#amount_comment", Static).update("")
            else:
                # Only show error if it looks like they're done typing
                if '.' in value or len(value) > 2:
                    input_hint.update(f"[red]✗ {error_msg}[/red]")
                    self.query_one("#amount_comment", Static).update("")
                else:
                    staked_xtz = mutez_to_xtz(self.staked_mutez)
                    input_hint.update(f"[dim]💡 Available: {format_xtz(self.balance_xtz)} XTZ | Staked: {format_xtz(staked_xtz)} XTZ[/dim]")
                    self.query_one("#amount_comment", Static).update("")

    async def _refresh_selected_chain_state(self, *, force_refresh: bool, preserve_input: bool) -> bool:
        """Refresh selected wallet's delegation + staking state (best-effort)."""
        if not self.selected_account:
            return False

        addr = self.selected_account.address
        input_field = self.query_one("#input_field", Input)
        prev_value = input_field.value if preserve_input else ""

        prev = self._wallet_info_cache.get(addr) or {}
        prev_staked = int(prev.get("staked_mutez") or 0)
        prev_seen = prev.get("staked_seen_at")
        now_ts = time.time()

        try:
            state = await asyncio.to_thread(
                get_wallet_chain_state,
                self.rpc,
                addr,
                force_refresh=force_refresh,
                prefer_rpc=True,
            )
            delegate_addr = state.get("delegate")
            balance_mutez = int(state.get("balance_mutez") or 0)
            staked_mutez = int(state.get("staked_mutez") or 0)
            unstaked_mutez = int(state.get("unstaked_mutez") or 0)
            staking_active = bool(state.get("staking_active")) or (staked_mutez > 0)
        except _FLOW_TASK_EXCEPTIONS as e:
            log_debug("Failed to refresh wallet chain state", exception=str(e), address=addr)
            return False

        # If stake recently existed, don't immediately downgrade to 0 (TzKT can lag right after a baker change).
        if (
            prev_staked > 0
            and staked_mutez == 0
            and unstaked_mutez <= 0
            and isinstance(prev_seen, (int, float))
        ):
            if now_ts - float(prev_seen) < self._stake_status_grace_seconds:
                staked_mutez = prev_staked
                staking_active = True

        self.delegate_addr = delegate_addr
        self.is_delegated = bool(delegate_addr)
        self.staked_mutez = staked_mutez
        self.unstaked_mutez = unstaked_mutez
        self.staking_active = staking_active
        self.balance_xtz = mutez_to_xtz(balance_mutez)
        self._wallet_info_cache[addr] = {
            "delegate_addr": delegate_addr,
            "staked_mutez": staked_mutez,
            "unstaked_mutez": unstaked_mutez,
            "staking_active": staking_active,
            "balance_mutez": balance_mutez,
            "fetched_at": now_ts,
            "staked_seen_at": now_ts if staked_mutez > 0 else prev.get("staked_seen_at"),
        }
        self._update_view()
        if preserve_input:
            try:
                self.query_one("#input_field", Input).value = prev_value
            except _UI_QUERY_EXCEPTIONS as e:
                log_debug("Failed to restore input field after refresh", exception=str(e))
        return True

    async def _confirm_pending_ops_or_abort(
        self,
        *,
        cancel_message: str,
        detailed: bool = False,
    ) -> bool:
        if not self.selected_account:
            return True

        pending_info = check_pending_operations(self.rpc, self.selected_account.address)
        if not pending_info or not pending_info.get("has_pending"):
            return True

        pending_count = pending_info.get("pending_count", 0)
        if detailed:
            operations = pending_info.get("operations", [])
            ops_details: list[str] = []
            for op in operations[:3]:
                kind = op.get("kind", "unknown")
                counter = op.get("counter", "?")
                hash_short = op.get("hash", "unknown")[:16]
                ops_details.append(f"  • {kind} (counter: {counter}) - {hash_short}...")
            ops_text = "\n".join(ops_details)
            if len(operations) > 3:
                ops_text += f"\n  ... and {len(operations) - 3} more"
            warning_msg = (
                f"⚠️ [b]Pending Transactions Detected![/b]\n\n"
                f"Found {pending_count} pending operation(s) for this wallet:\n\n"
                f"{ops_text}\n\n"
                f"These transactions are waiting to be confirmed in the blockchain.\n"
                f"Attempting to proceed now may cause counter errors.\n\n"
                f"[b]Recommendations:[/b]\n"
                f"• Wait 1-2 minutes for pending operations to confirm\n"
                f"• Check your transaction history\n"
                f"• Try again after pending operations clear\n\n"
                f"Do you want to proceed anyway? (Not recommended)"
            )
        else:
            warning_msg = (
                f"⚠️ [b]Pending Transactions Detected![/b]\n\n"
                f"Found {pending_count} pending operation(s) for this wallet.\n"
                f"Proceeding may cause counter errors.\n\n"
                f"Wait 1-2 minutes for operations to confirm, then try again.\n\n"
                f"Proceed anyway? (Not recommended)"
            )

        proceed = await self.app.push_screen_wait(ConfirmScreen(warning_msg))
        if proceed:
            return True
        self._show_error(cancel_message)
        return False

    def _has_outgoing_activity(self, address: str) -> bool:
        try:
            return has_outgoing_tx(self.rpc, address)
        except _FLOW_PRECHECK_EXCEPTIONS:
            return True

    @work(exclusive=True)
    @on(Button.Pressed, "#change_baker_btn")
    async def change_baker_pressed(self) -> None:
        """Toggle change-baker mode (uses the same input field)."""
        if not self.selected_account:
            return
        if self._delegation_pending:
            return

        if self._change_baker_mode:
            self._change_baker_mode = False
            self._update_view()
            return

        # Refresh state first so we show the current baker even if it changed elsewhere.
        await self._refresh_selected_chain_state(force_refresh=True, preserve_input=False)
        self._change_baker_mode = True
        self._update_view()
        try:
            self.query_one("#delegate_btn", Button).disabled = True
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to disable delegate button in change-baker mode", exception=str(e))

    @work(exclusive=True)
    @on(Button.Pressed, "#delegate_btn")
    async def delegate_pressed(self) -> None:
        """Handle delegation action."""
        if not self.selected_account:
            self._show_error("⚠️ Select a wallet first.")
            return
        has_outgoing = self._has_outgoing_activity(self.selected_account.address)
        if self.balance_xtz <= 0 or not has_outgoing:
            self._show_error(_STAKE_OUTGOING_REQUIRED_MSG)
            return

        input_field = self.query_one("#input_field", Input)
        value = sanitize_input(input_field.value)

        if not value:
            self._show_error("⚠️ Please enter baker address")
            return

        # Validate baker address with full regex validation
        is_valid, error_msg = validate_baker_address(value)
        if not is_valid:
            self._show_error(f"⚠️ {error_msg}")
            return

        if not await self._confirm_pending_ops_or_abort(
            cancel_message="⏸️ Delegation cancelled - waiting for pending operations",
            detailed=True,
        ):
            return

        # Resolve baker alias for a friendlier confirmation summary.
        baker_name = "Unknown Baker"
        try:
            baker_info = get_baker_info(self.rpc, value, force_refresh=True) or {}
            baker_name = str(baker_info.get("alias") or baker_name)
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_debug("Failed to resolve baker alias", exception=str(e), baker=value)

        result = await self._confirm_delegate_flow(baker_address=value)
        if not result:
            return
        key, confirm = result

        fee_mutez = confirm.get("fee_mutez")
        gas_limit = confirm.get("gas_limit")
        storage_limit = confirm.get("storage_limit")

        if self._change_baker_mode:
            self._dismiss_stake_action(
                "change_baker",
                key=key,
                fee_mutez=fee_mutez,
                gas_limit=gas_limit,
                storage_limit=storage_limit,
                baker_address=value,
                baker_name=baker_name,
                current_baker=self.delegate_addr,
            )
            return

        self._dismiss_stake_action(
            "delegate",
            key=key,
            fee_mutez=fee_mutez,
            gas_limit=gas_limit,
            storage_limit=storage_limit,
            baker_address=value,
            baker_name=baker_name,
        )
        return
            
    @on(Button.Pressed, "#stake_btn")
    async def stake_pressed(self) -> None:
        """Handle staking action."""
        if self._stake_action_in_progress:
            log_info(
                "StakeScreen stake_pressed ignored (already in progress)",
                selected_address=getattr(self.selected_account, "address", ""),
            )
            return
        self._stake_action_in_progress = True
        log_info(
            "StakeScreen stake_pressed",
            selected_address=getattr(self.selected_account, "address", ""),
        )
        try:
            if not self.selected_account:
                self._show_error("⚠️ Select a wallet first.")
                return
            await self._refresh_selected_chain_state(force_refresh=True, preserve_input=True)
            if not self.is_delegated:
                self._show_error("⚠️ Wallet is not delegated. Delegate (or change baker) first.")
                return
            if self.unstaked_mutez > 0 and self.staked_mutez <= 0:
                pending_unstake = format_xtz(mutez_to_xtz(self.unstaked_mutez))
                self._show_error(
                    f"⚠️ Pending unstake detected ({pending_unstake} XTZ). "
                    "After changing baker, stake is temporarily locked until finalization (~4 cycles)."
                )
                return

            has_outgoing = self._has_outgoing_activity(self.selected_account.address)
            if self.balance_xtz <= 0 or not has_outgoing:
                self._show_error(_STAKE_OUTGOING_REQUIRED_MSG)
                return

            amount = self._read_validated_amount(
                empty_message="⚠️ Please enter amount",
                max_value=self.balance_xtz,
            )
            if amount is None:
                return

            if not await self._confirm_pending_ops_or_abort(
                cancel_message="⏸️ Staking cancelled - waiting for pending operations",
                detailed=False,
            ):
                return

            result = await self._confirm_stake_flow(
                amount=amount,
                cancel_message="⏸️ Staking cancelled",
                confirm_screen_factory=lambda key: ConfirmStakeScreen(
                    rpc=self.rpc,
                    key=key,
                    address=self.selected_account.address,
                    amount=amount,
                    show_back_button=True,
                ),
            )
            log_info(
                "StakeScreen confirm_stake_flow returned",
                has_result=bool(result),
                selected_address=getattr(self.selected_account, "address", ""),
            )
            if not result:
                return
            key, confirm = result
            # Re-check pending operations right before handing control back to app.
            # This closes a race where a just-injected op appears after the first check.
            if not await self._confirm_pending_ops_or_abort(
                cancel_message="⏸️ Staking paused - previous operation still pending",
                detailed=False,
            ):
                return
            log_info(
                "StakeScreen dismissing stake action payload",
                selected_address=getattr(self.selected_account, "address", ""),
                amount=str(amount),
                has_key=bool(key),
            )
            self._dismiss_stake_action(
                "stake",
                key=key,
                amount=amount,
                fee_mutez=confirm.get("fee_mutez"),
                gas_limit=confirm.get("gas_limit"),
                storage_limit=confirm.get("storage_limit"),
            )
            return

        except (ValueError, decimal.InvalidOperation):
            self._show_error("⚠️ Invalid amount format")
        except _FLOW_TASK_EXCEPTIONS as ex:
            log_error("Stake flow failed in modal", exception=ex)
            self._show_error(f"⚠️ Staking failed: {str(ex)}")
            return
        finally:
            self._stake_action_in_progress = False

    @work(exclusive=True)
    @on(Button.Pressed, "#unstake_btn")
    async def unstake_pressed(self) -> None:
        """Handle unstaking action."""
        if not self.selected_account:
            self._show_error("⚠️ Select a wallet first.")
            return
        await self._refresh_selected_chain_state(force_refresh=True, preserve_input=True)
        if self.staked_mutez <= 0 and not self.staking_active:
            self._show_error("⚠️ No staked balance detected. Refresh history and try again.")
            return

        # Validate amount against staked balance when available; if we can't reliably
        # determine it (TzKT lag / external baker change), let the chain validate.
        staked_xtz = mutez_to_xtz(self.staked_mutez)
        max_value = staked_xtz if self.staked_mutez > 0 else None
        amount = self._read_validated_amount(
            empty_message="⚠️ Please enter amount to unstake",
            max_value=max_value,
            over_limit_message=f"⚠️ Cannot unstake more than staked ({format_xtz(staked_xtz)} XTZ)",
        )
        if amount is None:
            return

        try:
            if not await self._confirm_pending_ops_or_abort(
                cancel_message="⏸️ Unstaking cancelled - waiting for pending operations",
                detailed=False,
            ):
                return

            result = await self._confirm_stake_flow(
                amount=amount,
                cancel_message="⏸️ Unstaking cancelled",
                confirm_screen_factory=lambda key: ConfirmUnstakeScreen(
                    rpc=self.rpc,
                    key=key,
                    address=self.selected_account.address,
                    amount=amount,
                    show_back_button=True,
                ),
            )
            if not result:
                return
            key, confirm = result
            # Re-check pending operations right before handing control back to app.
            if not await self._confirm_pending_ops_or_abort(
                cancel_message="⏸️ Unstaking paused - previous operation still pending",
                detailed=False,
            ):
                return

            confirmed = await self._push_hidden_screen(
                ConfirmScreen(
                    "Unstaking is reversible, but your future self might judge you.\n\n"
                    "Still want to proceed?",
                    title="Second Thoughts",
                    yes_label="Yes, unstake",
                    no_label="Keep staking",
                )
            )
            if not confirmed:
                self._show_error("😒 Unstake canceled. Chad mode stays on.")
                return

            self._dismiss_stake_action(
                "unstake",
                key=key,
                amount=amount,
                fee_mutez=confirm.get("fee_mutez"),
                gas_limit=confirm.get("gas_limit"),
                storage_limit=confirm.get("storage_limit"),
                second_confirmed=True,
            )
            return

        except (ValueError, decimal.InvalidOperation):
            self._show_error("⚠️ Invalid amount format")
        except _FLOW_TASK_EXCEPTIONS as ex:
            log_error("Unstake flow failed in modal", exception=ex)
            self._show_error(f"⚠️ Unstaking failed: {str(ex)}")
            return

    def _read_validated_amount(
        self,
        *,
        empty_message: str,
        max_value: Optional[Decimal],
        over_limit_message: str | None = None,
    ) -> Optional[Decimal]:
        value = sanitize_input(self.query_one("#input_field", Input).value)
        if not value:
            self._show_error(empty_message)
            return None
        is_valid, error_msg, amount = validate_amount(value, min_value=Decimal("0"), max_value=max_value)
        if is_valid:
            return amount
        if over_limit_message and error_msg and "must not exceed" in error_msg:
            self._show_error(over_limit_message)
        else:
            self._show_error(f"⚠️ {error_msg}")
        return None

    def _dismiss_stake_action(
        self,
        action: str,
        *,
        key: Any,
        amount: Optional[Decimal] = None,
        baker_address: Optional[str] = None,
        baker_name: Optional[str] = None,
        current_baker: Optional[str] = None,
        fee_mutez: Optional[int] = None,
        gas_limit: Optional[int] = None,
        storage_limit: Optional[int] = None,
        second_confirmed: bool = False,
    ) -> None:
        if not self.selected_account:
            log_warning("StakeScreen attempted to dismiss action without selected account", action=action)
            return
        payload: dict[str, Any] = {
            "action": action,
            "account": self.selected_account,
            "key": key,
            "fee_mutez": fee_mutez,
            "gas_limit": gas_limit,
            "storage_limit": storage_limit,
        }
        if amount is not None:
            payload["amount"] = amount
        if baker_address is not None:
            payload["baker_address"] = baker_address
        if baker_name is not None:
            payload["baker_name"] = baker_name
        if current_baker is not None:
            payload["current_baker"] = current_baker
        if second_confirmed:
            payload["second_confirmed"] = True
        log_info(
            "StakeScreen dismiss payload",
            action=action,
            selected_address=self.selected_account.address,
            has_key=bool(key),
            has_amount=("amount" in payload),
        )
        self.dismiss(payload)

    async def _confirm_stake_flow(
        self,
        *,
        amount: Decimal,
        confirm_screen_factory: Callable[[Any], ModalScreen[dict]],
        cancel_message: str,
    ) -> Optional[tuple[Any, dict]]:
        """Run passphrase+key check+confirm flow for stake/unstake actions."""
        if not self.selected_account:
            return None

        while True:
            key = await self._prompt_key_with_retry(
                cancel_message=cancel_message,
                prompt_factory=lambda error_note: StakePassphraseScreen(
                    "Enter Your Encryption Password",
                    password=True,
                    placeholder="Your wallet encryption password",
                    wallet_info=f"[b cyan]Wallet:[/b cyan] {self.selected_account.name}",
                    ok_label="Next →",
                    fun_note="Keep your keys safe. Never share this encryption password. 🔐🥖",
                    show_back_button=True,
                    error_note=error_note,
                ),
            )
            if key is None:
                log_info(
                    "StakeScreen confirm_stake_flow aborted at passphrase",
                    selected_address=getattr(self.selected_account, "address", ""),
                )
                return None

            confirm = await self._push_hidden_screen(confirm_screen_factory(key))
            if confirm and confirm.get(BACK_NAV_MARKER):
                log_info(
                    "StakeScreen confirm_stake_flow got __BACK__ from confirm screen",
                    selected_address=getattr(self.selected_account, "address", ""),
                )
                continue
            if not confirm or not confirm.get("ok"):
                log_info(
                    "StakeScreen confirm_stake_flow cancelled at confirm screen",
                    selected_address=getattr(self.selected_account, "address", ""),
                )
                self._show_error(cancel_message)
                return None
            log_info(
                "StakeScreen confirm_stake_flow confirmed",
                selected_address=getattr(self.selected_account, "address", ""),
            )
            return key, confirm

    async def _confirm_delegate_flow(self, *, baker_address: str) -> Optional[tuple[Any, dict]]:
        """Run passphrase + confirm flow for delegate/change-baker actions."""
        if not self.selected_account:
            return None

        while True:
            key = await self._prompt_key_with_retry(
                cancel_message="⏸️ Delegation cancelled",
                prompt_factory=lambda error_note: WarningPassphraseScreen(
                    "Enter Your Encryption Password",
                    password=True,
                    placeholder="Your wallet encryption password",
                    wallet_info=f"[b cyan]Wallet:[/b cyan] {self.selected_account.name}",
                    ok_label="Next →",
                    fun_note=(
                        "Switching bakers is still a delegation op (but spicier). 🔁🥐"
                        if self._change_baker_mode
                        else "Delegate like a boss! Your XTZ will thank you! 🎯"
                    ),
                    show_back_button=True,
                    error_note=error_note,
                ),
            )
            if key is None:
                return None

            if self._change_baker_mode:
                confirm = await self._push_hidden_screen(
                    ConfirmChangeBakerScreen(
                        rpc=self.rpc,
                        from_addr=self.selected_account.address,
                        current_baker_address=self.delegate_addr or "",
                        new_baker_address=baker_address,
                        show_back_button=True,
                    )
                )
            else:
                confirm = await self._push_hidden_screen(
                    ConfirmDelegateScreen(
                        self.rpc,
                        self.selected_account.address,
                        baker_address,
                        show_back_button=True,
                    )
                )

            if confirm and confirm.get(BACK_NAV_MARKER):
                continue
            if not confirm or not confirm.get("ok"):
                self._show_error("⏸️ Delegation cancelled")
                return None
            return key, confirm

    async def _prompt_key_with_retry(
        self,
        *,
        cancel_message: str,
        prompt_factory: Callable[[str], ModalScreen[str]],
    ) -> Optional[Any]:
        if not self.selected_account:
            return None
        error_note = ""
        while True:
            pw = await self._push_hidden_screen(prompt_factory(error_note))
            if pw == BACK_NAV_MARKER:
                log_info(
                    "StakeScreen passphrase returned __BACK__",
                    selected_address=getattr(self.selected_account, "address", ""),
                )
                return None
            if not pw:
                log_info(
                    "StakeScreen passphrase cancelled/empty",
                    selected_address=getattr(self.selected_account, "address", ""),
                )
                self._show_error(cancel_message)
                return None
            try:
                secret_key = decrypt_secret(self.selected_account.enc, pw)
                key = key_from_encoded_secret(secret_key)
            except InvalidTag:
                error_note = "❌ Wrong encryption password. Try again."
                continue
            except (ValueError, TypeError) as decrypt_err:
                raise RuntimeError("Malformed encrypted wallet data") from decrypt_err
            if not self._selected_key_matches(key):
                return None
            return key

    async def _prompt_operation_secret(
        self,
        *,
        ok_label: str,
        fun_note: str,
        cancel_status: str,
    ) -> Optional[str]:
        """Prompt passphrase with retry and decrypt current wallet secret."""
        if not self.selected_account:
            return None
        error_note = ""
        while True:
            passphrase = await self.app.push_screen_wait(  # type: ignore[attr-defined]
                SendPassphraseScreen(
                    "Enter Your Encryption Password",
                    password=True,
                    placeholder="Your wallet encryption password",
                    wallet_info=f"[b]{self.selected_account.name}[/b]",
                    ok_label=ok_label,
                    fun_note=fun_note,
                    error_note=error_note,
                )
            )
            if not passphrase:
                self.query_one("#status_msg", Static).update(cancel_status)
                return None
            try:
                return decrypt_secret(self.selected_account.enc, passphrase)
            except InvalidTag:
                error_note = "❌ Wrong encryption password. Try again."
                continue
            except (ValueError, TypeError) as decrypt_err:
                raise RuntimeError("Malformed encrypted wallet data") from decrypt_err

    def _prepare_rpc_for_operation(self) -> bool:
        _, can_send, _ = self.app._ensure_working_rpc()  # type: ignore[attr-defined]
        self.rpc = self.app.rpc  # type: ignore[attr-defined]
        if can_send:
            return True
        self.query_one("#status_msg", Static).update("[red]❌ No RPC available to inject operations[/red]")
        return False

    def _show_operation_failure(self, *, title: str, app_status: str, exception: BaseException) -> None:
        error_msg = str(exception)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        try:
            self.query_one("#status_msg", Static).update(
                f"[red]❌ {title} failed[/red]\n"
                f"[dim]{error_msg}[/dim]\n"
                f"[yellow]Check logs/wallet.log for details[/yellow]"
            )
        except _UI_CALLBACK_EXCEPTIONS as e:
            log_debug("Failed to update operation error message in modal", exception=str(e), title=title)
        try:
            self.app._ui(self.app._stop_breathing_effect)  # type: ignore[attr-defined]
            self.app._set_status(f"[red]❌ {app_status} failed - check logs[/red]")  # type: ignore[attr-defined]
        except _UI_CALLBACK_EXCEPTIONS as e:
            log_debug("Failed to update operation error status in app", exception=str(e), title=title)

    def _selected_key_matches(self, key: Any, *, detailed: bool = False) -> bool:
        if not self.selected_account:
            return False
        try:
            key_pkh = key.public_key_hash()
        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Failed to read key public hash", exception=e)
            self.query_one("#status_msg", Static).update("[red]❌ Invalid key data[/red]")
            return False
        if key_pkh == self.selected_account.address:
            return True
        msg = (
            "[red]❌ KEY MISMATCH! Wallet address doesn't match decrypted key[/red]"
            if detailed
            else "[red]❌ KEY MISMATCH![/red]"
        )
        self.query_one("#status_msg", Static).update(msg)
        return False

    def _finalize_operation_success(
        self,
        *,
        modal_success: str,
        op_hash: str,
        app_status: str,
    ) -> None:
        self.query_one("#status_msg", Static).update(
            f"[#34d399]✅ {modal_success}[/#34d399]\n"
            f"[dim]Operation: {op_hash}[/dim]"
        )
        self.app._ui(self.app._stop_breathing_effect)  # type: ignore[attr-defined]
        self.app._set_status(f"[#34d399]✅ {app_status}[/#34d399]")  # type: ignore[attr-defined]
        self.app.call_later(self.app._refresh_account)  # type: ignore[attr-defined]
        self.call_later(lambda: self.dismiss(None))

    async def _await_tx_flow_budget(self, flow_start: float) -> None:
        remaining = self.app._tx_flow_remaining_or_default(flow_start)  # type: ignore[attr-defined]
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def _perform_delegation(self, baker_address: str, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> None:
        """Delegate to baker."""
        if not self.selected_account:
            return

        secret_key = await self._prompt_operation_secret(
            ok_label="✅ Delegate!",
            fun_note="Delegate like a boss! Your XTZ will thank you! 🎯",
            cancel_status="[yellow]⏸️ Delegation cancelled[/yellow]",
        )
        if not secret_key:
            return

        try:
            if not self._prepare_rpc_for_operation():
                return
            key = key_from_encoded_secret(secret_key)
            if not self._selected_key_matches(key):
                return

            status_widget = self.query_one("#status_msg", Static)
            status_widget.update("[yellow]⏳ Delegating... This may take a moment...[/yellow]")
            flow_start = time.time()
            self.app._ui(
                self.app._start_breathing_effect,
                "⏳ Delegating...",
                bright_class="status-warning",
                dim_class="status-warning-dim",
            )  # type: ignore[attr-defined]

            # Perform delegation with fee parameters (with RPC fallback on stale-branch errors)
            _, op_hash = self.app._with_rpc_fallback(  # type: ignore[attr-defined]
                action="delegate",
                rpc=self.rpc,
                fn=lambda r: delegate_to_baker(
                    r,
                    key,
                    baker_address,
                    fee_mutez=fee_mutez,
                    gas_limit=gas_limit,
                    storage_limit=storage_limit,
                ),
            )
            self.rpc = self.app.rpc  # type: ignore[attr-defined]

            await self._await_tx_flow_budget(flow_start)

            status_widget.update(f"[#34d399]✅ Delegation sent![/#34d399]\n[dim]Op: {op_hash} Waiting for confirmation...[/dim]")
            self.app._ui(self.app._stop_breathing_effect)  # type: ignore[attr-defined]

            # Start spinner with baker-themed messages in main app
            baker_msg = get_baker_message()
            self.app._ui(
                self.app._set_status_styled,
                baker_msg,
                style="warning",
                duration=0.0,
                force=True,
            )  # type: ignore[attr-defined]
            self.app._ui(self.app._start_spinner, baker_msg)  # type: ignore[attr-defined]

            # Set delegation pending state
            self._delegation_pending = True
            self.delegate_addr = baker_address  # Store baker address
            self._update_view()

            # Start polling for delegation confirmation
            self._start_delegation_polling()

        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Delegation failed", exception=e)
            # Stop spinner on error
            self.app._ui(self.app._stop_spinner)  # type: ignore[attr-defined]
            self.app._ui(self.app._stop_breathing_effect)  # type: ignore[attr-defined]
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update(f"[red]❌ Delegation failed: {str(e)}[/red]")
            # Also show error in main app
            self.app._set_status(f"[red]❌ Delegation failed: {str(e)}[/red]")  # type: ignore[attr-defined]

    async def _perform_staking(self, amount: Decimal, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> None:
        """Stake XTZ."""
        try:
            if not self.selected_account:
                return

            source_address = self.selected_account.address

            secret_key = await self._prompt_operation_secret(
                ok_label="💎 Stake!",
                fun_note="Time to become a CHAD! Lock in that XTZ! 💪🔥",
                cancel_status="[yellow]⏸️ Staking cancelled - encryption password not provided[/yellow]",
            )
            if not secret_key:
                return

            if not self._prepare_rpc_for_operation():
                return
            key = key_from_encoded_secret(secret_key)
            if not self._selected_key_matches(key, detailed=True):
                return

            status_widget = self.query_one("#status_msg", Static)
            status_widget.update("[yellow]⏳ Staking... This may take a moment...[/yellow]")
            flow_start = time.time()
            self.app._ui(
                self.app._start_breathing_effect,
                "⏳ Staking...",
                bright_class="status-stake",
                dim_class="status-stake-dim",
            )  # type: ignore[attr-defined]

            # Perform staking (with RPC fallback on stale-branch errors)
            _, op_hash = self.app._with_rpc_fallback(  # type: ignore[attr-defined]
                action="stake",
                rpc=self.rpc,
                source_address=source_address,
                require_stake_support=True,
                fn=lambda r: stake_xtz(
                    r,
                    key,
                    amount,
                    fee_mutez=fee_mutez,
                    gas_limit=gas_limit,
                    storage_limit=storage_limit,
                ),
            )
            self.rpc = self.app.rpc  # type: ignore[attr-defined]

            await self._await_tx_flow_budget(flow_start)

            self._finalize_operation_success(
                modal_success="STAKE SUCCESSFUL! You're a true CHAD now! 🔥💪",
                op_hash=op_hash,
                app_status=f"Staked {format_xtz(amount)} XTZ successfully!",
            )

        except _FLOW_TASK_EXCEPTIONS as e:
            self._show_operation_failure(title="Staking", app_status="Staking", exception=e)

    async def _perform_unstaking(self, amount: Decimal, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> None:
        """Unstake XTZ."""
        if not self.selected_account:
            return

        secret_key = await self._prompt_operation_secret(
            ok_label="💸 Unstake!",
            fun_note="Time to unlock that XTZ! Freedom awaits! 🔓✨",
            cancel_status="[yellow]⏸️ Unstaking cancelled[/yellow]",
        )
        if not secret_key:
            return

        try:
            if not self._prepare_rpc_for_operation():
                return

            key = key_from_encoded_secret(secret_key)
            if not self._selected_key_matches(key):
                return

            status_widget = self.query_one("#status_msg", Static)
            status_widget.update("[yellow]⏳ Unstaking... This may take a moment...[/yellow]")
            flow_start = time.time()
            self.app._ui(
                self.app._start_breathing_effect,
                "⏳ Unstaking...",
                bright_class="status-unstake",
                dim_class="status-unstake-dim",
            )  # type: ignore[attr-defined]

            # Perform unstaking with fee parameters (with RPC fallback on stale-branch errors)
            _, op_hash = self.app._with_rpc_fallback(  # type: ignore[attr-defined]
                action="unstake",
                rpc=self.rpc,
                source_address=self.selected_account.address,
                require_stake_support=True,
                fn=lambda r: unstake_xtz(
                    r,
                    key,
                    amount,
                    fee_mutez=fee_mutez,
                    gas_limit=gas_limit,
                    storage_limit=storage_limit,
                ),
            )
            self.rpc = self.app.rpc  # type: ignore[attr-defined]

            await self._await_tx_flow_budget(flow_start)

            self._finalize_operation_success(
                modal_success="UNSTAKE SUCCESSFUL! XTZ unlocked! 💰",
                op_hash=op_hash,
                app_status=f"Unstaked {format_xtz(amount)} XTZ successfully!",
            )

        except _FLOW_TASK_EXCEPTIONS as e:
            log_error(f"Unstaking failed - Full error details", exception=e)
            self._show_operation_failure(title="Unstaking", app_status="Unstaking", exception=e)

    def _show_error(self, message: str) -> None:
        """Show error message."""
        status_widget = self.query_one("#status_msg", Static)
        status_widget.update(f"[red]{message}[/red]")

    def _start_delegation_polling(self) -> None:
        """Start polling to check if delegation is confirmed."""
        def check_delegation():
            try:
                if not self.selected_account:
                    return

                # Rotate baker message every poll
                baker_msg = get_baker_message()
                self.app._ui(self.app._start_spinner, baker_msg)  # type: ignore[attr-defined]

                # Check if delegation is confirmed
                current_delegate = get_delegation_info(self.rpc, self.selected_account.address)

                if current_delegate == self.delegate_addr:
                    # Delegation confirmed!
                    self._delegation_pending = False
                    self.is_delegated = True

                    # Stop polling
                    if self._polling_timer:
                        self._polling_timer.stop()
                        self._polling_timer = None

                    # Stop spinner
                    self.app._ui(self.app._stop_spinner)  # type: ignore[attr-defined]

                    # Update status
                    status_widget = self.query_one("#status_msg", Static)
                    status_widget.update(
                        f"[#34d399]🎉 DELEGATION CONFIRMED! Staking unlocked! 💪[/#34d399]\n"
                        f"[dim]You can now stake your XTZ![/dim]"
                    )

                    # Show success in main app
                    self.app._status_lock_until_refresh = True  # type: ignore[attr-defined]
                    self.app._set_status("[#34d399]✅ Delegation confirmed! You can now stake your XTZ! 💪[/#34d399]", force=True)  # type: ignore[attr-defined]

                    # Update fun message
                    self._fun_message = get_modal_message("delegation_confirmed")

                    # Update view to enable Stake button
                    self._update_view()

                    # Trigger main app refresh
                    self.app.call_later(self.app._refresh_account)  # type: ignore[attr-defined]

            except _UI_QUERY_EXCEPTIONS + _FLOW_TASK_EXCEPTIONS as e:
                log_error("Failed to check delegation status", exception=e)

        # Poll every 5 seconds for up to 2 minutes
        self._polling_timer = self.set_interval(5.0, check_delegation, repeat=24)

    @on(Button.Pressed, "#back_btn")
    def back_pressed(self) -> None:
        """Handle Back button - return to wallet selector."""
        self._go_back_to_selector()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        # Stop polling if active
        if self._polling_timer:
            self._polling_timer.stop()
            self._polling_timer = None
        # Stop spinner if delegation was pending
        if self._delegation_pending:
            self.app._ui(self.app._stop_spinner)  # type: ignore[attr-defined]
        self.app._set_status("👀 Chad mode canceled — dough back in the fridge.")  # type: ignore[attr-defined]
        self.dismiss(None)

    def on_unmount(self) -> None:
        """Cleanup timer, spinner, and cache on screen close."""
        if self._polling_timer:
            self._polling_timer.stop()
            self._polling_timer = None
        # Stop spinner if delegation was pending
        if self._delegation_pending:
            self.app._ui(self.app._stop_spinner)  # type: ignore[attr-defined]
        # Clear cache so next time modal opens it fetches fresh data
        self._wallet_info_cache.clear()


class TxDetailsScreen(ModalScreen[None]):
    CSS = """
    TxDetailsScreen {
        align: center middle;
    }

    TxDetailsScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy $primary;
        padding: 1 2;
    }

    TxDetailsScreen #tx_details {
        margin-bottom: 0;
    }

    TxDetailsScreen #buttons {
        align: center middle;
        margin-top: 0;
    }

    TxDetailsScreen #buttons > Button {
        margin: 0 1;
    }
    """

    def __init__(self, rpc: str, tx: dict, wallet_address: str = ""):
        super().__init__()
        self.rpc = rpc
        self.tx = tx
        self.wallet_address = wallet_address
        self.tzkt_link = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            ts = (self.tx.get("ts") or "").replace("T", " ").replace("Z", "")
            direction = self.tx.get("direction") or "?"
            amt: Decimal = self.tx.get("amount_xtz") or Decimal(0)
            cp = self.tx.get("counterparty") or "?"
            h = self.tx.get("hash") or ""
            baker = self.tx.get("baker") or ""

            # Determine From and To based on direction
            if direction == "IN":
                from_addr = cp
                to_addr = self.wallet_address or "Your Wallet"
                amt_label = f"[#34d399]+{format_xtz(amt)} XTZ[/#34d399]"
            elif direction == "OUT":
                from_addr = self.wallet_address or "Your Wallet"
                to_addr = cp
                amt_label = f"[red]-{format_xtz(amt)} XTZ[/red]"
            else:
                from_addr = "?"
                to_addr = "?"
                amt_label = f"{format_xtz(amt)} XTZ"

            # Build TzKT link
            self.tzkt_link = f"{tzkt_ui_base_from_rpc(self.rpc)}/{h}" if h else ""

            # Shorten addresses for display
            from_short = from_addr[:10] + "..." + from_addr[-8:] if len(from_addr) > 20 else from_addr
            to_short = to_addr[:10] + "..." + to_addr[-8:] if len(to_addr) > 20 else to_addr
            lines = [
                f"Time:    {ts}",
                f"Amount:  {amt_label}",
                f"From:    {from_short}",
                f"To:      {to_short}",
                f"Hash:    {h}",
            ]

            if baker:
                baker_short = baker[:10] + "..." + baker[-8:] if len(baker) > 20 else baker
                lines.append(f"Baker:   {baker_short}")

            yield Static("\n".join(lines), id="tx_details", markup=True)

            with Horizontal(id="buttons"):
                if self.tzkt_link:
                    yield Button("Check in TzKT Explorer", id="tzkt", variant="primary")
                yield Button("Close", id="close")

    @on(Button.Pressed, "#tzkt")
    def tzkt_pressed(self) -> None:
        """Open transaction in TzKT explorer."""
        if self.tzkt_link:
            webbrowser.open(self.tzkt_link)

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.dismiss(None)
            event.stop()


class ConfirmSendScreen(ModalScreen[dict]):
    """
    Confirmación con:
      - selector simple de fee (Economy / Normal / Priority)
      - Advanced opcional (overrides TX: fee/gas/storage)

    Devuelve dict:
      {
        "ok": bool,
        "fee_mutez": Optional[int],
        "gas_limit": Optional[int],
        "storage_limit": Optional[int],
      }
    """
    CSS = """
    ConfirmSendScreen {
        align: center middle;
    }

    ConfirmSendScreen > Vertical {
        width: 72;
        min-width: 72;
        max-width: 72;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #10b981;
        padding: 1 2;
    }

    ConfirmSendScreen #summary {
        margin-bottom: 0;
    }

    ConfirmSendScreen #confirm_comment {
        margin-top: 1;
        margin-bottom: 0;
        color: #fbbf24;
        text-style: italic;
        min-height: 2;
    }

    ConfirmSendScreen #fee_title {
        margin-bottom: 0;
        color: $accent;
    }

    ConfirmSendScreen #fee_list {
        height: 4;
        margin-bottom: 1;
    }

    ConfirmSendScreen #fee_list > ListItem {
        padding: 0 0 0 2;
    }

    ConfirmSendScreen #suggested_limits {
        margin-top: 1;
        margin-bottom: 1;
        color: $text-muted;
        min-height: 2;
    }

    ConfirmSendScreen #advanced {
        margin-top: 0;
        margin-bottom: 1;
    }

    ConfirmSendScreen #advanced_joke {
        margin-top: 1;
        margin-bottom: 0;
        color: #f97316;
        text-style: bold italic;
        min-height: 2;
    }

    ConfirmSendScreen Input {
        border: solid #4b5563;
        background: transparent;
        padding: 0 1;
    }

    ConfirmSendScreen Input:focus {
        border: solid #10b981;
    }

    ConfirmSendScreen Horizontal {
        align: center middle;
        margin-top: 1;
    }

    ConfirmSendScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, rpc: str, key, from_addr: str, to_addr: str, amount: Decimal, show_back_button: bool = False):
        super().__init__()
        self.rpc = rpc
        self.key = key
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount
        self.show_back_button = show_back_button

        self._advanced = False
        self._estimate: Optional[dict] = None
        self._fee_choice: str = "normal"   # economy|normal|priority
        self._fee_labels: list[Label] = []  # label refs inside fee_list items

        # Estimation pulse (visual feedback)
        self._est_timer = None
        self._est_i: int = 0
        self._estimating: bool = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="summary", markup=True)

            yield Static("[b]Fee[/b] (↑/↓ to choose)", id="fee_title", markup=True)
            yield ListView(id="fee_list")

            # Suggested limits (shown only when advanced mode is active)
            yield Static("", id="suggested_limits", markup=True)

            # Advanced container (hidden by default)
            with Vertical(id="advanced"):
                yield Static("[b]Advanced (TX overrides)[/b]\nLeave blank to use suggested/autofill.", markup=True)
                with Horizontal():
                    yield Static("Fee (XTZ):", id="lbl_fee")
                    yield Input(placeholder="e.g. 0.005", id="fee_xtz")
                with Horizontal():
                    yield Static("Gas limit:", id="lbl_gas")
                    yield Input(placeholder="e.g. 20000", id="gas_limit")
                with Horizontal():
                    yield Static("Storage limit:", id="lbl_storage")
                    yield Input(placeholder="e.g. 0", id="storage_limit")

            # Advanced mode joke (near buttons)
            yield Static("", id="advanced_joke", markup=True)

            # Sassy confirmation comment appears here, right before buttons
            yield Static("", id="confirm_comment", markup=True)

            with Horizontal():
                if self.show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button("💸 SEND", id="send", variant="primary")
                yield Button("Advanced", id="toggle")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        adv = self.query_one("#advanced", Vertical)
        adv.styles.display = "none"

        # Hide suggested limits by default
        suggested_widget = self.query_one("#suggested_limits", Static)
        suggested_widget.styles.display = "none"

        # Hide advanced joke by default
        joke_widget = self.query_one("#advanced_joke", Static)
        joke_widget.styles.display = "none"

        # Show confirmation comment based on amount
        comment_widget = self.query_one("#confirm_comment", Static)
        confirmation_msg = get_confirmation_comment(self.amount)
        comment_widget.update(f"[dim italic]{confirmation_msg}[/dim italic]")

        self._start_est_pulse()
        self._render_summary(estimating=True)
        self._init_fee_list()
        self._update_fee_list(estimating=True)

        send_btn = self.query_one("#send", Button)
        send_btn.disabled = True
        send_btn.focus()
        self._estimate_worker()
        self.set_timer(Config.ESTIMATE_FALLBACK_SECONDS, self._apply_estimate_fallback)

    @on(Input.Changed, "#fee_xtz")
    def fee_changed(self, event: Input.Changed) -> None:
        inp = self.query_one("#fee_xtz", Input)
        filtered = filter_amount_input(event.value)
        if filtered != event.value:
            inp.value = filtered

    @on(Input.Changed, "#gas_limit")
    def gas_changed(self, event: Input.Changed) -> None:
        inp = self.query_one("#gas_limit", Input)
        filtered = filter_digits_input(event.value)
        if filtered != event.value:
            inp.value = filtered

    @on(Input.Changed, "#storage_limit")
    def storage_changed(self, event: Input.Changed) -> None:
        inp = self.query_one("#storage_limit", Input)
        filtered = filter_digits_input(event.value)
        if filtered != event.value:
            inp.value = filtered

    def on_unmount(self) -> None:
        self._stop_est_pulse()


    # -------------------------
    # Estimation pulse (ConfirmSendScreen)
    # -------------------------
    def _start_est_pulse(self) -> None:
        _start_estimation_pulse(self)

    def _stop_est_pulse(self) -> None:
        _stop_estimation_pulse(self)

    def _tick_est_pulse(self) -> None:
        _tick_estimation_pulse(self)

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)
        # Gas/fee estimation uses estimate_send_xtz and feeds the fee list; keep in sync.

        if estimating:
            lines = [
                "[b]Confirm transaction[/b]",
                "",
                f"[b cyan]Network:[/b cyan]   {net}",
                "",
                f"[b cyan]From:[/b cyan]      {self.from_addr}",
                f"[b cyan]To:[/b cyan]        {self.to_addr}",
                "",
                f"[b cyan]Amount:[/b cyan]    {format_xtz(self.amount)} XTZ",
            ]
        elif err:
            lines = [
                "[b]Confirm transaction[/b]",
                "",
                f"[b cyan]Network:[/b cyan]   {net}",
                "",
                f"[b cyan]From:[/b cyan]      {self.from_addr}",
                f"[b cyan]To:[/b cyan]        {self.to_addr}",
                "",
                f"[b cyan]Amount:[/b cyan]    {format_xtz(self.amount)} XTZ",
                "",
                f"[red]Fee estimate failed:[/red] {err}",
                "",
                "You can still SEND (autofill) or use Advanced overrides.",
            ]
        else:
            # Simple summary (suggested limits moved to separate widget)
            lines = [
                "[b]Confirm transaction[/b]",
                "",
                f"[b cyan]Network:[/b cyan]   {net}",
                "",
                f"[b cyan]From:[/b cyan]      {self.from_addr}",
                f"[b cyan]To:[/b cyan]        {self.to_addr}",
                "",
                f"[b cyan]Amount:[/b cyan]    {format_xtz(self.amount)} XTZ",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))


    def _init_fee_list(self) -> None:
        _init_fee_rows(self)

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        """Update fee rows text + checkmark without rebuilding ListView."""
        # Ensure list initialized
        if not self._fee_labels:
            self._init_fee_list()

        _update_fee_title(self, estimating=estimating, debug_context="Failed to update fee title in send confirm")

        texts = _build_fee_rows_text(
            self._fee_choice,
            estimate=self._estimate,
            estimating=estimating,
            err=err,
            value_prefix="total fee: ",
            selected_mark="✓ ",
            unselected_mark="  ",
        )

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        _handle_fee_selection(self, event, render_requires_estimate=True)

    @work(exclusive=True, thread=True)
    def _estimate_worker(self) -> None:
        try:
            est = estimate_send_xtz(self.rpc, self.key, self.to_addr, self.amount)
            self._estimate = est

            # Prefills Advanced con “suggested tx fee/gas/storage”
            tx = est.get("tx") or {}
            fee_mutez = int(tx.get("fee_mutez") or 0)
            gas = int(tx.get("gas_limit") or 0)
            storage = int(tx.get("storage_limit") or 0)

            def _ui_apply():
                self._stop_est_pulse()
                # default “normal”
                self._fee_choice = "normal"
                self._update_fee_list(estimating=False)
                self._render_summary(estimating=False)
                self._enable_send_button()

                self.query_one("#fee_xtz", Input).value = str(mutez_to_xtz(fee_mutez))
                self.query_one("#gas_limit", Input).value = str(gas) if gas else ""
                self.query_one("#storage_limit", Input).value = str(storage) if storage else ""

            # ModalScreen doesn't provide call_from_thread in some Textual versions.
            # Use the App bridge instead.
            self.app.call_from_thread(_ui_apply)

        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Failed to estimate transaction fees", exception=e)
            # Report error safely on UI thread
            self.app.call_from_thread(self._stop_est_pulse)
            self.app.call_from_thread(self._update_fee_list, False, str(e))
            self.app.call_from_thread(self._render_summary, False, str(e))

    def _enable_send_button(self) -> None:
        _enable_action_button(self, "#send", "Failed to enable send button in send confirm")

    def _apply_estimate_fallback(self) -> None:
        if not self._estimating or self._estimate is not None:
            return
        # Fallback defaults for UI responsiveness; real autofill happens on inject.
        tx_fee_mutez = 1200
        tx_gas = 2000
        tx_storage = 0
        priority_fee = int((Decimal(tx_fee_mutez) * Decimal("1.5")).to_integral_value())
        self._estimate = {
            "reveal_needed": False,
            "tx": {"fee_mutez": tx_fee_mutez, "gas_limit": tx_gas, "storage_limit": tx_storage},
            "fee_options": {
                "economy": {
                    "label": "Economy (autofill)",
                    "tx_fee_mutez": None,
                    "total_fee_mutez": tx_fee_mutez,
                    "total_fee_xtz": mutez_to_xtz(tx_fee_mutez),
                },
                "normal": {
                    "label": "Normal (suggested)",
                    "tx_fee_mutez": tx_fee_mutez,
                    "total_fee_mutez": tx_fee_mutez,
                    "total_fee_xtz": mutez_to_xtz(tx_fee_mutez),
                },
                "priority": {
                    "label": "Priority (+50%)",
                    "tx_fee_mutez": priority_fee,
                    "total_fee_mutez": priority_fee,
                    "total_fee_xtz": mutez_to_xtz(priority_fee),
                },
            },
        }
        self._stop_est_pulse()
        self._fee_choice = "normal"
        self._update_fee_list(estimating=False)
        self._render_summary(estimating=False)
        self._enable_send_button()

    def _toggle_advanced(self) -> None:
        self._advanced = not self._advanced
        adv = self.query_one("#advanced", Vertical)
        suggested_widget = self.query_one("#suggested_limits", Static)
        confirm_widget = self.query_one("#confirm_comment", Static)

        # Keep advanced inputs hidden (future feature)
        adv.styles.display = "none"
        suggested_widget.styles.display = "none"
        confirm_widget.styles.display = "none" if self._advanced else "block"

        # Show/hide sarcastic joke when toggling advanced
        joke_widget = self.query_one("#advanced_joke", Static)
        if self._advanced:
            message = "Stop pretending you're an expert and pick one of the options above."
            joke_widget.update(f"[bold]{message}[/bold]")
            joke_widget.styles.display = "block"
        else:
            joke_widget.styles.display = "none"

        self.query_one("#toggle", Button).label = "Basic" if self._advanced else "Advanced"
        if self._advanced:
            self.query_one("#fee_xtz", Input).focus()
        else:
            _focus_with_fallback(
                self,
                primary=("#fee_list", ListView),
                fallbacks=(("#send", Button), ("#delegate", Button)),
                primary_error="Failed to focus fee list",
                fallback_error="Failed to focus fallback buttons in send confirm",
            )

    @on(Button.Pressed, "#toggle")
    def toggle_pressed(self) -> None:
        self._toggle_advanced()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(_tx_modal_result(ok=False))

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss(_tx_modal_result(ok=False, back=True))

    @on(Button.Pressed, "#send")
    def send_pressed(self) -> None:
        # Modo Advanced => overrides manuales
        if self._advanced:
            try:
                fee_mutez, gas, storage = _parse_tx_overrides(self)
            except (ValueError, TypeError) as e:
                log_error("Failed to parse override values", exception=e)
                self._render_summary(err=str(e))
                return
            self.dismiss(_tx_modal_result(ok=True, fee_mutez=fee_mutez, gas_limit=gas, storage_limit=storage))
            return

        # Modo normal => fee por selector, gas/storage = None (autofill)
        fee_mutez = _tx_fee_mutez_from_choice(self._estimate, self._fee_choice)
        self.dismiss(_tx_modal_result(ok=True, fee_mutez=fee_mutez))

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        _handle_tx_confirm_key(
            self,
            event,
            key,
            context="send confirm",
            action_handler=self.send_pressed,
        )


class ConfirmDelegateScreen(ModalScreen[dict]):
    """
    Confirmation modal for delegation with:
      - simple fee selector (Economy / Normal / Priority)
      - optional Advanced mode (overrides TX: fee/gas/storage)

    Returns dict:
      {
        "ok": bool,
        "fee_mutez": Optional[int],
        "gas_limit": Optional[int],
        "storage_limit": Optional[int],
      }
    """
    CSS = """
    ConfirmDelegateScreen {
        align: center middle;
    }

    ConfirmDelegateScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #eab308;
        padding: 1 2;
    }

    ConfirmDelegateScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ConfirmDelegateScreen #summary {
        margin-bottom: 0;
    }

    ConfirmDelegateScreen #fee_title {
        margin-bottom: 0;
        color: $accent;
    }

    ConfirmDelegateScreen #fee_list {
        height: 4;
        margin-bottom: 1;
    }

    ConfirmDelegateScreen #fee_list > ListItem {
        padding: 0 0 0 2;
    }

    ConfirmDelegateScreen #suggested_limits {
        margin-top: 1;
        margin-bottom: 1;
        color: $text-muted;
        min-height: 2;
    }

    ConfirmDelegateScreen #advanced {
        margin-top: 0;
        margin-bottom: 1;
    }

    ConfirmDelegateScreen #advanced_joke {
        margin-top: 1;
        margin-bottom: 0;
        color: #f97316;
        text-style: bold italic;
        min-height: 2;
    }

    ConfirmDelegateScreen Input {
        border: solid #4b5563;
        background: transparent;
        padding: 0 1;
    }

    ConfirmDelegateScreen Input:focus {
        border: solid #10b981;
    }

    ConfirmDelegateScreen Horizontal {
        align: center middle;
        margin-top: 1;
    }

    ConfirmDelegateScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, rpc: str, from_addr: str, baker_address: str, show_back_button: bool = False):
        super().__init__()
        self.rpc = rpc
        self.from_addr = from_addr
        self.baker_address = baker_address
        self.show_back_button = show_back_button
        self._baker_label = self._resolve_baker_label()

        self._advanced = False
        self._estimate: Optional[dict] = None
        self._fee_choice: str = "normal"   # economy|normal|priority
        self._fee_labels: list[Label] = []  # label refs inside fee_list items

        # Estimation pulse (visual feedback)
        self._est_timer = None
        self._est_i: int = 0
        self._estimating: bool = False

    def _resolve_baker_label(self) -> str:
        if not self.baker_address:
            return "—"
        info = get_baker_info(self.rpc, self.baker_address)
        alias = info.get("alias") if info else None
        if alias:
            return f"{alias} [dim]({self.baker_address})[/dim]"
        return self.baker_address

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Confirm Delegation[/b]", id="title", markup=True)
            yield Static("", id="summary", markup=True)

            yield Static("[b]Fee[/b] (↑/↓ to choose)", id="fee_title", markup=True)
            yield ListView(id="fee_list")

            # Suggested limits (shown only when advanced mode is active)
            yield Static("", id="suggested_limits", markup=True)

            # Advanced container (hidden by default)
            with Vertical(id="advanced"):
                yield Static("[b]Advanced (TX overrides)[/b]\nLeave blank to use suggested/autofill.", markup=True)
                with Horizontal():
                    yield Static("Fee (XTZ):", id="lbl_fee")
                    yield Input(placeholder="e.g. 0.005", id="fee_xtz")
                with Horizontal():
                    yield Static("Gas limit:", id="lbl_gas")
                    yield Input(placeholder="e.g. 20000", id="gas_limit")
                with Horizontal():
                    yield Static("Storage limit:", id="lbl_storage")
                    yield Input(placeholder="e.g. 0", id="storage_limit")

            # Advanced mode joke (near buttons)
            yield Static("", id="advanced_joke", markup=True)

            with Horizontal():
                if self.show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button("Delegate", id="delegate", variant="warning")
                yield Button("Advanced", id="toggle")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        adv = self.query_one("#advanced", Vertical)
        adv.styles.display = "none"

        # Hide suggested limits by default
        suggested_widget = self.query_one("#suggested_limits", Static)
        suggested_widget.styles.display = "none"

        # Hide advanced joke by default
        joke_widget = self.query_one("#advanced_joke", Static)
        joke_widget.styles.display = "none"

        self._start_est_pulse()
        self._render_summary(estimating=True)
        self._init_fee_list()
        self._update_fee_list(estimating=True)

        delegate_btn = self.query_one("#delegate", Button)
        delegate_btn.disabled = True
        delegate_btn.focus()
        self._estimate_worker()
        self.set_timer(Config.ESTIMATE_FALLBACK_SECONDS, self._apply_estimate_fallback)

    def on_unmount(self) -> None:
        self._stop_est_pulse()


    # -------------------------
    # Estimation pulse (ConfirmDelegateScreen)
    # -------------------------
    def _start_est_pulse(self) -> None:
        _start_estimation_pulse(self)

    def _stop_est_pulse(self) -> None:
        _stop_estimation_pulse(self)

    def _tick_est_pulse(self) -> None:
        _tick_estimation_pulse(self)

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)

        if estimating:
            lines = [
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]To:[/b yellow]        {self._baker_label}",
            ]
        elif err:
            lines = [
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]To:[/b yellow]        {self._baker_label}",
                "",
                f"[red]Fee estimate failed:[/red] {err}",
                "",
                "You can still DELEGATE (autofill) or use Advanced overrides.",
            ]
        else:
            # Simple summary (suggested limits moved to separate widget)
            lines = [
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]To:[/b yellow]        {self._baker_label}",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))

    def _init_fee_list(self) -> None:
        _init_fee_rows(self)

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        """Update fee rows text + checkmark without rebuilding ListView."""
        # Ensure list initialized
        if not self._fee_labels:
            self._init_fee_list()

        _update_fee_title(self, estimating=estimating, debug_context="Failed to update fee title in delegate confirm")

        texts = _build_fee_rows_text(
            self._fee_choice,
            estimate=self._estimate,
            estimating=estimating,
            err=err,
            value_prefix="total fee: ",
            selected_mark="✓ ",
            unselected_mark="  ",
        )

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        _handle_fee_selection(self, event, render_requires_estimate=True)

    @work(exclusive=True, thread=True)
    def _estimate_worker(self) -> None:
        try:
            est = estimate_delegation(self.rpc, self.from_addr, self.baker_address)
            self._estimate = est

            # Prefills Advanced with "suggested tx fee/gas/storage"
            tx = est.get("tx") or {}
            fee_mutez = int(tx.get("fee_mutez") or 0)
            gas = int(tx.get("gas_limit") or 0)
            storage = int(tx.get("storage_limit") or 0)

            def _ui_apply():
                self._stop_est_pulse()
                # default "normal"
                self._fee_choice = "normal"
                self._update_fee_list(estimating=False)
                self._render_summary(estimating=False)
                self._enable_delegate_button()

                self.query_one("#fee_xtz", Input).value = str(mutez_to_xtz(fee_mutez))
                self.query_one("#gas_limit", Input).value = str(gas) if gas else ""
                self.query_one("#storage_limit", Input).value = str(storage) if storage else ""

            # ModalScreen doesn't provide call_from_thread in some Textual versions.
            # Use the App bridge instead.
            self.app.call_from_thread(_ui_apply)

        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Failed to estimate delegation fees", exception=e)
            # Report error safely on UI thread
            self.app.call_from_thread(self._stop_est_pulse)
            self.app.call_from_thread(self._update_fee_list, False, str(e))
            self.app.call_from_thread(self._render_summary, False, str(e))

    def _apply_estimate_fallback(self) -> None:
        _apply_basic_estimate_fallback(self, enable_action=self._enable_delegate_button)

    def _enable_delegate_button(self) -> None:
        _enable_action_button(self, "#delegate", "Failed to enable delegate button in delegate confirm")

    def _toggle_advanced(self) -> None:
        self._advanced = not self._advanced
        adv = self.query_one("#advanced", Vertical)
        adv.styles.display = "block" if self._advanced else "none"

        # Show/hide suggested limits when toggling advanced
        suggested_widget = self.query_one("#suggested_limits", Static)
        if self._advanced and self._estimate:
            # Show suggested limits when opening advanced mode
            est = self._estimate or {}
            reveal_needed = bool(est.get("reveal_needed"))
            tx = est.get("tx") or {}
            gas = int(tx.get("gas_limit") or 0)
            storage = int(tx.get("storage_limit") or 0)

            limits_text = [
                f"[b cyan]Reveal:[/b cyan] {'yes (first send)' if reveal_needed else 'no'}",
                "",
                f"[dim]Suggested limits:[/dim] gas={gas}, storage={storage}",
                "[dim]Tip:[/dim] use Economy/Normal/Priority, Advanced only if you know what you're doing.",
            ]
            suggested_widget.update("\n".join(limits_text))
            suggested_widget.styles.display = "block"
        else:
            # Hide suggested limits when closing advanced mode
            suggested_widget.styles.display = "none"

        # Show/hide sarcastic joke when toggling advanced
        joke_widget = self.query_one("#advanced_joke", Static)
        if self._advanced:
            # Show joke when opening advanced mode
            message = get_advanced_mode_message()
            joke_widget.update(f"[bold]{message}[/bold]")
            joke_widget.styles.display = "block"
        else:
            # Hide joke when closing advanced mode
            joke_widget.styles.display = "none"

        self.query_one("#toggle", Button).label = "Basic" if self._advanced else "Advanced"
        if self._advanced:
            self.query_one("#fee_xtz", Input).focus()
        else:
            _focus_with_fallback(
                self,
                primary=("#fee_list", ListView),
                fallbacks=(("#send", Button), ("#delegate", Button)),
                primary_error="Failed to focus fee list",
                fallback_error="Failed to focus fallback buttons in delegate confirm",
            )

    @on(Button.Pressed, "#toggle")
    def toggle_pressed(self) -> None:
        self._toggle_advanced()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(_tx_modal_result(ok=False))

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss(_tx_modal_result(ok=False, back=True))

    @on(Button.Pressed, "#delegate")
    def delegate_pressed(self) -> None:
        # Advanced mode => manual overrides
        if self._advanced:
            try:
                fee_mutez, gas, storage = _parse_tx_overrides(self)
            except (ValueError, TypeError) as e:
                log_error("Failed to parse override values", exception=e)
                self._render_summary(err=str(e))
                return
            self.dismiss(_tx_modal_result(ok=True, fee_mutez=fee_mutez, gas_limit=gas, storage_limit=storage))
            return

        # Normal mode => fee by selector, gas/storage via autofill
        fee_mutez = _tx_fee_mutez_from_choice(self._estimate, self._fee_choice)
        self.dismiss(_tx_modal_result(ok=True, fee_mutez=fee_mutez))

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        _handle_tx_confirm_key(
            self,
            event,
            key,
            context="delegate confirm",
            action_handler=self.delegate_pressed,
        )


class ConfirmChangeBakerScreen(ConfirmDelegateScreen):
    """Confirmation modal for changing baker (delegation under the hood)."""

    CSS = """
    ConfirmChangeBakerScreen {
        align: center middle;
    }

    ConfirmChangeBakerScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        min-height: 22;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #eab308;
        padding: 1 2;
    }

    ConfirmChangeBakerScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    ConfirmChangeBakerScreen #summary {
        margin-bottom: 0;
    }

    ConfirmChangeBakerScreen #fee_title {
        margin-bottom: 0;
        color: $accent;
    }

    ConfirmChangeBakerScreen #fee_list {
        height: 4;
        margin-bottom: 1;
    }

    ConfirmChangeBakerScreen #fee_list > ListItem {
        padding: 0 0 0 2;
    }

    ConfirmChangeBakerScreen #suggested_limits {
        margin-top: 1;
        margin-bottom: 1;
        color: $text-muted;
        min-height: 2;
    }

    ConfirmChangeBakerScreen #advanced {
        margin-top: 0;
        margin-bottom: 1;
    }

    ConfirmChangeBakerScreen #advanced_joke {
        margin-top: 1;
        margin-bottom: 0;
        color: #f97316;
        text-style: bold italic;
        min-height: 2;
    }

    ConfirmChangeBakerScreen Input {
        border: solid #4b5563;
        background: transparent;
        padding: 0 1;
    }

    ConfirmChangeBakerScreen Input:focus {
        border: solid #10b981;
    }

    ConfirmChangeBakerScreen Horizontal {
        align: center middle;
        margin-top: 1;
    }

    ConfirmChangeBakerScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        rpc: str,
        from_addr: str,
        current_baker_address: str,
        new_baker_address: str,
        show_back_button: bool = False,
    ):
        super().__init__(rpc=rpc, from_addr=from_addr, baker_address=new_baker_address, show_back_button=show_back_button)
        self.current_baker_address = current_baker_address
        self.new_baker_address = new_baker_address
        self._current_baker_label = self._resolve_current_baker_label()
        self._new_baker_label = self._baker_label

    def _resolve_current_baker_label(self) -> str:
        if not self.current_baker_address:
            return "—"
        info = get_baker_info(self.rpc, self.current_baker_address, force_refresh=True)
        alias = info.get("alias") if info else None
        if alias:
            return f"{alias} [dim]({self.current_baker_address})[/dim]"
        return self.current_baker_address

    def compose(self) -> ComposeResult:
        # Same structure as ConfirmDelegateScreen, but with different primary button label.
        with Vertical():
            yield Static("[b]Confirm Baker Change[/b]", id="title", markup=True)
            yield Static("", id="summary", markup=True)

            yield Static("[b]Fee[/b] (↑/↓ to choose)", id="fee_title", markup=True)
            yield ListView(id="fee_list")

            # Suggested limits (shown only when advanced mode is active)
            yield Static("", id="suggested_limits", markup=True)

            # Advanced container (hidden by default)
            with Vertical(id="advanced"):
                yield Static("[b]Advanced (TX overrides)[/b]\nLeave blank to use suggested/autofill.", markup=True)
                with Horizontal():
                    yield Static("Fee (XTZ):", id="lbl_fee")
                    yield Input(placeholder="e.g. 0.005", id="fee_xtz")
                with Horizontal():
                    yield Static("Gas limit:", id="lbl_gas")
                    yield Input(placeholder="e.g. 20000", id="gas_limit")
                with Horizontal():
                    yield Static("Storage limit:", id="lbl_storage")
                    yield Input(placeholder="e.g. 0", id="storage_limit")

            # Advanced mode joke (near buttons)
            yield Static("", id="advanced_joke", markup=True)

            with Horizontal():
                if self.show_back_button:
                    yield Button("← Back", id="back", variant="default")
                yield Button("Change Baker", id="delegate", variant="warning")
                yield Button("Advanced", id="toggle")
                yield Button("Cancel", id="cancel")

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)
        if estimating:
            lines = [
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]Current:[/b yellow]   {self._current_baker_label}",
                "",
                f"[b yellow]New:[/b yellow]       {self._new_baker_label}",
                "",
                "[dim]Note:[/dim] Existing staked tez moves to unstaking until finalization.",
            ]
        elif err:
            lines = [
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]Current:[/b yellow]   {self._current_baker_label}",
                "",
                f"[b yellow]New:[/b yellow]       {self._new_baker_label}",
                "",
                f"[red]Fee estimate failed:[/red] {err}",
                "",
                "[dim]Note:[/dim] Existing staked tez moves to unstaking until finalization.",
                "",
                "You can still CHANGE BAKER (autofill) or use Advanced overrides.",
            ]
        else:
            lines = [
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]Current:[/b yellow]   {self._current_baker_label}",
                "",
                f"[b yellow]New:[/b yellow]       {self._new_baker_label}",
                "",
                "[dim]Note:[/dim] Existing staked tez moves to unstaking until finalization.",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))

class SendScreen(ModalScreen[Optional[dict]]):
    """
    Unified Send screen showing From/To/Amount all at once.
    
    Returns dict or None:
      {
        "from_account": Account,
        "to_addr": str,
        "amount": Decimal
      }
    """
    CSS = """
    SendScreen {
        align: center middle;
    }

    SendScreen #send_root.hidden {
        display: none;
    }

    SendScreen > Vertical {
        width: 76;
        min-width: 76;
        max-width: 76;
        height: 36;
        min-height: 36;
        max-height: 36;
        overflow-y: hidden;
        background: $surface;
        border: heavy #10b981;
        padding: 1 2;
    }

    SendScreen #title {
        margin-bottom: 1;
        color: $accent;
    }

    SendScreen #wallet_selector_label {
        margin-bottom: 0;
    }

    SendScreen #wallet_selector {
        margin-bottom: 1;
        min-height: 8;
        max-height: 10;
    }

    SendScreen #wallet_selector > ListItem {
        padding: 0 0 0 2;
    }

    SendScreen #to_label {
        margin-top: 1;
        margin-bottom: 0;
    }

    SendScreen Input {
        margin-top: 0;
        margin-bottom: 0;
        border: solid #4b5563;
        background: transparent;
        padding: 0 1;
    }

    SendScreen Input:focus {
        border: solid #10b981;
    }

    SendScreen #hint_text {
        margin-top: 0;
        margin-bottom: 0;
        height: auto;
        color: $text-muted;
    }

    SendScreen #hint_text:hover {
        color: $accent;
        text-style: bold;
    }

    SendScreen #quick_destinations {
        margin-top: 0;
        margin-bottom: 1;
        max-height: 6;
    }

    SendScreen #quick_destinations > ListItem {
        padding: 0 0 0 2;
    }

    SendScreen #amount_label {
        margin-bottom: 0;
    }

    SendScreen #amount_comment {
        margin-top: 0;
        margin-bottom: 1;
        color: #fbbf24;
        text-style: italic;
        min-height: 1;
    }

    SendScreen Horizontal {
        align: center middle;
    }

    SendScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, accounts: list["Account"], rpc: str, recent_to: list[str]):
        super().__init__()
        # Filter only accounts with secret keys (not watch-only)
        self.accounts = [acc for acc in accounts if acc.enc is not None]
        self.rpc = rpc
        self.recent_to = recent_to  # Last used addresses
        self.selected_account: Optional["Account"] = None
        self.balance_xtz: Decimal = Decimal(0)
        self._balance_cache: dict[str, Decimal] = {}
        self._balance_loading = False
        self._blocked_new_wallet = False
        self._quick_destination_addrs: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="send_root"):
            yield Static("[b]Select Source Wallet:[/b]", id="title", markup=True)

            # Wallet selector (always visible)
            yield ListView(id="wallet_selector")

            # To address (always visible)
            yield Static("[b]To Address:[/b]", id="to_label", markup=True)
            yield Input(placeholder="tz1/tz2/tz3/tz4/KT1 address...", id="to_input")
            yield Static("", id="hint_text", markup=True)
            yield ListView(id="quick_destinations")

            # Amount (always visible)
            yield Static("[b]Amount (XTZ):[/b]", id="amount_label", markup=True)
            yield Input(placeholder="e.g., 0.5 or 1", id="amount_input")

            # Comment appears here, right before buttons
            yield Static("", id="amount_comment", markup=True)

            # Buttons
            with Horizontal(id="button_container"):
                yield Button("Next →", id="next", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Populate wallet selector with balances."""
        lv = self.query_one("#wallet_selector", ListView)
        lv.clear()

        if not self.accounts:
            label_text = "[dim]No wallets with secret keys available[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))
        else:
            # Add all wallets
            for acc in self.accounts:
                addr_short = acc.address[:10] + "…" + acc.address[-8:]
                label_text = f"[b]{acc.name}[/b] [dim]Loading...[/dim]\n[dim]{addr_short}[/dim]"
                lv.append(ListItem(Label(label_text, markup=True)))

            lv.index = 0
            # Pre-select first wallet
            self._select_wallet(0)

            # Load balances asynchronously (threaded to avoid UI lag)
            self.run_worker(self._load_wallet_balances, exclusive=False, thread=True)

        # Populate quick destinations
        self._populate_quick_destinations()

    def _populate_quick_destinations(self) -> None:
        """Populate quick destinations list with recent + loaded wallets."""
        dest_lv = self.query_one("#quick_destinations", ListView)
        dest_lv.clear()

        from_addr = self.selected_account.address if self.selected_account else None
        self._quick_destination_addrs = []

        # Add last used address if available
        if self.recent_to:
            recent_addr = self.recent_to[0]
            if recent_addr and recent_addr != from_addr:
                recent_short = f"{recent_addr[:10]}...{recent_addr[-8:]}"
                label_text = f"💡 [b cyan]Last used:[/b cyan] {recent_short}"
                dest_lv.append(ListItem(Label(label_text, markup=True)))
                self._quick_destination_addrs.append(recent_addr)

        # Add all loaded wallets as quick destinations
        for acc in self.accounts:
            if from_addr and acc.address == from_addr:
                continue
            addr_short = f"{acc.address[:10]}…{acc.address[-8:]}"
            label_text = f"📱 [b]{acc.name}[/b] [dim]{addr_short}[/dim]"
            dest_lv.append(ListItem(Label(label_text, markup=True)))
            self._quick_destination_addrs.append(acc.address)

        # Show hint
        if self._quick_destination_addrs:
            self._set_hint("[dim]💡 Click below to quick-fill address[/dim]")
        else:
            self._set_hint("")

    def _load_wallet_balances(self) -> None:
        """Load wallet balances without blocking UI (threaded)."""
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        indices = list(range(len(self.accounts)))
        if self.selected_account:
            sel_idx = next(
                (i for i, acc in enumerate(self.accounts) if acc.address == self.selected_account.address),
                None,
            )
            if sel_idx is not None:
                indices = [sel_idx] + [i for i in indices if i != sel_idx]

        for idx in indices:
            acc = self.accounts[idx]
            try:
                addr_short = acc.address[:10] + "…" + acc.address[-8:]
                spin = spinner[idx % len(spinner)]
                self.app._ui(
                    self._update_send_wallet_row,
                    idx,
                    f"{spin} [b]{acc.name}[/b] [dim]Loading...[/dim]\n[dim]{addr_short}[/dim]",
                )

                if acc.address in self._balance_cache:
                    balance_xtz = self._balance_cache[acc.address]
                else:
                    balance_mutez = get_balance_mutez(self.rpc, acc.address)
                    balance_xtz = mutez_to_xtz(balance_mutez)
                    self._balance_cache[acc.address] = balance_xtz
                balance_str = format_xtz(balance_xtz)
                if balance_xtz <= 0:
                    label_text = f"[b]{acc.name}[/b] [#34d399]{balance_str} XTZ[/#34d399] [#f97316]NEW WALLET[/#f97316]\n[dim]{addr_short}[/dim]"
                else:
                    label_text = f"[b]{acc.name}[/b] [#34d399]{balance_str} XTZ[/#34d399]\n[dim]{addr_short}[/dim]"

                # Update list item
                self.app._ui(self._update_send_wallet_row, idx, label_text)

                # Update selected account balance if this is the one
                if self.selected_account and self.selected_account.address == acc.address:
                    self.balance_xtz = balance_xtz
                    self._balance_loading = False

            except _FLOW_PRECHECK_EXCEPTIONS as e:
                log_error(f"Failed to load balance for {acc.name}", exception=e)

    def _update_send_wallet_row(self, idx: int, label_text: str) -> None:
        """Update a wallet row in the send selector (UI thread)."""
        try:
            lv = self.query_one("#wallet_selector", ListView)
            list_items = list(lv.children)
            if idx < len(list_items):
                item = list_items[idx]
                label = item.query_one(Label)
                label.update(label_text)
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update send wallet row", exception=e)

    @on(ListView.Selected, "#wallet_selector")
    def wallet_selected(self, event: ListView.Selected) -> None:
        """Handle wallet selection from ListView."""
        if event.list_view.index is not None:
            self._select_wallet(event.list_view.index)

    def _select_wallet(self, index: int) -> None:
        """Select wallet and update balance."""
        if index < 0 or index >= len(self.accounts):
            return

        self.selected_account = self.accounts[index]
        self._blocked_new_wallet = False
        cached = self._balance_cache.get(self.selected_account.address)
        if cached is not None:
            self.balance_xtz = cached
            self._balance_loading = False
        else:
            self.balance_xtz = Decimal(0)
            self._balance_loading = True

        if self.balance_xtz <= 0:
            self._blocked_new_wallet = True

        self._populate_quick_destinations()
        if self._balance_loading:
            self._fetch_balance_for_selected()

    @work(thread=True)
    def _fetch_balance_for_selected(self) -> None:
        try:
            if not self.selected_account:
                return
            addr = self.selected_account.address
            balance_mutez = get_balance_mutez(self.rpc, addr)
            balance_xtz = mutez_to_xtz(balance_mutez)
            self._balance_cache[addr] = balance_xtz
            self.app.call_from_thread(self._apply_selected_balance, addr, balance_xtz)
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_error("Failed to get wallet balance", exception=e)

    def _apply_selected_balance(self, address: str, balance_xtz: Decimal) -> None:
        if not self.selected_account or self.selected_account.address != address:
            return
        self.balance_xtz = balance_xtz
        self._balance_loading = False
        self._blocked_new_wallet = self.balance_xtz <= 0

    def _set_amount_comment(self, text: str) -> None:
        self.query_one("#amount_comment", Static).update(text)

    def _set_hint(self, text: str) -> None:
        self.query_one("#hint_text", Static).update(text)

    @on(ListView.Selected, "#quick_destinations")
    def destination_selected(self, event: ListView.Selected) -> None:
        """When user clicks a quick destination, fill the To address."""
        if event.list_view.index is None:
            return

        index = event.list_view.index
        to_input = self.query_one("#to_input", Input)
        if 0 <= index < len(self._quick_destination_addrs):
            to_input.value = self._quick_destination_addrs[index]

        to_input.focus()

    @on(Input.Changed, "#amount_input")
    def on_amount_changed(self, event: Input.Changed) -> None:
        """Show sassy comment based on amount entered."""
        try:
            amount_input = self.query_one("#amount_input", Input)
            filtered = filter_amount_input(event.value)
            if filtered != event.value:
                amount_input.value = filtered
            value = sanitize_input(filtered)
            if not value:
                self._set_amount_comment("")
                return

            amount = Decimal(value)
            if amount <= 0:
                self._set_amount_comment("")
                return

            # Show sassy comment based on amount
            comment = get_amount_comment(amount)
            self._set_amount_comment(f"[dim italic]{comment}[/dim italic]")
        except (ValueError, decimal.InvalidOperation):
            self._set_amount_comment("")

    @on(Input.Changed, "#to_input")
    def on_to_changed(self, event: Input.Changed) -> None:
        to_input = self.query_one("#to_input", Input)
        filtered = filter_base58_input(event.value)
        if filtered != event.value:
            to_input.value = filtered
        if not filtered:
            self._set_hint("")
            return
        if len(filtered) < 36:
            self._set_hint(f"[dim]Address length: {len(filtered)}/36[/dim]")
            return
        is_valid, error_msg = validate_tezos_address(filtered, allow_kt1=True)
        if not is_valid:
            self._set_hint(f"[red]✗ {error_msg}[/red]")
        else:
            self._set_hint("[#34d399]✓ Address looks valid[/#34d399]")

    @on(Input.Submitted, "#to_input")
    async def to_submitted(self, event: Input.Submitted) -> None:
        await self.next_pressed()

    @on(Input.Submitted, "#amount_input")
    async def amount_submitted(self, event: Input.Submitted) -> None:
        await self.next_pressed()

    @on(Button.Pressed, "#next")
    async def next_pressed(self) -> None:
        """Validate and return data."""
        if not self.selected_account:
            self._set_amount_comment("[red]✗ Please select a wallet first[/red]")
            return
        if self._balance_loading:
            self._set_amount_comment("[dim]⏳ Balance still loading...[/dim]")
            return
        if self._blocked_new_wallet:
            self._set_amount_comment(
                "[red]⚠️ No balance in this wallet, dude! What are you sending? Croissants? ¬_¬[/red]"
            )
            return

        # Get To address
        to_input = self.query_one("#to_input", Input)
        to_addr = sanitize_input(to_input.value)

        if not to_addr:
            self._set_hint("[red]✗ Please enter a destination address[/red]")
            to_input.focus()
            return

        # Validate address
        is_valid, error_msg = validate_tezos_address(to_addr, allow_kt1=True)
        if not is_valid:
            self._set_hint(f"[red]✗ {error_msg}[/red]")
            to_input.focus()
            return
        if self.selected_account and to_addr == self.selected_account.address:
            self._set_hint("[red]✗ Cannot send to the same wallet[/red]")
            to_input.focus()
            return

        # Get amount
        amount_input = self.query_one("#amount_input", Input)
        amount_str = sanitize_input(amount_input.value)

        if not amount_str:
            self._set_amount_comment("[red]✗ Please enter an amount[/red]")
            amount_input.focus()
            return

        # Validate amount
        is_valid, error_msg, amount = validate_amount(amount_str, min_value=Decimal("0"))
        if not is_valid:
            self._set_amount_comment(f"[red]✗ {error_msg}[/red]")
            amount_input.focus()
            return

        # Check sufficient balance
        estimated_max_fee = Decimal("0.01")
        total_needed = amount + estimated_max_fee

        if self.balance_xtz < total_needed:
            self._set_amount_comment(
                f"[red]✗ Insufficient balance. Have: {format_xtz(self.balance_xtz)} XTZ, "
                f"Need: ~{format_xtz(total_needed)} XTZ (including fees)[/red]"
            )
            amount_input.focus()
            return

        error_note = ""
        while True:
            # Step 2: Passphrase
            self.query_one("#send_root", Vertical).add_class("hidden")
            try:
                pw = await self.app.push_screen_wait(  # type: ignore[attr-defined]
                    SendPassphraseScreen(
                        "Enter Your Encryption Password",
                        password=True,
                        placeholder="Your wallet encryption password",
                        wallet_info=f"[b]{self.selected_account.name}[/b]",
                        ok_label="Next →",
                        fun_note="The moment of truth! Like opening a safe, but cooler. 🔓✨",
                        show_back_button=True,
                        error_note=error_note,
                    )
                )
            finally:
                self.query_one("#send_root", Vertical).remove_class("hidden")

            if pw == BACK_NAV_MARKER:
                return

            if not pw:
                self.app._set_status("🚫 Send canceled — keeping my baguettes. 🥖")  # type: ignore[attr-defined]
                self.dismiss(None)
                return

            try:
                secret = decrypt_secret(self.selected_account.enc, pw)
                key = key_from_encoded_secret(secret)
            except _CRYPTO_DECODE_EXCEPTIONS as e:
                log_error("Failed to decrypt secret key", exception=e)
                if isinstance(e, InvalidTag):
                    error_note = "❌ Wrong encryption password. Try again."
                else:
                    error_note = f"❌ Decrypt key failed: {e}"
                continue

            # Step 3: Confirm and estimate
            self.query_one("#send_root", Vertical).add_class("hidden")
            try:
                resp = await self.app.push_screen_wait(  # type: ignore[attr-defined]
                    ConfirmSendScreen(self.rpc, key, self.selected_account.address, to_addr, amount, show_back_button=True)
                )
            finally:
                self.query_one("#send_root", Vertical).remove_class("hidden")

            if resp and resp.get(BACK_NAV_MARKER):
                continue

            if not resp or not resp.get("ok"):
                self.app._set_status("🚫 Send canceled — keeping my baguettes. 🥖")  # type: ignore[attr-defined]
                self.dismiss(None)
                return

            self.dismiss(
                {
                    "from_account": self.selected_account,
                    "to_addr": to_addr,
                    "amount": amount,
                    "key": key,
                    "fee_mutez": resp.get("fee_mutez"),
                    "gas_limit": resp.get("gas_limit"),
                    "storage_limit": resp.get("storage_limit"),
                }
            )
            return

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)

        # Let Input handle keys naturally, but allow escape to blur first
        if _handle_input_escape_focus_cancel(
            self,
            event,
            key,
            context="send screen",
            fallbacks=(("#next", Button),),
        ):
            return

        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return
class DestinationPickerScreen(ModalScreen[str]):
    """Input + lista de últimos destinos + wallets cargadas (click/enter). Flechas funcionan si lista tiene foco."""

    CSS = """
    DestinationPickerScreen {
        align: center middle;
    }

    DestinationPickerScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #10b981;
        padding: 1 2;
    }

    DestinationPickerScreen Static {
        margin-bottom: 0;
    }

    #dest_inp {
        margin-bottom: 0;
        border: solid #4b5563;
        background: transparent;
        padding: 0 1;
    }

    #dest_inp:focus {
        border: solid #10b981;
    }

    #sassy_comment {
        margin-top: 1;
        margin-bottom: 0;
        color: #fbbf24;
        text-style: italic;
        min-height: 2;
    }

    #wallets_title {
        margin-top: 1;
        margin-bottom: 0;
        color: $accent;
    }

    #wallets_list {
        height: auto;
        max-height: 6;
        margin-bottom: 1;
    }

    #wallets_list > ListItem {
        padding: 0 0 0 2;
    }

    #recent_title {
        margin-top: 1;
        margin-bottom: 0;
        color: $accent;
    }

    #recent_list {
        height: auto;
        max-height: 4;
        margin-bottom: 1;
    }

    #recent_list > ListItem {
        padding: 0 0 0 2;
    }

    DestinationPickerScreen Horizontal {
        align: center middle;
    }

    DestinationPickerScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, recents: list[str], accounts: list, from_address: str):
        super().__init__()
        self.recents = recents[:Config.RECENT_DESTINATIONS_MAX]
        # Filter out the sending wallet (can't send to yourself)
        self.accounts = [acc for acc in accounts if acc.address != from_address]
        self.from_address = from_address

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Send to Address[/b]\nEnter destination address (tz1/tz2/tz3/tz4 or KT1)", markup=True)
            yield Input(placeholder="Paste address here…", id="dest_inp")
            yield Static("", id="dest_validation_hint", markup=True)

            # Your wallets section
            if self.accounts:
                yield Static("Your wallets:", id="wallets_title", markup=True)
                yield ListView(id="wallets_list")

            # Recent destinations section
            yield Static("Recent destinations:", id="recent_title", markup=True)
            yield ListView(id="recent_list")

            # Sassy comment appears here, right before buttons
            yield Static("", id="sassy_comment", markup=True)

            with Horizontal():
                yield Button("OK", id="ok")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#dest_inp", Input).focus()

        # Populate wallets list
        if self.accounts:
            wl = self.query_one("#wallets_list", ListView)
            wl.clear()
            for acc in self.accounts:
                # Show name and shortened address
                display = f"{acc.name} ({acc.address[:10]}...{acc.address[-6:]})"
                lbl = Label(display)
                lbl.tooltip = acc.address  # Full address on hover
                wl.append(ListItem(lbl))

        # Populate recent destinations list
        lv = self.query_one("#recent_list", ListView)
        lv.clear()
        if not self.recents:
            lv.append(ListItem(Label("[dim]No recent destinations yet[/dim]", markup=True)))
        else:
            for a in self.recents:
                lv.append(ListItem(Label(a)))

    def _current_value(self) -> str:
        return (self.query_one("#dest_inp", Input).value or "").strip()

    def _set_dest_hint(self, text: str) -> None:
        self.query_one("#dest_validation_hint", Static).update(text)

    def _set_sassy_comment(self, text: str) -> None:
        self.query_one("#sassy_comment", Static).update(text)

    @on(Input.Changed, "#dest_inp")
    def on_dest_input_changed(self, event: Input.Changed) -> None:
        """Validate destination address in real-time."""
        value = sanitize_input(event.value)

        if not value:
            self._set_dest_hint("")
            self._set_sassy_comment("")
            return

        # Check if sending to self
        if value == self.from_address:
            self._set_dest_hint("[red]✗ Cannot send to yourself[/red]")
            self._set_sassy_comment("")
            return

        # Validate address
        is_valid, error_msg = validate_tezos_address(value, allow_kt1=True)
        if is_valid:
            self._set_dest_hint("[#34d399]✓ Valid Tezos address[/#34d399]")
            # Show a sassy comment when address is valid
            self._set_sassy_comment(f"[dim italic]{get_recipient_comment()}[/dim italic]")
        else:
            self._set_sassy_comment("")
            # Only show error if the address looks complete (36 characters)
            if len(value) >= 36:
                self._set_dest_hint(f"[red]✗ {error_msg}[/red]")
            elif len(value) > 3:
                self._set_dest_hint("[yellow]⏳ Enter complete address (36 characters)...[/yellow]")
            else:
                self._set_dest_hint("")

    @on(Input.Submitted, "#dest_inp")
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss((event.value or "").strip())

    @on(ListView.Selected, "#wallets_list")
    def pick_wallet(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        if 0 <= idx < len(self.accounts):
            self.query_one("#dest_inp", Input).value = self.accounts[idx].address

    @on(ListView.Selected, "#recent_list")
    def pick_recent(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        if 0 <= idx < len(self.recents):
            self.query_one("#dest_inp", Input).value = self.recents[idx]

    @on(Button.Pressed, "#ok")
    def ok_pressed(self) -> None:
        self.dismiss(self._current_value())

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss("")

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)

        if _handle_input_escape_focus_cancel(
            self,
            event,
            key,
            context="destination picker",
            fallbacks=(("#ok", Button),),
        ):
            return

        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return

        if key == "down":
            try:
                inp = self.query_one("#dest_inp", Input)
                lv = self.query_one("#recent_list", ListView)
                if inp.has_focus:
                    lv.focus()
                    return
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to handle down key in destination picker", exception=e)

        if key == "enter":
            try:
                lv = self.query_one("#recent_list", ListView)
                if lv.has_focus and self.recents:
                    idx = lv.index or 0
                    if 0 <= idx < len(self.recents):
                        self.dismiss(self.recents[idx])
                        return
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to handle enter key in destination picker", exception=e)


class WalletApp(App):
    CSS = """
    Screen {
        padding: 0;
        align: left top;
    }

    /* Keep main padding inside a fixed container to avoid modal-open layout shifts. */
    #main_content {
        padding: 1 24;
        align: center top;
    }

    Footer {
        padding: 0 24;
        margin-top: 0;
    }

    /* Global Input styles to ensure text is always visible */
    Input {
        color: $text;
    }

    Input:focus {
        color: $text;
    }

    Input > .input--cursor {
        color: #ffffff;
        background: #10b981;
    }

    Input > .input--placeholder {
        color: #64748b;
    }

    Button {
        background: #3b82f6;
        color: white;
        height: 3;
        min-height: 3;
        padding: 0 2;
        border: none;
        outline: none;
    }

    Button:hover {
        background: #2563eb;
        color: white;
        border: none;
        outline: none;
    }

    Button:focus {
        background: #1e40af;
        color: #f8fafc;
        border: none;
        outline: none;
        text-style: bold;
    }

    ModalScreen Button {
        border: none;
    }

    ModalScreen Horizontal > Button {
        margin: 0 1;
    }

    ModalScreen {
        background: transparent;
    }


    ModalScreen Button#back,
    ModalScreen Button#cancel,
    ModalScreen Button#next,
    ModalScreen Button#back_btn {
        background: #334155;
        color: #f8fafc;
        border: none;
    }

    ModalScreen Button#back:hover,
    ModalScreen Button#cancel:hover,
    ModalScreen Button#next:hover,
    ModalScreen Button#back_btn:hover,
    ModalScreen Button#back:focus,
    ModalScreen Button#cancel:focus,
    ModalScreen Button#next:focus,
    ModalScreen Button#back_btn:focus {
        background: #3b82f6;
        color: #f8fafc;
        border: none;
    }

    ListView > ListItem.--highlight,
    ListView > ListItem.--selected {
        background: rgba(59, 130, 246, 0.25);
    }

    ListView:focus > ListItem.--highlight,
    ListView:focus > ListItem.--selected {
        background: rgba(59, 130, 246, 0.25);
    }

    #banner {
        height: auto;
        margin-bottom: 1;
        padding: 1 1 1 1;
    }

    #accounts_header {
        height: auto;
        margin-bottom: 1;
        align: left middle;
    }

    #tagline {
        width: 1fr;
        content-align: right middle;
        margin-left: 2;
        padding-right: 1;
        color: #a855f7;
        text-style: italic;
    }

    #add {
        width: auto;
        background: #3b82f6;
        color: white;
        content-align: center middle;
        margin-right: 1;
    }

    #add:hover {
        background: #2563eb;
        color: white;
    }

    #backup {
        width: auto;
        background: #eab308;
        color: white;
        content-align: center middle;
        margin-right: 1;
    }

    #backup:hover {
        background: #ca8a04;
        color: white;
    }

    #delete {
        width: auto;
        background: #ef4444;
        color: white;
        content-align: center middle;
    }

    #delete:hover {
        background: #dc2626;
        color: white;
    }

    #exit {
        width: auto;
        background: #9ca3af;
        color: #111827;
        content-align: center middle;
        margin-left: 1;
    }

    #exit:hover {
        background: #6b7280;
        color: #f8fafc;
    }

    #accounts_columns_header {
        height: 1;
        margin-bottom: 0;
        padding-left: 2;
        color: $accent;
    }

    #accounts {
        height: 2;
        max-height: 2;
        overflow-y: auto;
        margin-bottom: 1;
    }

    #accounts > ListItem {
        height: 1;
    }

    #accounts > ListItem {
        margin-bottom: 0;
        padding: 0 0 0 2;
        height: 1;
    }

    #accounts > ListItem > Horizontal {
        width: 100%;
        height: 1;
    }

    #accounts > ListItem > Horizontal > Label.account_name {
        width: 26;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        content-align: left middle;
    }

    #accounts > ListItem > Horizontal > Label.account_sep {
        width: 1;
        content-align: center middle;
    }

    #accounts > ListItem > Horizontal > Label.account_address {
        width: auto;
        min-width: 0;
        content-align: left middle;
    }

    #accounts > ListItem > Horizontal > Label.account_marker {
        width: 2;
        content-align: center middle;
    }

    #accounts > ListItem > Horizontal > Button.copy_addr {
        width: 3;
        min-width: 3;
        max-width: 3;
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0;
        margin-left: 1;
        border: none;
        outline: none;
        background: transparent;
        color: #cbd5f5;
        content-align: center middle;
        text-style: dim;
    }

    #accounts > ListItem > Horizontal > Button.copy_addr:hover {
        background: transparent;
        color: #f8fafc;
    }

    #accounts > ListItem > Horizontal > Button.copy_addr:focus {
        background: transparent;
        color: #ffffff;
    }

    #wallet_details {
        height: auto;
        padding: 0 1 0 2;
        margin-bottom: 0;
        background: $surface;
    }

    #wallet_status {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
    }

    #wallet_balance {
        height: auto;
        margin-bottom: 1;
    }

    #wallet_delegation {
        height: auto;
        margin-bottom: 1;
    }

    #wallet_staking {
        height: auto;
        margin-bottom: 1;
    }

    #wallet_network {
        height: auto;
        margin-bottom: 0;
    }

    #action_buttons {
        height: auto;
        margin-top: 1;
        margin-bottom: 0;
        padding-bottom: 1;
    }

    #send {
        background: #10b981;
        color: white;
        margin-right: 1;
    }

    #send:hover {
        background: #059669;
        color: white;
    }

    #recv {
        background: #374151;
        color: white;
        margin-right: 1;
    }

    #recv:hover {
        background: #1f2937;
        color: white;
    }

    #stake {
        background: #8b5cf6;
        color: white;
        margin-right: 1;
    }

    #stake:hover {
        background: #7c3aed;
        color: white;
    }

    #refresh {
        background: #f97316;
        color: white;
    }

    #refresh:hover {
        background: #ea580c;
        color: white;
    }

    #hist_title {
        height: auto;
        margin-top: 0;
        margin-bottom: 0;
        color: $accent;
        padding-left: 2;
    }

    #history_headers {
        height: 1;
        margin-bottom: 0;
        color: $accent;
    }

	    #history_header {
	        width: 60%;
	        padding-left: 2;
	        color: $accent;
	        background: $surface;
	    }

	    #tx_detail_header {
	        width: 40%;
	        padding-left: 1;
	        color: $accent;
	        background: $surface;
	        border-left: solid $primary;
	    }

    #history_split {
        height: 1fr;
    }

	    #history {
	        width: 60%;
	        height: 100%;
	    }

    #history > ListItem {
        padding: 0 0 0 2;
    }

	    #tx_detail_pane {
	        width: 40%;
	        height: 100%;
	        padding: 1;
	        border-left: solid $primary;
	        overflow-y: auto;
	    }

    #tx_detail_content {
        height: auto;
        padding: 0 1;
    }

    #tx_detail_content Link {
        color: #3b82f6;
        text-style: underline;
    }

    #tx_detail_content Link:hover {
        color: #60a5fa;
        text-style: bold underline;
    }

    #bottom_bar {
        height: auto;
        min-height: 1;
        margin-top: 0;
        margin-bottom: 0;
        padding: 0;
        background: $boost;
        border: heavy $accent;
        border-title-align: left;
    }

    #status_line {
        width: 1fr;
        height: auto;
        padding: 0 1;
        text-align: left;
        color: $text;
        text-style: bold;
        background: $boost;
    }

    #tx_link_area {
        width: auto;
        padding: 0 1;
        text-align: center;
        color: #3b82f6;
        text-style: bold;
        background: $boost;
        link-style: underline;
    }

    #price_indicator {
        width: auto;
        min-width: 10;
        padding: 0 1;
        text-align: right;
        color: #3b82f6;
        text-style: bold;
        background: $boost;
    }

    #rpc_indicator {
        width: auto;
        min-width: 18;
        padding: 0 1;
        text-align: right;
        color: #16a34a;
        text-style: bold;
        background: $boost;
    }

    /* Status bar states with glow effects */
    #bottom_bar.status-success {
        border: heavy #16a34a;
        background: #0f1f16;
    }

    #bottom_bar.status-warning {
        border: heavy #ca8a04;
        background: #2a1f0a;
    }

    #bottom_bar.status-warning-dim {
        border: heavy #a16207;
        background: #241c0f;
    }

    #bottom_bar.status-error {
        border: heavy #dc2626;
        background: #2a0f12;
    }

    #bottom_bar.status-info {
        border: heavy #60a5fa;
        background: #0f1a2e;
    }

    /* Stake/Unstake: higher-contrast pulse so the blink is obvious in terminals. */
    #bottom_bar.status-stake {
        border: heavy #a855f7;
        background: #240a38;
    }

    #bottom_bar.status-unstake {
        border: heavy #a855f7;
        background: #2a0b3f;
    }

    #bottom_bar.status-stake-dim {
        border: heavy #6d28d9;
        background: #14061f;
    }

    #bottom_bar.status-unstake-dim {
        border: heavy #6d28d9;
        background: #14061f;
    }

    #status_line.status-success {
        color: #22c55e;
        background: #0f1f16;
    }

    #bottom_bar.status-success-dim {
        border: heavy #15803d;
        background: #0b1a12;
    }

    #status_line.status-success-dim {
        color: #16a34a;
        background: #0b1a12;
    }

    #status_line.status-warning {
        color: #eab308;
        background: #2a1f0a;
    }

    #status_line.status-warning-dim {
        color: #ca8a04;
        background: #241c0f;
    }

    #status_line.status-error {
        color: #ef4444;
        background: #2a0f12;
    }

    #status_line.status-info {
        color: #60a5fa;
        background: #0f1a2e;
    }

    #status_line.status-stake {
        color: #f5d0fe;
        background: #240a38;
    }

    #status_line.status-unstake {
        color: #f5d0fe;
        background: #2a0b3f;
    }

    #status_line.status-stake-dim {
        color: #c084fc;
        background: #14061f;
    }

    #status_line.status-unstake-dim {
        color: #c084fc;
        background: #14061f;
    }

    /* Processing state with yellow glow (breathing effect handled by timer) */
    #bottom_bar.status-processing {
        border: heavy #d97706;
        background: #2a210f;
    }

    #status_line.status-processing {
        color: #f59e0b;
        background: #2a210f;
    }

    #bottom_bar.status-processing-dim {
        border: heavy #b45309;
        background: #241c0f;
    }

    #status_line.status-processing-dim {
        color: #d97706;
        background: #241c0f;
    }
    """

    BINDINGS = [
        # Primary actions
        Binding("s", "send", "Send", show=True),
        Binding("x", "receive", "Receive", show=True),
        Binding("k", "stake", "Stake HQ", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        # Wallet management
        Binding("i", "import_wallet", "Import", show=True),
        Binding("b", "backup", "Backup", show=True),
        Binding("delete", "delete_wallet", "Delete", show=True),
        # Network/config
        Binding("n", "network", "Network", show=True),
        Binding("p", "rpc", "RPC", show=True),
        # Exit
        Binding("q", "quit", "Quit", show=True),
        # Hidden bindings (still work, just not shown in footer)
        Binding("d", "tx_details", "Tx details", show=False),
        Binding("enter", "tx_details", "Tx details", show=False),
        Binding("m", "more_history", "More history", show=False),
        Binding("left", "nav_left", "Left", show=False),
        Binding("right", "nav_right", "Right", show=False),
        Binding("ctrl+r", "toggle_auto_refresh", "Toggle auto-refresh", show=False),
    ]

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Loading messages imported from bakery_messages module
    FUN_LOADING_MESSAGES = SPINNER_MESSAGES

    def __init__(self):
        super().__init__()
        logging.info("Initializing WalletApp")

        # Thread safety: track main thread ID and protect shared state
        self._thread_id: Optional[int] = None  # Set in on_mount
        self._store_lock = RLock()             # Protects self.store
        self._selected_lock = RLock()          # Protects self.selected
        self._history_cache_lock = RLock()     # Protects self.history_cache
        self._balance_cache_lock = RLock()     # Protects self._balance_cache
        self._pending_ops_lock = RLock()       # Protects self._pending_ops

        self.store = load_store()
        stored_rpc = self.store.get("rpc")
        self.rpc, rpc_replaced = _normalize_rpc_runtime(
            stored_rpc,
            fallback=Config.RPC_DEFAULT_GHOSTNET,
        )
        if rpc_replaced:
            self.store["rpc"] = self.rpc
            save_store(self.store)
            log_warning(
                "Invalid RPC in store; reset to safe default",
                invalid_rpc=stored_rpc,
                fallback_rpc=self.rpc,
            )
        logging.info(f"RPC: {self.rpc}")
        self.accounts = list_accounts(self.store)
        logging.info(f"Loaded {len(self.accounts)} account(s)")
        self.selected: Account | None = None
        self._startup_notice: str | None = None
        migration = get_last_migration()
        if migration:
            to_path = migration.get("to", "")
            display_path = to_path
            try:
                display_path = display_path.replace(str(Path.home()), "~")
            except (TypeError, ValueError) as e:
                log_debug("Failed to normalize migration path for startup notice", exception=str(e))
            if display_path:
                self._startup_notice = f"ℹ️ Wallet data moved to {display_path} (legacy kept)."

        self.history_cache: dict[tuple[str, int], list[dict]] = {}
        self.history_items: list[dict] = []
        self.history_selected_index: int | None = None
        self.history_limit: int = Config.HISTORY_DEFAULT_LIMIT
        self._history_keep_index: int | None = None
        self._history_notice: str | None = None
        self._history_requested_more: bool = False
        self._history_exhausted: dict[str, bool] = {}
        self._last_selected_addr: str | None = None
        self._history_loaded_addr: str | None = None
        self._stake_wallet_info_cache: dict[str, dict] = {}
        pending_list = self.store.get("pending_ops", [])
        if isinstance(pending_list, list):
            self._pending_ops = {
                str(item.get("hash")): self._coerce_pending_item(item)
                for item in pending_list
                if isinstance(item, dict) and item.get("hash")
            }
        else:
            self._pending_ops = {}

        # Operation entrypoint overrides (hash -> entrypoint).
        # Used to preserve custom semantics (e.g. "change_baker" is a delegation under the hood,
        # but should remain labeled as "CH / BAKER CHANGED" in history even after refresh).
        raw_overrides = self.store.get("op_entrypoint_overrides", {})
        if isinstance(raw_overrides, dict):
            self._op_entrypoint_overrides: dict[str, str] = {
                str(k): str(v)
                for k, v in raw_overrides.items()
                if k and isinstance(k, str) and v and isinstance(v, str)
            }
        else:
            self._op_entrypoint_overrides = {}
        self._pending_shimmer_i: int = 0
        self._pending_shimmer_timer = None

        # Balance cache: address -> (balance_mutez, timestamp)
        self._balance_cache: dict[str, tuple[int, float]] = {}

        # Auto-refresh
        self._auto_refresh_enabled = self.store.get("auto_refresh_enabled", False)
        self._auto_refresh_timer = None

        self._spin_msg: str | None = None

        # Staking message cache (persists until next refresh)
        self._staking_message: str = ""
        # Balance tier message cache (persists until next refresh)
        self._balance_message: str = ""
        # Empty wallet message cache (selected once on startup)
        self._empty_wallet_message: str = get_empty_wallet_message()
        self._spin_i: int = 0
        self._spin_timer = None
        self._spin_start_time: float = 0.0

        # Breathing effect state for transaction processing
        self._breathing_active: bool = False
        self._breathing_bright: bool = True
        self._breathing_timer = None

        self._price_timer = None
        self._price_initial_timer = None
        self._price_usd: float | None = None

        self._rpc_pulse_timer = None
        self._rpc_pulse_i: int = 0
        self._rpc_short: str = ""
        self._rpc_online: bool = True

        # Subtle loading animation for account rows
        self._loading_accounts: set[str] = set()
        self._loading_anim_i: int = 0
        self._loading_anim_timer = None

        self._last_status: str = ""
        self._status_lock_until_refresh: bool = False
        self._size_warned: bool = False

        self._send_in_progress: bool = False
        self._send_in_progress_token: float | None = None
        self._tx_watchdog_token: float | None = None
        self._tx_watchdog_action: str | None = None
        self._tx_watchdog_timer = None
        self._tx_watchdog_notice_timer = None
        self._stake_flow_in_progress: bool = False
        self._stake_button_cooldown_until: float = 0.0

        self._copy_blink_timer = None
        self._copy_blink_active = False
        self._copy_blink_i = 0
        self._copy_blink_addr = ""

        # One-time hardening for existing local backup artifacts.
        try:
            ensure_private_files_in_dir(Path("data/backups"), suffixes=(".json",))
        except _LOCAL_IO_EXCEPTIONS as e:
            log_warning("Failed to harden backup file permissions", exception=e)

        # Migrate from old global recent_to to per-wallet recent_to_by_wallet
        if "recent_to_by_wallet" not in self.store:
            # Initialize new structure
            self.store["recent_to_by_wallet"] = {}
            # Migrate old data if it exists (assign to all wallets for backwards compatibility)
            old_recent = self.store.get("recent_to", [])
            if isinstance(old_recent, list) and old_recent:
                for acc in self.accounts:
                    self.store["recent_to_by_wallet"][acc.address] = list(old_recent)
            save_store(self.store)

        self.recent_to_by_wallet: dict[str, list[str]] = self.store.get("recent_to_by_wallet", {})

    def compose(self) -> ComposeResult:
        # ASCII logo banner (plain text, no special formatting)
        logo = load_ascii_logo()
        with Vertical(id="main_content"):
            yield Static(logo, id="banner")

            with Vertical():
                # Accounts section with action buttons
                with Horizontal(id="accounts_header"):
                    yield Button("Import (i)", id="add")
                    yield Button("Backup (b)", id="backup")
                    yield Button("Delete (Del)", id="delete")
                    yield Button("Exit", id="exit")
                    yield Static("💅 A wallet with an attitude", id="tagline")
                # Column headers for wallet list (aligned with fixed column widths)
                header = f"{'#':<2} {'Wallet':<23}│ Address"
                yield Static(f"[b]{header}[/b]", id="accounts_columns_header", markup=True)
                yield ListView(id="accounts")

                # Selected wallet details
                with Vertical(id="wallet_details"):
                    yield Static("", id="wallet_status", markup=True)
                    yield Static("", id="wallet_balance", markup=True)
                    yield Static("", id="wallet_delegation", markup=True)
                    yield Static("", id="wallet_staking", markup=True)
                    yield Static("", id="wallet_network", markup=True)

                # Action buttons
                with Horizontal(id="action_buttons"):
                    yield Button("Send (s)", id="send")
                    yield Button("Receive (x)", id="recv")
                    yield Button("Stake HQ (k)", id="stake")
                    yield Button("Refresh (r)", id="refresh")

                # Recent Transactions section with split view
                yield Static(
                    self._history_title_text(),
                    id="hist_title",
                    markup=True,
                )
                # Column headers for both panels with fixed widths matching content
                with Horizontal(id="history_headers"):
                    # Fixed widths: #=3, Time=12, Type=4, Amount=15, Destination=23, Status=10
                    header_line = f"{'#':<3} {'Time':<12}  {'Type':<4}  {'Amount':<15}  {'Destination':<23}  {'Status':<10}"
                    yield Static(header_line, id="history_header", markup=True)
                    yield Static("[b]More info[/b]", id="tx_detail_header", markup=True)
                with Horizontal(id="history_split"):
                    yield ListView(id="history")
                    with Vertical(id="tx_detail_pane"):
                        yield Static("Select a transaction to view details", id="tx_detail_content", markup=True)

                # RPC indicator at bottom
                with Horizontal(id="bottom_bar"):
                    yield Static("🍞 Oven ready!", id="status_line", markup=True)
                    yield Static("", id="tx_link_area", markup=True)
                    yield Static("ꜩ XTZ Price: --", id="price_indicator", markup=True)
                    yield Static("● RPC", id="rpc_indicator", markup=True)

        yield Footer()

    def on_mount(self) -> None:
        # Store the main thread ID for thread safety checks
        self._thread_id = threading.get_ident()

        self._update_rpc_indicator()
        self._start_rpc_pulse()
        self._start_price_indicator()
        self._render_accounts()
        self._maybe_warn_terminal_size(self.size)
        # Auto-pick an RPC that supports BOTH simulation and injection.
        # Many public RPCs are read-only or restrict sensitive endpoints.
        self._autodetect_rpc()
        if self._startup_notice:
            notice = self._startup_notice
            self._schedule_after(
                0.5,
                lambda n=notice: self._set_status_styled(n, style="info", duration=6.0, force=True),
            )

        # Start auto-refresh if enabled
        if self._auto_refresh_enabled:
            self._start_auto_refresh()

    def on_resize(self, event) -> None:
        try:
            self._maybe_warn_terminal_size(event.size)
        except (AttributeError, TypeError, ValueError) as e:
            log_debug("Failed to handle resize event", exception=str(e))

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to the OS clipboard with CLI fallbacks for TUI environments."""
        last_error: Exception | None = None
        safe_env = dict(os.environ)
        safe_env["PATH"] = os.environ.get("PATH", "")
        for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            if shutil.which(cmd[0]) is None:
                continue
            try:
                # Command argv is a fixed allowlist (no shell, no user-selected executable).
                subprocess.run(
                    cmd,
                    input=text,
                    text=True,
                    check=True,
                    timeout=3,
                    close_fds=True,
                    env=safe_env,
                )  # nosec B603
                return
            except (subprocess.SubprocessError, OSError, ValueError) as e:
                last_error = e
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(text)
            return
        except (ImportError, RuntimeError, AttributeError, OSError, ValueError) as e:
            last_error = e
        try:
            super().copy_to_clipboard(text)
            return
        except (RuntimeError, AttributeError, OSError) as e:
            last_error = e
        if last_error:
            raise last_error

    def _maybe_warn_terminal_size(self, size) -> None:
        if self._size_warned or self._status_lock_until_refresh:
            return
        try:
            width = getattr(size, "width", 0)
            height = getattr(size, "height", 0)
        except (AttributeError, TypeError):
            return
        if width < 120 or height < 35:
            if not self._last_status:
                self._set_status("ℹ️ Tip: best at 120x35 for full history view.")
            self._size_warned = True

    def on_unmount(self) -> None:
        """Cleanup timers on app close."""
        if self._spin_timer:
            self._spin_timer.stop()
            self._spin_timer = None

        if self._auto_refresh_timer:
            self._auto_refresh_timer.stop()
            self._auto_refresh_timer = None
        if self._price_timer:
            self._price_timer.stop()
            self._price_timer = None
        if self._price_initial_timer:
            self._price_initial_timer.stop()
            self._price_initial_timer = None
        if self._copy_blink_timer:
            self._copy_blink_timer.stop()
            self._copy_blink_timer = None

        log_info("WalletApp unmounted, timers cleaned up")

    def on_key(self, event) -> None:
        """Handle key events at App level.

        CRITICAL: Block app-level keybindings when a modal is open.
        This prevents actions from firing behind the modal.
        """
        if isinstance(self.screen, ModalScreen):
            key = getattr(event, "key", None)
            if _move_focus_in_button_row(self.focused, key, include_hidden=False, require_visible=True):
                event.stop()
                return
            event.stop()
            return
        # If no modal, let normal key handling proceed (bindings, etc.)

        key = getattr(event, "key", None)
        if key == "down" and self.focused is None:
            try:
                self.query_one("#add", Button).focus()
            except _UI_QUERY_EXCEPTIONS as e:
                log_debug("Failed to focus add button from keyboard", exception=str(e))
            event.stop()
            return
        if key == "up" and self.focused is None:
            try:
                self.query_one("#send", Button).focus()
            except _UI_QUERY_EXCEPTIONS as e:
                log_debug("Failed to focus send button from keyboard", exception=str(e))
            event.stop()
            return
        if key == "enter" and isinstance(self.focused, ListView):
            lv = self.focused
            if getattr(lv, "id", None) == "accounts":
                idx = lv.index
                if idx is not None and 0 <= idx < len(self.accounts):
                    if (
                        self._last_selected_addr == self.accounts[idx].address
                        and self._history_loaded_addr == self.accounts[idx].address
                        and self.history_items
                    ):
                        event.stop()
                        return
                    self._apply_account_selection(idx)
                    event.stop()
                    return
            if getattr(lv, "id", None) == "history":
                idx = lv.index
                if idx is not None and idx >= len(self.history_items) and not self._history_notice:
                    self.action_more_history()
                    event.stop()
                    return
        if key == "c" and isinstance(self.focused, ListView):
            lv = self.focused
            if getattr(lv, "id", None) == "accounts":
                idx = lv.index
                if idx is not None and 0 <= idx < len(self.accounts):
                    addr = self.accounts[idx].address
                    try:
                        self.copy_to_clipboard(addr)
                        self._start_copy_blink(addr)
                    except (RuntimeError, OSError, ValueError, ImportError) as e:
                        log_warning("Clipboard copy failed", exception=e, address=addr)
                        self._set_status(f"❌ Copy failed. Address: {addr}")
                    event.stop()
                    return
        if key in ("up", "down") and isinstance(self.focused, ListView):
            lv = self.focused
            idx = lv.index
            if idx is None and len(lv.children) > 0:
                lv.index = 0
                event.stop()
                return
            if idx is not None:
                n = len(lv.children)
                if n > 0:
                    if getattr(lv, "id", None) == "history" and n <= 1:
                        self._focus_action_buttons()
                        event.stop()
                        return
                    if key == "down" and getattr(lv, "id", None) == "history" and idx >= n - 1:
                        self._focus_accounts_header()
                        event.stop()
                        return
                    if key == "up" and getattr(lv, "id", None) == "history" and idx <= 0:
                        self._focus_action_buttons()
                        event.stop()
                        return
                    if key == "up" and idx <= 0:
                        self._focus_out_of_row(direction="prev")
                        event.stop()
                        return
                    if key == "down" and idx >= n - 1:
                        if getattr(lv, "id", None) == "accounts":
                            self._focus_wallet_buttons()
                        else:
                            self._focus_out_of_row(direction="next")
                        event.stop()
                        return
        if key == "escape":
            if self.focused is not None:
                try:
                    self.set_focus(None)
                except _UI_CALLBACK_EXCEPTIONS as e:
                    log_debug("Failed to clear focus on escape", exception=str(e))
                event.stop()
                return
            self.action_quit()
            event.stop()
        if key == "up" and not isinstance(self.focused, ListView):
            self.action_nav_up()
            event.stop()
            return
        if key == "down" and not isinstance(self.focused, ListView):
            self.action_nav_down()
            event.stop()
            return

    @on(MouseDown, "#bottom_bar")
    @on(MouseDown, "#price_indicator")
    @on(MouseDown, "#rpc_indicator")
    def _stop_bottom_bar_mouse_down(self, event: MouseDown) -> None:
        """Prevent clicks from shifting focus or causing flicker."""
        event.stop()

    @on(MouseUp, "#bottom_bar")
    @on(MouseUp, "#price_indicator")
    @on(MouseUp, "#rpc_indicator")
    def _stop_bottom_bar_mouse_up(self, event: MouseUp) -> None:
        """Ignore mouse-up events on the bottom bar area."""
        event.stop()

    @on(MouseDown, "#accounts ListItem")
    def _accounts_item_mouse_down(self, event: MouseDown) -> None:
        item = event.widget
        width = getattr(item.size, "width", 0) or 0
        if event.button != 1 or event.x < max(0, width - 3):
            return
        lv = self.query_one("#accounts", ListView)
        items = list(lv.children)
        try:
            idx = items.index(item)
        except ValueError:
            return
        if not (0 <= idx < len(self.accounts)):
            return
        addr = self.accounts[idx].address
        try:
            self.copy_to_clipboard(addr)
            self._start_copy_blink(addr)
        except (RuntimeError, OSError, ValueError, ImportError) as e:
            log_warning("Clipboard copy failed", exception=e, address=addr)
            self._set_status(f"❌ Copy failed. Address: {addr}")
        event.stop()

    @on(Button.Pressed, ".copy_addr")
    def _copy_addr_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if not btn_id.startswith("copy_addr_"):
            return
        try:
            idx = int(btn_id.rsplit("_", 1)[1])
        except ValueError:
            return
        if not (0 <= idx < len(self.accounts)):
            return
        addr = self.accounts[idx].address
        try:
            self.copy_to_clipboard(addr)
            self._start_copy_blink(addr)
        except (RuntimeError, OSError, ValueError, ImportError) as e:
            log_warning("Clipboard copy failed", exception=e, address=addr)
            self._set_status(f"❌ Copy failed. Address: {addr}")
        event.stop()

    # -------------------------
    # Thread-safe accessors
    # -------------------------
    def _get_selected(self) -> Optional[Account]:
        """Thread-safe getter for self.selected."""
        with self._selected_lock:
            return self.selected

    def _set_selected(self, account: Optional[Account]) -> None:
        """Thread-safe setter for self.selected."""
        with self._selected_lock:
            self.selected = account

    @work(exclusive=True, thread=True)
    def _autodetect_rpc(self) -> None:
        """Detect and switch to a working RPC (supports injection + simulation).

        Runs in a worker thread (network I/O).
        """
        current = self.rpc
        self._ui(self._set_status, get_message("rpc_checking"))

        best, can_send, can_sim = choose_working_rpc(current)

        if best != current:
            self.rpc = best
            self.store["rpc"] = self.rpc
            save_store(self.store)
            self._ui(self._update_rpc_indicator)

            # History & balances depend on the RPC; refresh caches.
            self._invalidate_history_cache()
            self.history_limit = Config.HISTORY_DEFAULT_LIMIT
            self._ui(self._update_history_title)

        if can_send and can_sim:
            msg = get_message("rpc_hot")
        elif can_send and not can_sim:
            msg = get_message("rpc_warm")
        else:
            msg = get_message("rpc_display")

        self._ui(self._set_status, msg)

    def _ensure_working_rpc(self) -> tuple[str, bool, bool]:
        """Ensure the current RPC is usable for injection (and ideally simulation)."""
        current = self.rpc
        best, can_send, can_sim = choose_working_rpc(current)

        if best != current:
            self.rpc = best
            self.store["rpc"] = self.rpc
            save_store(self.store)
            self._ui(self._update_rpc_indicator)

            # History & balances depend on the RPC; refresh caches.
            self._invalidate_history_cache()
            self.history_limit = Config.HISTORY_DEFAULT_LIMIT
            self._ui(self._update_history_title)

            log_warning("RPC switched for action", from_rpc=current, to_rpc=best)

        if not can_send:
            log_warning("No RPC available with injection support", current_rpc=self.rpc)

        return best, can_send, can_sim

    def _tx_flow_remaining(self, start_ts: float) -> float:
        """Return remaining seconds to honor the standardized tx flow duration."""
        return max(0.0, (start_ts + Config.TX_FLOW_TOTAL_SECONDS) - time.time())

    def _tx_flow_remaining_or_default(self, start_ts: float) -> float:
        """Return remaining tx flow time or fallback to the default flow duration."""
        remaining = self._tx_flow_remaining(start_ts)
        return remaining if remaining > 0.1 else Config.TX_FLOW_TOTAL_SECONDS

    def _schedule_after(self, delay_seconds: float, fn: Callable[[], None]) -> None:
        if delay_seconds <= 0:
            fn()
            return
        self.set_timer(delay_seconds, fn)

    def _start_price_indicator(self) -> None:
        if self._price_timer is None:
            self._price_timer = self.set_interval(Config.PRICE_REFRESH_SECONDS, self._request_price_refresh)
        if self._price_initial_timer is None:
            self._price_initial_timer = self.set_timer(
                Config.PRICE_INITIAL_DELAY_SECONDS,
                self._request_price_refresh,
            )

    def _request_price_refresh(self) -> None:
        self.run_worker(self._fetch_price_worker, exclusive=False, thread=True)

    def _fetch_price_worker(self) -> None:
        price = _fetch_xtz_price_usd()
        self._ui(self._apply_price, price)

    def _apply_price(self, price: Optional[float]) -> None:
        self._price_usd = price
        if price is None:
            text = "ꜩ XTZ Price: --"
        else:
            text = f"ꜩ XTZ Price: ${price:,.2f}"
        try:
            self.query_one("#price_indicator", Static).update(text)
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update price indicator", exception=e)

    def _start_rpc_pulse(self) -> None:
        if self._rpc_pulse_timer is None:
            self._rpc_pulse_timer = self.set_interval(0.6, self._tick_rpc_pulse)
        self._render_rpc_indicator()

    def _tick_rpc_pulse(self) -> None:
        if self._rpc_pulse_timer is None:
            return
        self._rpc_pulse_i += 1
        self._render_rpc_indicator()

    def _render_rpc_indicator(self) -> None:
        try:
            if self._rpc_online:
                blink = (self._rpc_pulse_i % 2) == 0
                dot = "[#34d399]●[/#34d399]" if blink else "[#22c55e]●[/#22c55e]"
            else:
                dot = "[red]●[/red]"
            self.query_one("#rpc_indicator", Static).update(f"{dot} {self._rpc_short or 'RPC'}")
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update RPC indicator", exception=e)

    def _with_rpc_fallback(
        self,
        *,
        action: str,
        rpc: str,
        fn: Callable[[str], Any],
        source_address: Optional[str] = None,
        require_stake_support: bool = False,
    ) -> tuple[str, Any]:
        """Retry an action on a different RPC when we hit stale-branch errors."""
        try:
            return rpc, fn(rpc)
        except _FLOW_TASK_EXCEPTIONS as e:
            if not is_stale_branch_error(e):
                raise
            log_warning("Stale branch detected, attempting RPC fallback", action=action, error=str(e))
            if require_stake_support and source_address:
                new_rpc, can_send, _, can_stake = self._ensure_working_rpc_for_stake(source_address)
                if not can_send:
                    raise
                if not can_stake:
                    log_warning(
                        "Stake support probe failed during stale-branch fallback; retrying anyway",
                        action=action,
                        source_address=source_address,
                        rpc=new_rpc,
                    )
            else:
                new_rpc, can_send, _ = self._ensure_working_rpc()
                if not can_send:
                    raise
            if new_rpc == rpc:
                raise
            return new_rpc, fn(new_rpc)

    def _ensure_working_rpc_for_stake(self, source_address: str) -> tuple[str, bool, bool, bool]:
        """Ensure the current RPC supports stake operations; fallback if needed."""
        current = self.rpc
        net = network_from_rpc(current)
        candidates = _MAINNET_RPC_CANDIDATES if net == "mainnet" else _GHOSTNET_RPC_CANDIDATES
        ordered = [current] + [c for c in candidates if c != current]

        for rpc in ordered:
            if not rpc_supports_send(rpc):
                continue
            if not rpc_supports_stake(rpc, source_address):
                continue
            can_sim = rpc_supports_simulation(rpc)
            if rpc != current:
                self.rpc = rpc
                self.store["rpc"] = self.rpc
                save_store(self.store)
                self._ui(self._update_rpc_indicator)
                self._invalidate_history_cache()
                self.history_limit = Config.HISTORY_DEFAULT_LIMIT
                self._ui(self._update_history_title)
                log_warning("RPC switched for stake action", from_rpc=current, to_rpc=rpc)
            return rpc, True, can_sim, True

        can_send = rpc_supports_send(current)
        can_sim = rpc_supports_simulation(current)
        return current, can_send, can_sim, False

    # -------------------------
    # Thread-safe UI bridge
    # -------------------------
    def _ui(self, fn: Callable, *args, **kwargs):
        try:
            app_tid = getattr(self, "_thread_id", None)
            if app_tid is not None and threading.get_ident() == app_tid:
                return fn(*args, **kwargs)
        except (AttributeError, RuntimeError, TypeError) as e:
            log_error("Failed to check thread ID in _ui", exception=e)
        try:
            return self.call_from_thread(fn, *args, **kwargs)
        except RuntimeError as e:
            # Late callbacks may fire while the app is shutting down.
            if "app is not running" in str(e).lower():
                log_debug("Skipping late UI callback because app is not running", exception=str(e))
                return None
            raise

    # -------------------------
    # Spinner
    # -------------------------
    def _start_spinner(self, msg: str) -> None:
        self._spin_msg = msg
        self._spin_i = 0
        self._spin_start_time = time.time()
        if self._spin_timer is None:
            self._spin_timer = self.set_interval(Config.SPINNER_INTERVAL, self._tick_spinner)
        self._tick_spinner()

    def _stop_spinner(self) -> None:
        self._spin_msg = None
        self._spin_i = 0
        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None
        # Don't reset status - let each action set its own final message

    def _tick_spinner(self) -> None:
        if not self._spin_msg:
            return
        frame = self.SPINNER_FRAMES[self._spin_i % len(self.SPINNER_FRAMES)]

        # Calculate elapsed time
        elapsed = time.time() - self._spin_start_time
        elapsed_seconds = int(elapsed)

        # Show fun message every N ticks - slower for readability
        if self._spin_i > 0 and self._spin_i % Config.FUN_MESSAGE_INTERVAL == 0:
            fun_idx = (self._spin_i // Config.FUN_MESSAGE_INTERVAL) % len(self.FUN_LOADING_MESSAGES)
            msg = self.FUN_LOADING_MESSAGES[fun_idx]
        else:
            msg = self._spin_msg

        # Add elapsed time indicator if operation is taking longer than 5 seconds
        if elapsed_seconds >= 5:
            msg = f"{msg} [dim](⏱️ {elapsed_seconds}s)[/dim]"

        # Blinking effect - slower, more visible
        blink = (self._spin_i // Config.BLINK_INTERVAL) % 2 == 0
        if blink:
            display = f"[reverse]{frame}[/reverse] [b]{msg}[/b]"
        else:
            display = f"{frame} {msg}"

        self._spin_i += 1
        try:
            self.query_one("#status_line", Static).update(display)
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update spinner display", exception=e)

    # -------------------------
    # Balance cache helpers
    # -------------------------
    def _get_cached_balance(self, address: str) -> Optional[int]:
        """Get cached balance if still valid, None otherwise."""
        with self._balance_cache_lock:
            if address not in self._balance_cache:
                return None

            balance, timestamp = self._balance_cache[address]
            elapsed = time.time() - timestamp

            if elapsed < Config.BALANCE_CACHE_SECONDS:
                return balance

            # Cache expired, remove it
            del self._balance_cache[address]
            return None

    def _cache_balance(self, address: str, balance: int) -> None:
        """Cache a balance with current timestamp."""
        with self._balance_cache_lock:
            self._balance_cache[address] = (balance, time.time())
            logging.debug(f"Cached balance for {address}: {balance} mutez")

    def _invalidate_balance_cache(self, address: Optional[str] = None) -> None:
        """Invalidate balance cache for specific address or all addresses."""
        with self._balance_cache_lock:
            if address:
                self._balance_cache.pop(address, None)
                logging.debug(f"Invalidated balance cache for {address}")
            else:
                self._balance_cache.clear()
                logging.debug("Invalidated all balance caches")

    # -------------------------
    # UI helpers
    # -------------------------
    def _set_status(self, text: str, *, force: bool = False) -> None:
        """Update status message (for general messages).

        Args:
            text: Status message to display (stays visible until next action)
            force: Allow update even if status is locked
        """
        if self._status_lock_until_refresh and not force:
            return
        if self._is_error_status(text):
            self._set_status_styled(text, style="error", duration=0.0, force=force)
            return
        self._last_status = text
        # Status messages shown in status_line
        try:
            self.query_one("#status_line", Static).update(text)
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update status line", exception=e)

    def _set_status_styled(self, text: str, style: str = "default", duration: float = 4.0, *, force: bool = False) -> None:
        """Update status message with visual styling (success/warning/error/info).

        Args:
            text: Status message to display
            style: One of "success", "warning", "error", "info", or "default"
            duration: How long to show the styled state (seconds) before reverting to default
            force: Allow update even if status is locked
        """
        if self._status_lock_until_refresh and not force:
            return
        self._last_status = text
        if style != "error" and self._is_error_status(text):
            style = "error"

        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            # Update text
            status_widget.update(text)

            # Remove all status classes first
            for cls in _STATUS_STYLE_CLASSES:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

            # Add new style class if not default
            if style != "default":
                style_class = f"status-{style}"
                status_widget.add_class(style_class)
                bottom_bar.add_class(style_class)

                # Schedule revert to default after duration
                if duration > 0:
                    self.set_timer(duration, lambda: self._revert_status_style())

        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to set styled status", exception=e)

    def _revert_status_style(self) -> None:
        """Revert status bar to default styling."""
        if self._status_lock_until_refresh:
            return
        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            for cls in _STATUS_STYLE_CLASSES:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to revert status style", exception=e)

    @staticmethod
    def _is_error_status(text: str) -> bool:
        if not text:
            return False
        if "❌" in text:
            return True
        lowered = text.lower()
        if "[red]" in lowered:
            return True
        error_hints = (
            "error",
            "failed",
            "invalid",
            "mismatch",
            "not found",
            "no rpc",
            "cannot",
            "unable",
            "denied",
        )
        return any(hint in lowered for hint in error_hints)

    def _set_status_styled_locked(self, text: str, style: str) -> None:
        """Set a styled status that stays until refresh."""
        self._status_lock_until_refresh = True
        self._set_status_styled(text, style=style, duration=0.0, force=True)

    def _stop_timer_attr(self, attr_name: str, *, debug_message: str) -> None:
        """Stop a timer attribute safely and clear it."""
        timer = getattr(self, attr_name, None)
        if not timer:
            return
        try:
            timer.stop()
        except _UI_CALLBACK_EXCEPTIONS as e:
            log_debug(debug_message, exception=str(e))
        setattr(self, attr_name, None)

    def _send_failsafe(self, token: float, address: str) -> None:
        if not self._send_in_progress or self._send_in_progress_token != token:
            return
        log_warning("Send failsafe triggered; releasing send lock", address=address)
        self._send_in_progress = False
        self._send_in_progress_token = None
        try:
            self._stop_breathing_effect()
            self._clear_account_loading(address)
            self._refresh_account_row(address)
            self._set_busy(False)
            self._set_status("⚠️ Send stalled — oven cooling. Try again in 1-2 min.", force=True)
        except _UI_CALLBACK_EXCEPTIONS as e:
            log_warning("Failed to apply send failsafe cleanup", exception=e, address=address)

    def _start_tx_watchdog(self, action: str, address: str) -> float:
        token = time.time()
        self._tx_watchdog_token = token
        self._tx_watchdog_action = action
        self._stop_timer_attr("_tx_watchdog_timer", debug_message="Failed to stop tx watchdog timer")
        self._stop_timer_attr(
            "_tx_watchdog_notice_timer",
            debug_message="Failed to stop tx watchdog notice timer",
        )
        self._tx_watchdog_notice_timer = self.set_timer(
            Config.TX_RPC_TIMEOUT_SECONDS,
            lambda: self._tx_watchdog_notice(token, action, address),
        )
        self._tx_watchdog_timer = self.set_timer(
            Config.TX_RPC_HARD_TIMEOUT_SECONDS,
            lambda: self._tx_watchdog_fire(token, action, address),
        )
        return token

    def _stop_tx_watchdog(self, token: float) -> None:
        if self._tx_watchdog_token != token:
            return
        self._tx_watchdog_token = None
        self._tx_watchdog_action = None
        self._stop_timer_attr("_tx_watchdog_timer", debug_message="Failed to stop tx watchdog timer")
        self._stop_timer_attr(
            "_tx_watchdog_notice_timer",
            debug_message="Failed to stop tx watchdog notice timer",
        )

    def _tx_watchdog_message(self, action: str, *, timed_out: bool) -> str:
        base = {
            "stake": "Stake",
            "unstake": "Unstake",
            "delegate": "Delegation",
            "change_baker": "Change baker",
        }.get(action, "Transaction")
        if timed_out:
            return f"⏳ {base} timed out - check history; retry in 1-2 min if no op."
        return f"⏳ {base} is taking longer than usual… still working."

    def _tx_watchdog_notice(self, token: float, action: str, address: str) -> None:
        if self._tx_watchdog_token != token:
            return
        # Soft timeout: keep the breathing effect, just update the message.
        try:
            self._set_status(self._tx_watchdog_message(action, timed_out=False), force=True)
        except _UI_CALLBACK_EXCEPTIONS as e:
            log_warning("Failed to apply tx watchdog notice", exception=e, action=action, address=address)

    def _tx_watchdog_fire(self, token: float, action: str, address: str) -> None:
        if self._tx_watchdog_token != token:
            return
        self._tx_watchdog_token = None
        self._tx_watchdog_action = None
        self._stop_timer_attr("_tx_watchdog_timer", debug_message="Failed to stop tx watchdog timer")
        self._stop_timer_attr(
            "_tx_watchdog_notice_timer",
            debug_message="Failed to stop tx watchdog notice timer",
        )
        log_warning("TX watchdog triggered", action=action, address=address)
        try:
            self._stop_breathing_effect()
            self._set_busy(False)
            self._status_lock_until_refresh = False
            self._set_status_styled(
                self._tx_watchdog_message(action, timed_out=True),
                style="error",
                duration=6.0,
                force=True,
            )
            if address:
                self._schedule_after(60.0, lambda: self._silent_refresh_history_for(address))
        except _UI_CALLBACK_EXCEPTIONS as e:
            log_warning("Failed to apply tx watchdog cleanup", exception=e, action=action, address=address)

    def _tx_finalize_failsafe(self, action: str, address: str) -> None:
        """Stop lingering tx visuals if a finalize callback never executed."""
        # Even if breathing already stopped (e.g. success status rendered),
        # the status lock may still be active and must be released.
        if not self._breathing_active and not self._status_lock_until_refresh:
            return
        log_warning("TX finalize failsafe triggered", action=action, address=address)
        if self._breathing_active:
            self._stop_breathing_effect()
        self._set_busy(False)
        self._status_lock_until_refresh = False
        if address:
            self._schedule_after(0.0, lambda: self._silent_refresh_history_for(address))

    def _set_pending_counterparty(self, oph: str, address: str, counterparty: str) -> None:
        """Update a pending item's counterparty label (e.g. resolve 'The baker' -> tz1...)."""
        counterparty = (counterparty or "").strip()
        if not counterparty:
            return
        with self._pending_ops_lock:
            pending = self._pending_ops.get(oph)
            if not pending or pending.get("address") != address:
                return
            pending["counterparty"] = counterparty
            self._persist_pending_ops()
        self._update_history_row_for_pending(oph, address)

    def _resolve_delegate_for_pending(self, oph: str, address: str) -> None:
        """Resolve the current delegate (baker) address and update the pending row."""
        try:
            baker_addr = get_delegation_info(self.rpc, address)
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_warning("Failed to resolve delegate baker for pending row", exception=e, address=address, oph=oph)
            return
        if baker_addr:
            try:
                label = self._format_baker_label(baker_addr)
            except _FLOW_PRECHECK_EXCEPTIONS as e:
                log_warning("Failed to format delegate baker label", exception=e, baker_addr=baker_addr, oph=oph)
                label = baker_addr
            label = self._shorten_baker_label(label)
            self._ui(self._set_pending_counterparty, oph, address, label)

    def _start_copy_blink(self, address: str) -> None:
        self._status_lock_until_refresh = False
        if self._copy_blink_timer:
            self._copy_blink_timer.stop()
        self._copy_blink_active = True
        self._copy_blink_i = 0
        self._copy_blink_addr = address
        self._tick_copy_blink()

    def _tick_copy_blink(self) -> None:
        if not self._copy_blink_active:
            return
        if self._status_lock_until_refresh:
            self._status_lock_until_refresh = False
        blink_on = (self._copy_blink_i % 2) == 0
        icon = "⧉" if blink_on else "[dim]⧉[/dim]"
        self._set_status(f"✅ Address copied {icon}")
        self._copy_blink_i += 1
        if self._copy_blink_i >= 6:
            self._copy_blink_active = False
            self._set_status(f"✅ Address copied: {self._copy_blink_addr}")
            return
        self._copy_blink_timer = self.set_timer(
            Config.STATUS_BLINK_INTERVAL_SECONDS,
            self._tick_copy_blink,
        )

    def _start_breathing_effect(
        self,
        text: str,
        bright_class: str = "status-processing",
        dim_class: str = "status-processing-dim",
    ) -> None:
        """Start breathing glow effect for processing state.

        Args:
            text: Status message to display with breathing effect
        """
        # Stop any previous breathing timer before starting a new one
        if hasattr(self, "_breathing_timer") and self._breathing_timer:
            try:
                self._breathing_timer.stop()
            except _UI_CALLBACK_EXCEPTIONS as e:
                log_debug("Failed to stop breathing timer", exception=str(e))
        self._breathing_active = True
        self._breathing_bright = True
        self._breathing_bright_class = bright_class
        self._breathing_dim_class = dim_class
        self._last_status = text

        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            # Update text
            status_widget.update(text)

            # Remove all status classes
            for cls in _STATUS_STYLE_CLASSES:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

            # Start with bright state
            status_widget.add_class(bright_class)
            bottom_bar.add_class(bright_class)

            # Schedule breathing toggle
            self._breathing_timer = self.set_timer(Config.STATUS_BLINK_INTERVAL_SECONDS, self._toggle_breathing)

            if self._pending_shimmer_timer:
                self._pending_shimmer_timer.stop()
                self._pending_shimmer_timer = self.set_interval(
                    Config.STATUS_BLINK_INTERVAL_SECONDS,
                    self._tick_pending_shimmer,
                )
                self._pending_shimmer_i = 0

        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to start breathing effect", exception=e)

    def _toggle_breathing(self) -> None:
        """Toggle between bright and dim states for breathing effect."""
        if not self._breathing_active:
            return

        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            # Toggle state
            self._breathing_bright = not self._breathing_bright

            # Remove current classes
            bright_class = getattr(self, "_breathing_bright_class", "status-processing")
            dim_class = getattr(self, "_breathing_dim_class", "status-processing-dim")

            status_widget.remove_class(bright_class)
            status_widget.remove_class(dim_class)
            bottom_bar.remove_class(bright_class)
            bottom_bar.remove_class(dim_class)

            # Add new classes based on state
            if self._breathing_bright:
                status_widget.add_class(bright_class)
                bottom_bar.add_class(bright_class)
            else:
                status_widget.add_class(dim_class)
                bottom_bar.add_class(dim_class)

            # Schedule next toggle
            self._breathing_timer = self.set_timer(Config.STATUS_BLINK_INTERVAL_SECONDS, self._toggle_breathing)

        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to toggle breathing effect", exception=e)

    def _stop_breathing_effect(self) -> None:
        """Stop breathing effect and revert to default state."""
        self._breathing_active = False

        try:
            # Cancel timer if exists
            if hasattr(self, '_breathing_timer') and self._breathing_timer:
                self._breathing_timer.stop()

            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            # Remove breathing classes
            for cls in _STATUS_STYLE_CLASSES:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to stop breathing effect", exception=e)

    def _set_pending_blink(self, active: bool) -> None:
        if active:
            if not self._pending_shimmer_timer:
                self._pending_shimmer_i = 0
                self._pending_shimmer_timer = self.set_interval(
                    Config.STATUS_BLINK_INTERVAL_SECONDS,
                    self._tick_pending_shimmer,
                )
            if self._breathing_active:
                if self._breathing_timer:
                    self._breathing_timer.stop()
                self._breathing_bright = True
                try:
                    status_widget = self.query_one("#status_line", Static)
                    bottom_bar = self.query_one("#bottom_bar", Horizontal)
                    bright_class = getattr(self, "_breathing_bright_class", "status-processing")
                    dim_class = getattr(self, "_breathing_dim_class", "status-processing-dim")
                    status_widget.remove_class(dim_class)
                    bottom_bar.remove_class(dim_class)
                    status_widget.add_class(bright_class)
                    bottom_bar.add_class(bright_class)
                except _UI_QUERY_EXCEPTIONS as e:
                    log_debug("Failed to apply breathing classes for pending shimmer", exception=str(e))
                self._breathing_timer = self.set_timer(
                    Config.STATUS_BLINK_INTERVAL_SECONDS,
                    self._toggle_breathing,
                )
        else:
            if self._pending_shimmer_timer:
                try:
                    self._pending_shimmer_timer.stop()
                except _UI_QUERY_EXCEPTIONS as e:
                    log_debug("Failed to stop pending shimmer timer", exception=str(e))
                self._pending_shimmer_timer = None
            self._pending_shimmer_i = 0

    def _tick_pending_shimmer(self) -> None:
        if not self._pending_shimmer_timer:
            return
        self._pending_shimmer_i += 1
        if self.history_items:
            self._update_pending_shimmer_rows()

    def _update_pending_shimmer_rows(self) -> None:
        hv = self.query_one("#history", ListView)
        rows = list(hv.children)
        for idx, it in enumerate(self.history_items, start=1):
            status = (it.get("status") or "CONFIRMED").upper()
            if status not in ("PENDING", "PROCESSING"):
                continue
            if idx - 1 >= len(rows):
                break
            item = rows[idx - 1]
            try:
                label = item.query_one(Label)
                label.update(self._format_history_line(idx, it))
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to update pending shimmer row", exception=e)

    def _set_busy(self, busy: bool) -> None:
        for bid in ("#add", "#backup", "#export", "#delete", "#exit", "#refresh", "#send", "#recv", "#stake"):
            # Use query() to check if button exists before accessing
            btns = self.query(bid)
            if btns:
                try:
                    btns.first(Button).disabled = busy
                except _UI_QUERY_EXCEPTIONS as e:
                    log_error("Failed to set button busy state", exception=e, button_id=bid)
        account_lists = self.query("#accounts")
        if account_lists:
            try:
                account_lists.first(ListView).disabled = busy
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to set accounts list busy state", exception=e)

    def _update_rpc_indicator(self) -> None:
        """Update the RPC indicator in bottom-right corner with RPC URL."""
        try:
            # Shorten RPC URL for display
            rpc_short = self.rpc.replace("https://", "").replace("http://", "")
            if len(rpc_short) > 35:
                rpc_short = rpc_short[:32] + "..."

            self._rpc_short = rpc_short
            self._rpc_online = True
            self._render_rpc_indicator()
            self._request_price_refresh()
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update RPC indicator", exception=e)
            try:
                self._rpc_short = "Offline"
                self._rpc_online = False
                self._render_rpc_indicator()
            except _UI_QUERY_EXCEPTIONS as e2:
                log_error("Failed to set RPC indicator to offline", exception=e2)

    def _show_tx_link(self, oph_short: str, tzkt_url: str) -> None:
        """Show transaction hash with link to TzKT explorer.

        Args:
            oph_short: Shortened operation hash for display
            tzkt_url: Full TzKT explorer URL
        """
        try:
            self.query_one("#tx_link_area", Static).update("")
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to clear transaction link", exception=e)

    def _clear_tx_link(self) -> None:
        """Clear the transaction link area."""
        try:
            self.query_one("#tx_link_area", Static).update("")
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to clear transaction link", exception=e)

    def _history_title_text(self, suffix: str = "") -> str:
        """Build the history title with selected wallet context."""
        wallet_name = ""
        if self.selected:
            wallet_name = str(getattr(self.selected, "name", "") or "").strip()
        if wallet_name:
            wallet_name = wallet_name.replace("[", "\\[").replace("]", "\\]")
            return f"[cyan]{wallet_name}[/cyan] · [b]Oven Log[/b] (last {self.history_limit} fresh goodies){suffix}"
        else:
            return f"[dim]no wallet selected[/dim] · [b]Oven Log[/b] (last {self.history_limit} fresh goodies){suffix}"

    def _update_history_title(self, suffix: str = "") -> None:
        self.query_one("#hist_title", Static).update(self._history_title_text(suffix))

    def _update_tx_details(self) -> None:
        """Update the transaction details pane with the selected transaction."""
        try:
            detail_pane = self.query_one("#tx_detail_content", Static)
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to query transaction detail pane", exception=e)
            return

        if not self.history_items or self.history_selected_index is None:
            detail_pane.update("Select a transaction to view details")
            return

        idx = self.history_selected_index
        if idx < 0 or idx >= len(self.history_items):
            if self.selected:
                tzkt_url = f"https://tzkt.io/{self.selected.address}/operations"
                tzkt_link = (
                    f"[u][link=\"{tzkt_url}\"]{tzkt_url}[/link][/u] "
                    "[dim](Shift+Left click)[/dim]"
                )
                detail_pane.update(f"[b]More on TzKT[/b]\n{tzkt_link}")
                return
            detail_pane.update("Invalid selection")
            return

        tx = self.history_items[idx]

        # Extract transaction details
        ts = (tx.get("ts") or "").replace("T", " ").replace("Z", "")
        direction = tx.get("direction") or "?"
        amt: Decimal = tx.get("amount_xtz") or Decimal(0)
        cp = tx.get("counterparty") or "?"
        h = tx.get("hash") or ""
        baker = tx.get("baker") or ""
        kind = tx.get("kind") or ""
        entrypoint = tx.get("entrypoint") or ""
        status = (tx.get("status") or "CONFIRMED").upper()

        # Build TzKT link
        tzkt_base = tzkt_ui_base_from_rpc(self.rpc)
        tzkt_link = f"{tzkt_base}/{h}" if h else ""

        # Get wallet address
        wallet_addr = self.selected.address if self.selected else ""

        # Determine From and To based on direction
        if direction == "IN":
            from_addr = cp
            to_addr = wallet_addr or "Your Wallet"
            amt_label = f"[#34d399]+{format_xtz(amt)} XTZ[/#34d399]"
        elif direction == "OUT":
            from_addr = wallet_addr or "Your Wallet"
            to_addr = cp
            amt_label = f"[red]-{format_xtz(amt)} XTZ[/red]"
        elif direction == "STK":
            from_addr = wallet_addr or "Your Wallet"
            to_addr = wallet_addr or "Your Wallet"
            amt_label = f"[#8b5cf6]-{format_xtz(amt)} XTZ[/#8b5cf6]"
        elif direction == "UST":
            from_addr = wallet_addr or "Your Wallet"
            to_addr = wallet_addr or "Your Wallet"
            amt_label = f"[#8b5cf6]+{format_xtz(amt)} XTZ[/#8b5cf6]"
        elif direction == "DEL":
            from_addr = wallet_addr or "Your Wallet"
            to_addr = cp
            amt_label = f"[yellow]{format_xtz(amt)} XTZ[/yellow]"
        elif direction == "UND":
            from_addr = wallet_addr or "Your Wallet"
            to_addr = "—"
            amt_label = f"[yellow]{format_xtz(amt)} XTZ[/yellow]"
        else:
            from_addr = "?"
            to_addr = "?"
            amt_label = f"{format_xtz(amt)} XTZ"

        # Build details text - single line per field (except Hash and TzKT link)
        lines = [
            f"[b]Date:[/b] {ts}",
            f"[b]Type:[/b] {kind or '-'}",
            f"[b]Status:[/b] {status}",
            f"[b]From:[/b] {from_addr}",
            f"[b]To:[/b] {to_addr}",
            f"[b]Amount:[/b] {amt_label}",
        ]

        if entrypoint:
            lines.extend([
                f"[b]Entrypoint:[/b] {entrypoint}",
            ])

        lines.extend([
            f"[b]Hash:[/b] {h}",
        ])

        if baker:
            lines.extend([
                f"[b]Baker:[/b] {baker}",
            ])

        if tzkt_link:
            lines.extend([
                "[b]TzKT Explorer:[/b]",
                f"  [link=\"{tzkt_link}\"][u]{tzkt_link}[/u][/link] [dim](Shift + Left Click)[/dim]",
            ])

        detail_pane.update("\n".join(lines))

    # -------------------------
    # Global arrows nav
    # -------------------------
    def action_nav_up(self) -> None:
        w = self.focused
        if w is not None and getattr(w.parent, "id", None) == "action_buttons":
            self._focus_accounts_list()
            return
        if w is not None and isinstance(w.parent, Horizontal):
            self._focus_out_of_row(direction="prev")
            return
        if isinstance(w, ListView):
            idx = w.index or 0
            if getattr(w, "id", None) == "accounts" and idx <= 0:
                self._focus_accounts_header()
                return
            if getattr(w, "id", None) == "history":
                n = len(w.children)
                if n <= 1:
                    self._focus_action_buttons()
                    return
                if idx <= 0:
                    self._focus_action_buttons()
                    return
            if idx <= 0:
                self._focus_out_of_row(direction="prev")
            else:
                w.index = idx - 1
            return
        # General focus navigation with up arrow
        self.screen.focus_previous()

    def action_nav_down(self) -> None:
        w = self.focused
        if w is not None and isinstance(w.parent, Horizontal):
            self._focus_out_of_row(direction="next")
            return
        if w is not None and getattr(w, "id", None) == "tx_detail_content":
            try:
                self.query_one("#add", Button).focus()
            except _UI_QUERY_EXCEPTIONS as e:
                log_debug("Failed to focus add button from tx details", exception=str(e))
            return
        if isinstance(w, ListView):
            n = len(w.children)
            if n <= 0:
                return
            idx = w.index or 0
            if getattr(w, "id", None) == "history" and (n <= 1 or idx >= n - 1):
                self._focus_accounts_header()
                return
            if idx >= n - 1:
                self._focus_out_of_row(direction="next")
            else:
                w.index = idx + 1
            return
        # General focus navigation with down arrow
        self.screen.focus_next()

    def action_nav_left(self) -> None:
        """Move focus left in horizontal button rows."""
        w = self.focused
        if w is None:
            return
        if isinstance(w, ListView):
            if getattr(w, "id", None) == "history":
                idx = w.index
                if idx is not None and idx >= len(self.history_items):
                    self._focus_tx_details()
                    return
                try:
                    self._focus_tx_details()
                except _UI_QUERY_EXCEPTIONS:
                    self.screen.focus_previous()
                return
            self.screen.focus_previous()
            return
        if isinstance(w.parent, Horizontal):
            focusables = [c for c in w.parent.children if getattr(c, "can_focus", False)]
            if w in focusables:
                idx = focusables.index(w)
                if idx > 0:
                    focusables[idx - 1].focus()
            return
        self.screen.focus_previous()

    def action_nav_right(self) -> None:
        """Move focus right in horizontal button rows."""
        w = self.focused
        if w is None:
            return
        if isinstance(w, ListView):
            if getattr(w, "id", None) == "history":
                try:
                    self._focus_tx_details()
                except _UI_QUERY_EXCEPTIONS:
                    self.screen.focus_next()
                return
            self.screen.focus_next()
            return
        if isinstance(w.parent, Horizontal):
            focusables = [c for c in w.parent.children if getattr(c, "can_focus", False)]
            if w in focusables:
                idx = focusables.index(w)
                if idx < len(focusables) - 1:
                    focusables[idx + 1].focus()
            return
        self.screen.focus_next()

    def _focus_out_of_row(self, direction: str) -> None:
        """Move focus out of a horizontal row when using up/down."""
        w = self.focused
        if w is None:
            return
        parent = w.parent
        for _ in range(50):
            if direction == "prev":
                self.screen.focus_previous()
            else:
                self.screen.focus_next()
            nxt = self.focused
            if nxt is None or nxt.parent != parent:
                break

    def _focus_wallet_buttons(self) -> None:
        try:
            self.query_one("#send", Button).focus()
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to focus wallet buttons", exception=str(e))

    def _focus_action_buttons(self) -> None:
        try:
            self.query_one("#send", Button).focus()
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to focus action buttons", exception=str(e))

    def _focus_accounts_header(self) -> None:
        try:
            self.query_one("#add", Button).focus()
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to focus accounts header", exception=str(e))

    def _focus_accounts_list(self) -> None:
        try:
            lv = self.query_one("#accounts", ListView)
            if lv.index is None:
                lv.index = 0
            lv.focus()
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to focus accounts list", exception=str(e))

    def _focus_history_list(self) -> None:
        try:
            lv = self.query_one("#history", ListView)
            if lv.index is None:
                lv.index = 0
            lv.focus()
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to focus history list", exception=str(e))

    def _focus_tx_details(self) -> None:
        try:
            self.query_one("#tx_detail_content", Static).focus()
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to focus tx details", exception=str(e))

    # -------------------------
    # Accounts
    # -------------------------
    def _render_accounts(self) -> None:
        lv = self.query_one("#accounts", ListView)
        lv.clear()

        self.accounts = list_accounts(self.store)
        current_addrs = {acc.address for acc in self.accounts}
        self._loading_accounts = {addr for addr in self._loading_accounts if addr in current_addrs}
        if not self._loading_accounts:
            self._stop_loading_anim()

        if not self.accounts:
            self.selected = None
            self._update_status_balance()  # This will clear wallet details
            self._render_history([])
            self._loading_accounts.clear()
            self._stop_loading_anim()
            # Show a fun motivational message from the library
            lv.append(ListItem(Label(f"[yellow]{self._empty_wallet_message}[/yellow]", markup=True)))
            return

        for idx, a in enumerate(self.accounts, start=1):
            tag = " (watch)" if a.enc is None else ""
            name_with_tag = f"{a.name}{tag}"
            marker = self._marker_for_address(a.address)
            name_text = f"{idx:<2} {name_with_tag}"
            row = Horizontal(
                Label(name_text, classes="account_name", markup=True),
                Label("│", classes="account_sep", markup=True),
                Label(a.address, classes="account_address", markup=True),
                Button("⧉", id=f"copy_addr_{idx - 1}", classes="copy_addr"),
                Label(marker, classes="account_marker"),
            )
            lv.append(ListItem(row))

        if self.accounts:
            # Don't auto-select on startup; wait for user intent.
            self.selected = None
            self._last_selected_addr = None
            self._history_loaded_addr = None
            self._update_status_balance()
            self._render_history([])
            lv.focus()

    @on(ListView.Selected)
    def selected_account(self, event: ListView.Selected) -> None:
        return

    @on(ListView.Selected, "#accounts")
    def account_selected_by_click(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        if 0 <= idx < len(self.accounts):
            addr = self.accounts[idx].address
            if self._last_selected_addr == addr and self._history_loaded_addr == addr and self.history_items:
                return
            self._apply_account_selection(idx)

    @on(ListView.Highlighted, "#accounts")
    def account_highlighted(self, event: ListView.Highlighted) -> None:
        return

    def _apply_account_selection(
        self,
        idx: int,
        *,
        refresh_details: bool = True,
        refresh_history: bool = True,
    ) -> None:
        addr = self.accounts[idx].address
        if refresh_history and self._history_loaded_addr != addr:
            self._show_account_loading(idx)
        if self._last_selected_addr != addr:
            prev_addr = self._last_selected_addr
            self.selected = self.accounts[idx]
            self._last_selected_addr = addr
            if refresh_details:
                self._update_status_balance()
            if prev_addr:
                self._refresh_account_row(prev_addr)
        if refresh_history:
            self.call_later(lambda: self._load_history_for_selected(force=True, quiet=True))
            self._update_tx_details()

    def _select_account_by_address(self, address: str) -> None:
        if not address:
            return
        idx = self._account_index_by_address(address)
        if idx is None:
            return
        self._apply_account_selection(idx)

    def _account_index_by_address(self, address: str) -> Optional[int]:
        if not address:
            return None
        return next((i for i, acc in enumerate(self.accounts) if acc.address == address), None)

    def _history_index_by_hash(self, oph: str) -> Optional[int]:
        if not oph:
            return None
        return next((i for i, it in enumerate(self.history_items) if (it.get("hash") or "") == oph), None)

    def _marker_for_address(self, address: str) -> str:
        if address and self._last_selected_addr == address:
            return " 🥐"
        return ""

    def _render_account_row(self, idx: int, *, loading: bool = False, loading_suffix: str | None = None) -> None:
        try:
            lv = self.query_one("#accounts", ListView)
            item = list(lv.children)[idx]
            label = item.query_one(Label)
            marker_label = item.query_one(".account_marker", Label)
            acc = self.accounts[idx]
            tag = " (watch)" if acc.enc is None else ""
            addr_full = acc.address
            name_with_tag = f"{acc.name}{tag}"
            if loading:
                suffix_text = loading_suffix or "Loading..."
                suffix = f"  [dim]{suffix_text}[/dim]"
            else:
                suffix = ""
            marker = self._marker_for_address(acc.address)
            try:
                name_label = item.query_one(".account_name", Label)
                addr_label = item.query_one(".account_address", Label)
                name_label.update(f"{idx + 1:<2} {name_with_tag}")
                addr_label.update(f"{addr_full}{suffix}")
            except _UI_QUERY_EXCEPTIONS as e:
                log_debug(
                    "Failed to update account row labels",
                    exception=str(e),
                    index=idx,
                    address=addr_full,
                )
                label.update(f"{idx + 1:<2} {name_with_tag} │ {addr_full}{suffix}")
            marker_label.update(marker)
        except _UI_QUERY_EXCEPTIONS as e:
            log_debug("Failed to render account row", exception=str(e), index=idx)

    def _show_account_loading(self, idx: int) -> None:
        try:
            addr = self.accounts[idx].address
        except _UI_QUERY_EXCEPTIONS:
            return
        self._loading_accounts.add(addr)
        self._start_loading_anim()
        self._render_account_row(idx, loading=True, loading_suffix=self._current_loading_suffix())

    def _clear_account_loading(self, address: str) -> None:
        self._loading_accounts.discard(address)
        if not self._loading_accounts:
            self._stop_loading_anim()
        idx = self._account_index_by_address(address)
        if idx is None:
            return
        self._render_account_row(idx, loading=False)

    def _refresh_account_row(self, address: str) -> None:
        idx = self._account_index_by_address(address)
        if idx is None:
            return
        loading = address in self._loading_accounts
        self._render_account_row(idx, loading=loading, loading_suffix=self._current_loading_suffix())

    def _current_loading_suffix(self) -> str:
        return shimmer_text("Loading...", self._loading_anim_i, span=2)

    def _start_loading_anim(self) -> None:
        if self._loading_anim_timer is None:
            self._loading_anim_i = 0
            self._loading_anim_timer = self.set_interval(0.4, self._tick_loading_anim)

    def _stop_loading_anim(self) -> None:
        if self._loading_anim_timer is not None:
            self._loading_anim_timer.stop()
            self._loading_anim_timer = None

    def _tick_loading_anim(self) -> None:
        if not self._loading_accounts:
            self._stop_loading_anim()
            return
        self._loading_anim_i += 1
        suffix = self._current_loading_suffix()
        for idx, acc in enumerate(self.accounts):
            if acc.address in self._loading_accounts:
                self._render_account_row(idx, loading=True, loading_suffix=suffix)

    @on(ListView.Selected)
    def selected_history(self, event: ListView.Selected) -> None:
        if event.list_view.id != "history":
            return
        self.history_selected_index = event.list_view.index
        self._update_tx_details()

    @on(ListView.Highlighted)
    def highlighted_history(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "history":
            return
        self.history_selected_index = event.list_view.index
        self._update_tx_details()

    def _update_status_balance(self) -> None:
        if not self.selected:
            # Show labels only with placeholder values
            label_color = "#fdba74"
            self.query_one("#wallet_status", Static).update(
                f"[b][{label_color}]Wallet:[/{label_color}][/b] -"
            )
            self.query_one("#wallet_balance", Static).update(
                f"[b][{label_color}]Balance:[/{label_color}][/b] -"
            )
            self.query_one("#wallet_delegation", Static).update(
                f"[b][{label_color}]Delegation:[/{label_color}][/b] -"
            )
            self.query_one("#wallet_staking", Static).update(
                f"[b][{label_color}]Staking:[/{label_color}][/b] -"
            )
            self.query_one("#wallet_network", Static).update(
                f"[b][{label_color}]Network:[/{label_color}][/b] -"
            )
            return

        label_color = "#fdba74"
        wallet_tag = " [dim](watch-only)[/dim]" if self.selected.enc is None else ""
        self.query_one("#wallet_status", Static).update(
            f"[b][{label_color}]Wallet:[/{label_color}][/b] [b]{self.selected.name}[/b]{wallet_tag}"
        )
        self.query_one("#wallet_balance", Static).update(
            f"[b][{label_color}]Balance:[/{label_color}][/b] [dim]Loading...[/dim]"
        )
        self.query_one("#wallet_delegation", Static).update(
            f"[b][{label_color}]Delegated to:[/{label_color}][/b] [dim]Loading...[/dim]"
        )
        self.query_one("#wallet_staking", Static).update(
            f"[b][{label_color}]Staked Balance:[/{label_color}][/b] [dim]Loading...[/dim]"
        )
        net = network_from_rpc(self.rpc)
        net_label = "Mainnet" if net == "mainnet" else "Ghostnet"
        self.query_one("#wallet_network", Static).update(
            f"[b][{label_color}]Network:[/{label_color}][/b] [#34d399]●[/#34d399] {net_label}"
        )
        self._fetch_selected_status(self.selected.address)

    @work(thread=True)
    def _fetch_selected_status(self, address: str) -> None:
        try:
            cached_balance = self._get_cached_balance(address)
            if cached_balance is not None:
                bal = cached_balance
            else:
                bal = get_balance_mutez(self.rpc, address)
                self._cache_balance(address, bal)

            delegate = get_delegation_info(self.rpc, address)
            staking_bal = get_staking_balance(self.rpc, address)
            baker_info = get_baker_info(self.rpc, delegate) if delegate else None
            self._ui(
                self._apply_selected_status,
                address,
                bal,
                delegate,
                staking_bal,
                baker_info,
            )
        except _FLOW_TASK_EXCEPTIONS as e:
            self._ui(self._apply_selected_status_error, address, str(e))

    def _apply_selected_status(
        self,
        address: str,
        bal: int,
        delegate: Optional[str],
        staking_bal: int,
        baker_info: Optional[dict],
    ) -> None:
        if not self.selected or self.selected.address != address:
            return
        label_color = "#fdba74"
        balance_xtz = mutez_to_xtz(bal)
        is_staking = staking_bal > 0
        is_delegating = delegate is not None
        self._balance_message = get_balance_message(balance_xtz, is_staking, is_delegating)
        self.query_one("#wallet_balance", Static).update(
            f"[b][{label_color}]Balance:[/{label_color}][/b] [b]{format_xtz(balance_xtz)} XTZ[/b] [cyan]{self._balance_message}[/cyan]"
        )

        if delegate:
            if baker_info is not None:
                baker_balance_xtz = mutez_to_xtz(baker_info['balance'])
                commentary_short = get_baker_commentary_short(baker_balance_xtz)
                baker_display = baker_info.get('alias') or delegate
                delegation_text = (
                    f"[b][{label_color}]Delegated to:[/{label_color}][/b] "
                    f"[cyan]{baker_display}[/cyan] - {commentary_short}"
                )
            else:
                delegation_text = f"[b][{label_color}]Delegated to:[/{label_color}][/b] [cyan]{delegate}[/cyan]"
            self.query_one("#wallet_delegation", Static).update(delegation_text)
        else:
            self.query_one("#wallet_delegation", Static).update(
                f"[b][{label_color}]Delegated to:[/{label_color}][/b] [dim]not delegated[/dim]"
            )

        if staking_bal > 0:
            self._staking_message = get_staking_message("chad")
            self.query_one("#wallet_staking", Static).update(
                f"[b][{label_color}]Staked Balance:[/{label_color}][/b] [b]{format_xtz(mutez_to_xtz(staking_bal))} XTZ[/b] [#34d399]{self._staking_message}[/#34d399]"
            )
        elif delegate:
            self._staking_message = get_staking_message("boring")
            self.query_one("#wallet_staking", Static).update(
                f"[b][{label_color}]Staked Balance:[/{label_color}][/b] [dim]-[/dim] [yellow]{self._staking_message}[/yellow]"
            )
        else:
            self._staking_message = get_staking_message("lazy")
            self.query_one("#wallet_staking", Static).update(
                f"[b][{label_color}]Staked Balance:[/{label_color}][/b] [dim]-[/dim] [red]{self._staking_message}[/red]"
            )

    def _apply_selected_status_error(self, address: str, err: str) -> None:
        if not self.selected or self.selected.address != address:
            return
        label_color = "#fdba74"
        self.query_one("#wallet_balance", Static).update(
            f"[b][{label_color}]Balance:[/{label_color}][/b] error: {err}"
        )

    # -------------------------
    # History
    # -------------------------
    def _render_history(self, items: list[dict]) -> None:
        hv = self.query_one("#history", ListView)
        hv.clear()

        self.history_items = items
        self.history_selected_index = None
        has_pending = any((it.get("status") or "").upper() in ("PENDING", "PROCESSING") for it in items)

        if not items:
            if not self.accounts:
                hv.append(ListItem(Label("Import a wallet to see transactions here.")))
            else:
                hv.append(ListItem(Label("No transactions yet. Press 's' to send or 'x' to receive.")))
            try:
                self.query_one("#tx_detail_content", Static).update("No transactions available")
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to update tx detail content", exception=e)
            self._set_pending_blink(False)
            return

        for idx, it in enumerate(items, start=1):
            line = self._format_history_line(idx, it)
            hv.append(ListItem(Label(line, markup=True)))
        # Keep shimmer in sync whenever we render a list that includes pending items.
        self._set_pending_blink(has_pending)

        if self._history_notice:
            notice_item = ListItem(Label(self._history_notice, markup=True))
            hv.append(notice_item)
            if self.selected:
                tzkt_url = f"https://tzkt.io/{self.selected.address}/operations"
                tzkt_link = (
                    f"[u][link=\"{tzkt_url}\"]{tzkt_url}[/link][/u] "
                    "[dim](Shift+Left click)[/dim]"
                )
                try:
                    self.query_one("#tx_detail_content", Static).update(
                        f"[b]More on TzKT[/b]\n{tzkt_link}"
                    )
                except _UI_QUERY_EXCEPTIONS as e:
                    log_error("Failed to update tzkt link in tx details", exception=e)
        else:
            if (
                len(items) >= Config.HISTORY_DEFAULT_LIMIT
                and self.history_limit < Config.HISTORY_MAX_LIMIT
                and self.selected
                and not self._history_exhausted.get(self.selected.address)
            ):
                more_item = ListItem(Label("[dim]Press 'm' or Enter for more[/dim]", markup=True))
                hv.append(more_item)
            elif (
                self.history_limit >= Config.HISTORY_MAX_LIMIT
                and self.selected
                and len(items) >= Config.HISTORY_DEFAULT_LIMIT
            ):
                max_item = ListItem(
                    Label(
                        "[dim]🥐 What else you want from me, baguettes? "
                        "For more txs, head to tzkt.io. >>>[/dim]",
                        markup=True,
                    )
                )
                hv.append(max_item)

        # Auto-select first transaction if available, unless we want to keep position
        if items:
            try:
                if self._history_keep_index is not None:
                    keep = min(self._history_keep_index, len(hv.children) - 1)
                    hv.index = keep
                    self.history_selected_index = keep
                    self._history_keep_index = None
                    self._update_tx_details()
                else:
                    hv.index = 0
                    self.history_selected_index = 0
                    self._update_tx_details()
            except _UI_QUERY_EXCEPTIONS as e:
                log_error("Failed to select first transaction", exception=e)
        self._set_pending_blink(has_pending)

    def _update_history_row_for_pending(self, oph: str, address: str) -> None:
        if not self.selected or self.selected.address != address:
            return
        idx = self._history_index_by_hash(oph)
        if idx is None:
            return
        with self._pending_ops_lock:
            pending = self._pending_ops.get(oph)
            if not pending:
                return
            self.history_items[idx] = dict(pending)
        try:
            hv = self.query_one("#history", ListView)
            rows = list(hv.children)
            if idx >= len(rows):
                return
            label = rows[idx].query_one(Label)
            label.update(self._format_history_line(idx + 1, self.history_items[idx]))
        except _UI_QUERY_EXCEPTIONS as e:
            log_error("Failed to update pending history row", exception=e)
        has_pending = any((it.get("status") or "").upper() in ("PENDING", "PROCESSING") for it in self.history_items)
        self._set_pending_blink(has_pending)
        self._cache_visible_history_for_address(address)

    def _format_history_line(self, idx: int, it: dict) -> str:
        ts_raw = it.get("ts") or ""
        ts = format_relative_time(ts_raw)

        direction = it.get("direction") or "?"
        amt: Decimal = it.get("amount_xtz") or Decimal(0)
        cp = it.get("counterparty") or "?"

        amt_formatted = format_xtz(amt)
        if direction == "IN":
            amt_str = f"[#34d399]{f'+{amt_formatted} XTZ':<15}[/#34d399]"
        elif direction == "OUT":
            amt_str = f"[red]{f'-{amt_formatted} XTZ':<15}[/red]"
        elif direction == "STK":
            amt_str = f"[#8b5cf6]{f'+{amt_formatted} XTZ':<15}[/#8b5cf6]"
        elif direction == "UST":
            amt_str = f"[#8b5cf6]{f'-{amt_formatted} XTZ':<15}[/#8b5cf6]"
        elif direction == "DEL":
            amt_str = f"[yellow]{f'---':<15}[/yellow]"
        elif direction == "UND":
            amt_str = f"[yellow]{f'---':<15}[/yellow]"
        elif direction == "BAK":
            amt_str = f"[yellow]{f'---':<15}[/yellow]"
        else:
            amt_str = f"{f'{amt_formatted} XTZ':<15}"

        kind = (it.get("kind") or "").lower()
        entrypoint = (it.get("entrypoint") or "").lower()
        if entrypoint == "change_baker":
            type_raw = "CH"
        elif kind == "delegation":
            type_raw = "DLG"
        elif entrypoint == "stake":
            type_raw = "STK"
        elif entrypoint == "unstake":
            type_raw = "USTK"
        else:
            type_raw = "TX"

        if type_raw in ("DLG", "CH"):
            type_text = f"[yellow]{type_raw:<4}[/yellow]"
        elif type_raw in ("STK", "USTK"):
            type_text = f"[#8b5cf6]{type_raw:<4}[/#8b5cf6]"
        else:
            type_text = f"{type_raw:<4}"

        if len(cp) > 23:
            cp_display = (cp[:11] + "…" + cp[-11:])
        else:
            cp_display = f"{cp:<23}"

        ts_padded = f"{ts:<12}"
        status = (it.get("status") or "CONFIRMED").upper()
        if status == "PROCESSING":
            if entrypoint == "change_baker":
                status_label = "CHANGING BAKER"
            elif direction in ("DEL", "UND"):
                status_label = "DELEGATING"
            elif direction == "UST":
                status_label = "UNSTAKING"
            elif direction == "STK":
                status_label = "STAKING"
            elif direction == "OUT":
                status_label = "SENDING"
            else:
                status_label = "BAKING TX"
        elif status == "PENDING":
            if entrypoint == "change_baker":
                status_label = "CHANGING BAKER"
            elif direction in ("DEL", "UND"):
                status_label = "DELEGATING"
            elif direction == "UST":
                status_label = "UNSTAKING"
            elif direction == "STK":
                status_label = "STAKING"
            else:
                status_label = "BAKING TX"
        elif status == "UNKNOWN":
            status_label = "UNKNOWN"
        elif status == "FAILED":
            status_label = "FAIL"
        else:
            if entrypoint == "change_baker":
                status_label = "BAKER CHANGED"
            elif direction in ("DEL", "UND"):
                status_label = "DELEGATED"
            elif direction == "UST":
                status_label = "UNSTAKED"
            elif direction == "STK":
                status_label = "STAKED"
            elif direction == "IN":
                status_label = "RECEIVED"
            elif direction == "OUT":
                status_label = "SENT"
            else:
                status_label = "TX BAKED"

        if status == "FAILED":
            status_color = "red"
        elif status == "PROCESSING":
            status_color = "yellow"
        elif direction in ("STK", "UST"):
            status_color = "#8b5cf6"
        elif direction in ("DEL", "UND"):
            status_color = "yellow"
        elif direction in ("IN", "OUT"):
            status_color = "dim"
        else:
            status_color = "green"

        if status in ("PENDING", "PROCESSING"):
            shimmer = shimmer_text(status_label, self._pending_shimmer_i, span=2, pingpong=True)
            status_text = f"{shimmer}{' ' * max(0, 10 - len(status_label))}"
        else:
            status_text = f"[{status_color}]{status_label:<10}[/{status_color}]"

        idx_text = f"{idx:<3}"
        return f"{idx_text} {ts_padded}  {type_text}  {amt_str}  {cp_display}  {status_text}"

    def _history_cache_key(self, address: str) -> tuple[str, int]:
        return (address, self.history_limit)

    def _cache_visible_history_for_address(self, address: str) -> None:
        """Persist currently visible history for the selected address into cache."""
        if not address or self._history_loaded_addr != address:
            return
        with self._history_cache_lock:
            self.history_cache[self._history_cache_key(address)] = list(self.history_items)

    def _invalidate_history_cache(self, address: str | None = None) -> None:
        with self._history_cache_lock:
            if address:
                for k in list(self.history_cache.keys()):
                    if k[0] == address:
                        self.history_cache.pop(k, None)
                self._history_exhausted.pop(address, None)
            else:
                self.history_cache.clear()
                self._history_exhausted.clear()
        invalidate_history_cache()

    def _load_history_for_selected(self, force: bool = False, *, quiet: bool = False) -> None:
        selected = self._get_selected()
        if not selected:
            return
        self._history_notice = None
        addr = selected.address
        key = self._history_cache_key(addr)

        self._update_history_title()

        with self._history_cache_lock:
            if not force and key in self.history_cache:
                cached_items = self.history_cache[key]
                merged_items = self._merge_history_with_pending(cached_items, addr, resolve_pending=False)
                merged_items = merged_items[: self.history_limit]
                self._render_history(merged_items)
                self._history_loaded_addr = addr
                self._clear_account_loading(addr)
                if quiet:
                    return
                # Refresh in background to reconcile cache with indexer
                self._load_history(addr, self.history_limit, quiet=True)
                return

        self._load_history(addr, self.history_limit, quiet=quiet)

    def _apply_loaded_history_if_selected(
        self,
        address: str,
        items: list[dict],
        *,
        quiet: bool,
    ) -> None:
        """Apply loaded history only when the same wallet is still selected."""
        selected = self._get_selected()
        if not selected or selected.address != address:
            self._clear_account_loading(address)
            return
        self._render_history(items)
        self._set_history_loaded_addr(address)
        if not quiet:
            if self._history_requested_more:
                self._set_status_styled_locked(
                    "🥖 10 more baguettes ready to eat!",
                    "success",
                )
            else:
                self._set_status(get_message("refresh_success"))
        self._clear_account_loading(address)

    def _apply_history_load_error_if_selected(self, address: str, err: str, *, quiet: bool) -> None:
        """Show history-load errors only for the currently selected wallet."""
        selected = self._get_selected()
        if selected and selected.address == address:
            self._render_history([])
            if not quiet:
                self._set_status(f"❌ Display shelf check failed: {err}")
        self._clear_account_loading(address)

    def _prime_history_for_address(self, address: str) -> None:
        """Render cached history immediately to avoid a blank list during send."""
        if not address:
            return
        key = self._history_cache_key(address)
        cached_items = None
        with self._history_cache_lock:
            cached_items = self.history_cache.get(key)
        if cached_items is not None:
            merged_items = self._merge_history_with_pending(cached_items, address, resolve_pending=False)
            merged_items = merged_items[: self.history_limit]
            self._render_history(merged_items)
            self._set_history_loaded_addr(address)
            return
        if self._history_loaded_addr != address:
            self._render_history([])

    def _focus_history_on_address(
        self,
        address: str,
        *,
        ensure_loaded: bool = True,
        refresh_details: bool = True,
    ) -> None:
        """Select a wallet and show its history immediately (Send-like UX)."""
        if not address:
            return
        idx = self._account_index_by_address(address)
        if idx is None:
            return
        try:
            if self._last_selected_addr != address:
                # Switch context without forcing an immediate full refresh.
                self._apply_account_selection(
                    idx,
                    refresh_details=refresh_details,
                    refresh_history=False,
                )
            self._prime_history_for_address(address)
            if ensure_loaded and (self._history_loaded_addr != address or not self.history_items):
                self._load_history_for_selected(force=True, quiet=True)
        except _UI_QUERY_EXCEPTIONS as e:
            # Never block operation dispatch if UI selection/focus glitches transiently.
            log_warning("Failed to focus history on source wallet", exception=e, address=address)

    def _prefetch_history_for_address(self, address: str) -> None:
        def _worker() -> None:
            try:
                items = get_xtz_history(self.rpc, address, limit=self.history_limit)
                items = self._merge_history_with_pending(items, address, resolve_pending=True)
                items = items[: self.history_limit]
                with self._history_cache_lock:
                    self.history_cache[(address, self.history_limit)] = items
                selected = self._get_selected()
                if not selected or selected.address != address:
                    return
                self._ui(self._render_history, items)
                self._ui(self._set_history_loaded_addr, address)
                self._ui(self._clear_account_loading, address)
            except _FLOW_PRECHECK_EXCEPTIONS as e:
                log_warning("Failed to prefetch history", exception=e, address=address)
        self.run_worker(_worker, exclusive=False, thread=True)

    @work(exclusive=True, thread=True)
    def _load_history(self, address: str, limit: int, *, quiet: bool = False) -> None:
        logging.info(f"Loading history for {address} (limit: {limit})")
        if not quiet:
            self._ui(self._start_spinner, get_message("refresh_checking"))
        try:
            items = get_xtz_history(self.rpc, address, limit=limit)
            base_count = len(items)
            items = self._merge_history_with_pending(items, address, resolve_pending=True)
            items = items[:limit]
            logging.info(f"Loaded {len(items)} transaction(s) for {address}")
            with self._history_cache_lock:
                self.history_cache[(address, limit)] = items
            self._history_exhausted[address] = base_count < limit
            if base_count < limit and self._history_requested_more:
                self._history_notice = (
                    "[dim]🥐 What else you want from me, baguettes? "
                    "For more txs, head to tzkt.io.[/dim]"
                )
            self._ui(self._apply_loaded_history_if_selected, address, items, quiet=quiet)
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_error("Failed to load history", exception=e, address=address, limit=limit)
            self._ui(self._apply_history_load_error_if_selected, address, str(e), quiet=quiet)
        finally:
            self._ui(self._set_history_requested_more, False)
            if not quiet:
                self._ui(self._stop_spinner)
            self._ui(self._update_status_balance)

    def _merge_history_with_pending(self, items: list[dict], address: str, *, resolve_pending: bool = False) -> list[dict]:
        now = time.time()
        merged: list[dict] = []
        seen_hashes: set[str] = set()
        pending_changed = False
        resolved_items: list[dict] = []

        for it in items:
            item = dict(it)
            item.setdefault("status", "CONFIRMED")
            h = item.get("hash") or ""
            if h:
                override = self._op_entrypoint_overrides.get(h)
                if override:
                    item["entrypoint"] = override
                seen_hashes.add(h)
            merged.append(item)

        with self._pending_ops_lock:
            for oph, pending in list(self._pending_ops.items()):
                if pending.get("address") != address:
                    continue
                if oph in seen_hashes:
                    force_until = pending.get("force_pending_until")
                    if isinstance(force_until, (int, float)) and now < float(force_until):
                        merged = [it for it in merged if (it.get("hash") or "") != oph]
                        pending_changed = True
                    else:
                        self._pending_ops.pop(oph, None)
                        pending_changed = True
                        continue
                # For stake/delegate UX, treat UNKNOWN as OK unless proven otherwise
                if pending.get("status") == "UNKNOWN" and pending.get("direction") in ("STK", "DEL", "UST"):
                    pending["status"] = "CONFIRMED"
                    pending_changed = True
                age = now - float(pending.get("ts_epoch") or 0.0)
                if pending.get("status") == "PENDING" and age > Config.PENDING_TX_TIMEOUT_SECONDS:
                    pending["status"] = "UNKNOWN"
                    pending_changed = True
                if pending.get("status") == "PROCESSING":
                    until = pending.get("processing_until")
                    if isinstance(until, (int, float)) and now > float(until):
                        pending["status"] = "CONFIRMED"
                        pending["processing_until"] = None
                        pending_changed = True
                    else:
                        pending_changed = True
                if resolve_pending and pending.get("status") == "UNKNOWN":
                    try:
                        resolved = resolve_tx_by_hash(self.rpc, address, oph)
                        if resolved:
                            self._pending_ops.pop(oph, None)
                            pending_changed = True
                            resolved_items.append(resolved)
                            continue
                    except _FLOW_PRECHECK_EXCEPTIONS as e:
                        log_debug("Failed to resolve pending tx by hash", exception=str(e), oph=oph, address=address)
                merged.append(dict(pending))

        merged.extend(resolved_items)
        # Apply entrypoint overrides to resolved items too (e.g. change_baker).
        for it in merged:
            h = it.get("hash") or ""
            if not h:
                continue
            override = self._op_entrypoint_overrides.get(h)
            if override:
                it["entrypoint"] = override
        merged.sort(key=lambda x: x.get("ts") or "", reverse=True)
        if pending_changed:
            self._persist_pending_ops()
        return merged

    def _set_history_loaded_addr(self, address: str) -> None:
        self._history_loaded_addr = address

    def _set_history_requested_more(self, value: bool) -> None:
        self._history_requested_more = value

    def _coerce_pending_item(self, item: dict) -> dict:
        coerced = dict(item)
        amt = coerced.get("amount_xtz")
        if isinstance(amt, str):
            try:
                coerced["amount_xtz"] = Decimal(amt)
            except _NUMERIC_PARSE_EXCEPTIONS as e:
                log_debug("Failed to coerce pending amount", exception=str(e), amount=amt)
        proc = coerced.get("processing_until")
        if isinstance(proc, str):
            try:
                coerced["processing_until"] = float(proc)
            except _NUMERIC_PARSE_EXCEPTIONS as e:
                log_debug("Failed to coerce pending processing_until", exception=str(e), processing_until=proc)
        force_until = coerced.get("force_pending_until")
        if isinstance(force_until, str):
            try:
                coerced["force_pending_until"] = float(force_until)
            except _NUMERIC_PARSE_EXCEPTIONS as e:
                log_debug("Failed to coerce pending force_until", exception=str(e), force_until=force_until)
        return coerced

    def _persist_pending_ops(self) -> None:
        with self._store_lock, self._pending_ops_lock:
            serialized = []
            for item in self._pending_ops.values():
                out = dict(item)
                amt = out.get("amount_xtz")
                if isinstance(amt, Decimal):
                    out["amount_xtz"] = str(amt)
                serialized.append(out)
            self.store["pending_ops"] = serialized
            save_store(self.store)

    def _persist_op_entrypoint_overrides(self) -> None:
        with self._store_lock:
            self.store["op_entrypoint_overrides"] = dict(self._op_entrypoint_overrides)
            save_store(self.store)

    def _set_op_entrypoint_override(self, oph: str, entrypoint: str) -> None:
        oph = (oph or "").strip()
        entrypoint = (entrypoint or "").strip()
        if not oph or not entrypoint:
            return
        # Keep a small bounded set to avoid unbounded growth.
        self._op_entrypoint_overrides[oph] = entrypoint
        while len(self._op_entrypoint_overrides) > 500:
            oldest_key = next(iter(self._op_entrypoint_overrides), None)
            if oldest_key is None:
                break
            self._op_entrypoint_overrides.pop(oldest_key, None)
        self._persist_op_entrypoint_overrides()

    def _format_baker_label(self, baker_addr: Optional[str]) -> str:
        if not baker_addr:
            return "?"
        info = get_baker_info(self.rpc, baker_addr)
        alias = info.get("alias") if info else None
        return alias or baker_addr

    def _shorten_baker_label(self, label: str) -> str:
        if not label:
            return label
        if (label.startswith("tz") or label.startswith("KT1")) and len(label) > 16:
            return f"{label[:6]}…{label[-4:]}"
        return label

    def _resolve_baked_by_label(
        self,
        rpc: str,
        oph: str,
        *,
        wait_seconds: float = 0.0,
    ) -> Optional[str]:
        deadline = time.time() + max(0.0, wait_seconds)
        while True:
            baker_addr = None
            try:
                baker_addr = find_baker_for_operation(rpc, oph)
            except _FLOW_PRECHECK_EXCEPTIONS as e:
                log_warning("Failed to resolve baker for op", exception=e, oph=oph)
            if baker_addr:
                try:
                    label = self._format_baker_label(baker_addr)
                except _FLOW_PRECHECK_EXCEPTIONS as e:
                    log_warning("Failed to format baker label", exception=e, baker_addr=baker_addr)
                    label = baker_addr
                label = self._shorten_baker_label(label)
                if label and label != "?":
                    return label
            if time.time() >= deadline:
                break
            time.sleep(1.0)
        return None

    def _add_pending_tx(
        self,
        *,
        address: str,
        oph: str,
        direction: str,
        amount_xtz: Decimal,
        counterparty: str,
        kind: str = "transaction",
        entrypoint: str = "",
        history_delay_seconds: float | None = None,
        processing_seconds: float | None = None,
        select_wallet: bool = True,
    ) -> None:
        history_delay = 0.0
        if history_delay_seconds is not None and history_delay_seconds > 0:
            history_delay = float(history_delay_seconds)
        processing_delay = 0.0
        if processing_seconds is not None and processing_seconds > 0:
            processing_delay = float(processing_seconds)
        processing_total = history_delay + processing_delay

        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        item = {
            "ts": ts,
            "direction": direction,
            "amount_xtz": amount_xtz,
            "counterparty": counterparty,
            "hash": oph,
            "kind": kind,
            "entrypoint": entrypoint,
            "status": "PROCESSING" if processing_delay > 0 else "PENDING",
            "address": address,
            "ts_epoch": time.time(),
            "processing_until": (time.time() + processing_total) if processing_delay > 0 else None,
            "force_pending_until": (time.time() + processing_total) if processing_delay > 0 else None,
        }

        with self._pending_ops_lock:
            self._pending_ops[oph] = item
        self._persist_pending_ops()

        if entrypoint:
            self._set_op_entrypoint_override(oph, entrypoint)

        # Ensure source wallet is selected so pending row is visible immediately.
        if select_wallet and (not self.selected or self.selected.address != address):
            self._select_account_by_address(address)

        if self.selected and self.selected.address == address:
            # Avoid cross-wallet history bleed: right after selection switches,
            # self.history_items may still belong to the previously selected wallet.
            if self._history_loaded_addr == address:
                base_items = self.history_items
            else:
                with self._history_cache_lock:
                    base_items = list(self.history_cache.get(self._history_cache_key(address), []))
            merged_items = self._merge_history_with_pending(base_items, address, resolve_pending=False)
            merged_items = merged_items[: self.history_limit]
            self._render_history(merged_items)
            self._set_history_loaded_addr(address)
            self._cache_visible_history_for_address(address)
            # Start shimmer immediately (not only after the first timer tick), so the
            # "processing" feel is synced with the status bar breathing.
            has_pending = any(
                (it.get("status") or "").upper() in ("PENDING", "PROCESSING")
                for it in self.history_items
            )
            self._set_pending_blink(has_pending)

        # UX: assume OK after a short delay, then verify quietly in background
        try:
            if processing_delay > 0:
                self.set_timer(
                    processing_total,
                    lambda: self._finalize_processing_ok(oph, address),
                )
            else:
                self.set_timer(
                    Config.PENDING_TX_ASSUME_OK_SECONDS,
                    lambda: self._assume_pending_ok(oph, address),
                )
            self.set_timer(
                max(Config.PENDING_TX_VERIFY_SECONDS, processing_total),
                lambda: self._verify_pending_op(oph, address),
            )
        except _UI_CALLBACK_EXCEPTIONS as e:
            log_error("Failed to schedule pending op checks", exception=e)

        # Skip full history refresh here; pending rows update in-place for smoother UX.

    def _assume_pending_ok(self, oph: str, address: str) -> None:
        with self._pending_ops_lock:
            pending = self._pending_ops.get(oph)
            if not pending or pending.get("address") != address:
                return
            if pending.get("status") == "PENDING":
                pending["status"] = "CONFIRMED"
                pending["processing_until"] = None
                self._persist_pending_ops()
        self._update_history_row_for_pending(oph, address)

    def _finalize_processing_ok(self, oph: str, address: str) -> None:
        with self._pending_ops_lock:
            pending = self._pending_ops.get(oph)
            if not pending or pending.get("address") != address:
                return
            if pending.get("status") == "PROCESSING":
                pending["status"] = "CONFIRMED"
                pending["processing_until"] = None
                self._persist_pending_ops()

        self._update_history_row_for_pending(oph, address)

    def _verify_pending_op(self, oph: str, address: str) -> None:
        """Verify pending op quietly without blocking UI."""
        self.run_worker(
            lambda: self._verify_pending_op_worker(oph, address),
            exclusive=False,
            thread=True,
        )

    def _verify_pending_op_worker(self, oph: str, address: str) -> None:
        confirmed = False
        try:
            confirmed = bool(resolve_tx_by_hash(self.rpc, address, oph))
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_error("Pending op verify failed", exception=e)

        self._ui(self._apply_pending_verification, oph, address, confirmed)

    def _apply_pending_verification(self, oph: str, address: str, confirmed: bool) -> None:
        with self._pending_ops_lock:
            pending = self._pending_ops.get(oph)
            if not pending or pending.get("address") != address:
                return
            if pending.get("status") == "PROCESSING":
                until = pending.get("processing_until")
                if isinstance(until, (int, float)) and time.time() < float(until):
                    return
            if confirmed:
                pending["status"] = "CONFIRMED"
                pending["processing_until"] = None
            else:
                # Don't downgrade a previously assumed OK
                if pending.get("status") == "PENDING":
                    pending["status"] = "UNKNOWN"
            self._persist_pending_ops()

        self._update_history_row_for_pending(oph, address)

    # -------------------------
    # Recents helpers
    # -------------------------
    def _get_recent_to_for_wallet(self, wallet_addr: str) -> list[str]:
        """Get recent destinations for a specific wallet."""
        return self.recent_to_by_wallet.get(wallet_addr, [])

    def _push_recent_to(self, wallet_addr: str, dest_addr: str) -> None:
        """Add a destination to the recent list for a specific wallet."""
        dest_addr = (dest_addr or "").strip()
        if not dest_addr or not wallet_addr:
            return

        # Get or create the list for this wallet
        wallet_recents = self.recent_to_by_wallet.get(wallet_addr, [])

        # Remove if already exists (move to front)
        wallet_recents = [x for x in wallet_recents if x != dest_addr]
        wallet_recents.insert(0, dest_addr)
        wallet_recents = wallet_recents[:Config.RECENT_DESTINATIONS_MAX]

        # Update the dictionary and store (keep only max recent destinations)
        self.recent_to_by_wallet[wallet_addr] = wallet_recents[:Config.RECENT_DESTINATIONS_MAX]
        self.store["recent_to_by_wallet"] = self.recent_to_by_wallet
        save_store(self.store)

    # -------------------------
    # Actions
    # -------------------------
    def action_refresh(self) -> None:
        # Invalidate balance cache on manual refresh
        self._status_lock_until_refresh = False
        self._stop_breathing_effect()
        self._revert_status_style()
        if not self.accounts:
            self._set_status("🥖 Nothing to refresh — no bread, no pizza, nada. ¬_¬")
            return
        if self.selected:
            idx = self._account_index_by_address(self.selected.address)
            if idx is not None:
                self._show_account_loading(idx)
            self._invalidate_balance_cache(self.selected.address)
        self._update_status_balance()
        if self.selected:
            self._invalidate_history_cache(self.selected.address)
            self._load_history_for_selected(force=True, quiet=True)
            self._set_status(get_message("refresh_success"), force=True)
        else:
            self._set_status(get_message("refresh_success"), force=True)

    def _refresh_account(self) -> None:
        """Refresh balances and history for the selected account (silent)."""
        if not self.selected:
            return
        self._invalidate_balance_cache(self.selected.address)
        self._update_status_balance()
        self._invalidate_history_cache(self.selected.address)
        self._load_history_for_selected(force=True, quiet=True)

    def _refresh_account_status_only(self, address: Optional[str] = None) -> None:
        """Refresh balance/delegation/stake status without reloading history."""
        if not self.selected:
            return
        if address and self.selected.address != address:
            return
        self._invalidate_balance_cache(self.selected.address)
        # Keep current details visible while we refresh to avoid flicker.
        self._fetch_selected_status(self.selected.address)

    def _silent_refresh_history_for(self, address: str) -> None:
        """Silently refresh history for an address if it's still selected."""
        if not self.selected or self.selected.address != address:
            return
        self._invalidate_history_cache(address)
        self._load_history_for_selected(force=True, quiet=True)

    def action_toggle_auto_refresh(self) -> None:
        """Toggle automatic refresh on/off."""
        self._status_lock_until_refresh = False
        self._auto_refresh_enabled = not self._auto_refresh_enabled
        self.store["auto_refresh_enabled"] = self._auto_refresh_enabled
        save_store(self.store)

        if self._auto_refresh_enabled:
            self._start_auto_refresh()
            self._set_status(
                f"✅ Auto-refresh enabled (every {int(Config.AUTO_REFRESH_INTERVAL_SECONDS)}s)"
            )
            logging.info("Auto-refresh enabled")
        else:
            self._stop_auto_refresh()
            self._set_status("🛑 Auto-refresh disabled")
            logging.info("Auto-refresh disabled")

    def _start_auto_refresh(self) -> None:
        """Start the auto-refresh timer."""
        if self._auto_refresh_timer is None:
            self._auto_refresh_timer = self.set_interval(
                Config.AUTO_REFRESH_INTERVAL_SECONDS,
                self._auto_refresh_tick
            )
            logging.debug("Auto-refresh timer started")

    def _stop_auto_refresh(self) -> None:
        """Stop the auto-refresh timer."""
        if self._auto_refresh_timer is not None:
            self._auto_refresh_timer.stop()
            self._auto_refresh_timer = None
            logging.debug("Auto-refresh timer stopped")

    def _auto_refresh_tick(self) -> None:
        """Auto-refresh callback - refresh balance and history."""
        if not self.selected:
            return

        logging.debug("Auto-refresh tick")
        # Don't use cache for auto-refresh
        self._invalidate_balance_cache(self.selected.address)
        self._update_status_balance()

        # Refresh history silently (without user notification)
        self._invalidate_history_cache(self.selected.address)
        self._load_history_for_selected(force=True)

    def action_more_history(self) -> None:
        self._status_lock_until_refresh = False
        if not self.selected:
            self._set_status("ℹ️ No account selected")
            return
        self._history_notice = None
        addr = self.selected.address
        if self.history_limit >= Config.HISTORY_MAX_LIMIT:
            self._history_notice = (
                "[dim]🥐 What else you want from me, baguettes? "
                "For more txs, head to tzkt.io.[/dim]"
            )
            self._render_history(self.history_items)
            return
        if self._history_exhausted.get(addr):
            self._history_notice = (
                "[dim]🥐 What else you want from me, baguettes? "
                "For more txs, head to tzkt.io.[/dim]"
            )
            self._render_history(self.history_items)
            return
        new_limit = min(self.history_limit + Config.HISTORY_INCREMENT, Config.HISTORY_MAX_LIMIT)
        if new_limit == self.history_limit:
            return
        self._history_requested_more = True
        self._history_keep_index = self.history_selected_index
        self.history_limit = new_limit
        self._set_status_styled("🥖 Putting more bread in the oven…", style="info", duration=2.5)
        self._invalidate_history_cache(addr)
        self._load_history_for_selected(force=True)

    def action_tx_details(self) -> None:
        self._status_lock_until_refresh = False
        focused = self.focused
        if not isinstance(focused, ListView) or focused.id != "history":
            return
        if not self.history_items:
            self._set_status("ℹ️ No history items")
            return
        if self.history_selected_index is None:
            self._set_status("ℹ️ Select a history row first")
            return
        idx = self.history_selected_index
        if idx < 0 or idx >= len(self.history_items):
            self._set_status("⚠️ Invalid selection")
            return
        wallet_addr = self.selected.address if self.selected else ""
        self.push_screen(TxDetailsScreen(self.rpc, self.history_items[idx], wallet_addr))

    @work(exclusive=True)
    async def action_network(self) -> None:
        self._status_lock_until_refresh = False
        current = network_from_rpc(self.rpc)
        choice = await self.push_screen_wait(NetworkPickerScreen(current=current))
        if not choice or choice == current:
            return

        # Start from a reasonable default for the network, then auto-detect the first
        # RPC that supports BOTH simulation (run_operation) and injection.
        self.rpc = (
            _MAINNET_RPC_CANDIDATES[0]
            if choice == "mainnet"
            else _GHOSTNET_RPC_CANDIDATES[0]
        )
        self.store["rpc"] = self.rpc
        save_store(self.store)

        # Auto-detect a working RPC for this network (runs in this worker thread).
        best, can_send, can_sim = choose_working_rpc(self.rpc)
        self.rpc = best
        self.store["rpc"] = self.rpc
        save_store(self.store)

        self._update_rpc_indicator()

        self._invalidate_history_cache()
        self.history_limit = Config.HISTORY_DEFAULT_LIMIT
        self._update_history_title()

        import secrets

        if choice == "ghostnet":
            net_msgs = [
                "👻 Ghostnet selected — dummy tokens, real vibes.",
                "🧪 Ghostnet mode: play money, real lessons.",
                "🪄 Ghostnet it is — no risk, all practice.",
            ]
        else:
            net_msgs = [
                "🧠 Mainnet selected — serious tokens, serious moves.",
                "💎 Mainnet mode: real value on the line.",
                "⚠️ Mainnet engaged — make it count.",
            ]

        if can_send and can_sim:
            msg = f"Network set to {choice}. RPC OK. Refreshing…"
        elif can_send and not can_sim:
            msg = f"Network set to {choice}. RPC can send but no simulation. Refreshing…"
        else:
            msg = f"Network set to {choice}. RPC restricted. Refreshing…"

        self.query_one("#wallet_balance", Static).update(msg)
        self._status_lock_until_refresh = False
        self._set_status_styled_locked(secrets.choice(net_msgs), style="info")
        if self.selected:
            self._update_status_balance()
            self._load_history_for_selected(force=True, quiet=True)

    @work(exclusive=True)
    async def action_rpc(self) -> None:
        self._status_lock_until_refresh = False
        old_rpc = self.rpc
        choice = await self.push_screen_wait(RpcPickerScreen(current_rpc=self.rpc))
        if not choice or choice == old_rpc:
            return

        try:
            choice = normalize_rpc_url(choice)
        except ValueError as e:
            log_warning("Rejected invalid RPC selection", rpc=choice, reason=str(e))
            self._set_status_styled("❌ Invalid RPC URL. HTTPS endpoint required.", style="error", duration=6.0)
            return

        self.rpc = choice
        self.store["rpc"] = self.rpc
        save_store(self.store)

        self._update_rpc_indicator()
        self._invalidate_history_cache()
        self.history_limit = Config.HISTORY_DEFAULT_LIMIT
        self._update_history_title()

        can_send = rpc_supports_send(self.rpc)
        can_sim = rpc_supports_simulation(self.rpc)
        import secrets

        if can_send and can_sim:
            msg = f"RPC set: {self.rpc} (send + simulate)"
        elif can_send:
            msg = f"RPC set: {self.rpc} (send only)"
        else:
            msg = f"RPC set: {self.rpc} (restricted)"

        self.query_one("#wallet_balance", Static).update(msg)

        short_rpc = self.rpc.replace("https://", "").replace("http://", "")
        if len(short_rpc) > 35:
            short_rpc = short_rpc[:32] + "..."
        oven_msgs = [
            f"🥐 Fresh croissants incoming via {short_rpc}",
            f"🥖 New RPC oven, croissants on the way: {short_rpc}",
            f"🥐 Pastries queued — connected to {short_rpc}",
        ]
        self._status_lock_until_refresh = False
        self._set_status_styled_locked(secrets.choice(oven_msgs), style="info")
        if self.selected:
            self._update_status_balance()
            self._load_history_for_selected(force=True, quiet=True)

    def action_receive(self) -> None:
        self._status_lock_until_refresh = False
        if not self.accounts:
            self._set_status("🥐 Receive what, exactly? Fancy some croissant? Import a wallet first. ¬_¬")
            return
        addr = self.selected.address if self.selected else self.accounts[0].address
        self.push_screen(ReceiveScreen(addr, self.accounts))

    @work(exclusive=True)
    async def action_quit(self) -> None:
        self._status_lock_until_refresh = False
        import secrets

        exit_lines = [
            "🥐 Croissants are almost ready. Are you sure you want to leave?",
            "🥖 The oven is warm — you sure you want to walk away?",
            "🧈 Butter is melting. Exit now or stay for the aroma?",
            "🍞 Proofing in progress. Still want to close the bakery?",
            "🥐 Fresh batch incoming. Your call, baker.",
            "🔥 The oven just pinged. Walk away anyway?",
            "🍰 Dessert is queued. Exit or hang around?",
            "🥯 The bagels are rising. Sure about leaving?",
            "🧁 Frosting ready. Want to miss the finish?",
            "🥨 Twists are golden. Still exiting?",
            "🥖 Starter is alive. Leaving now feels wrong, no?",
            "🥐 The croissants just fluffed. Your call.",
        ]
        line = secrets.choice(exit_lines)
        message = f"[b #f59e0b]{line}[/b #f59e0b]\n\nAre you sure you want to exit?"
        confirmed = await self.push_screen_wait(
            ExitConfirmScreen(
                message,
                title="Exit",
                yes_label="Exit",
                no_label="Stay",
            )
        )
        if confirmed:
            self.exit()

    def action_stake(self) -> None:
        """Open stake/delegation modal and handle the returned action."""
        log_info(
            "action_stake requested",
            in_progress=self._stake_flow_in_progress,
            breathing=self._breathing_active,
            watchdog_active=bool(self._tx_watchdog_token),
            status_locked=self._status_lock_until_refresh,
        )
        if self._breathing_active or self._tx_watchdog_token is not None:
            self._set_status("⏳ Operation in progress - wait for current flow to finish.", force=True)
            return
        # A locked status line from a completed flow should not block entering Stake HQ.
        if self._status_lock_until_refresh:
            self._status_lock_until_refresh = False
        if self._stake_flow_in_progress:
            return
        self._stake_flow_in_progress = True
        self._status_lock_until_refresh = False

        try:
            self.run_worker(
                self._run_stake_flow,
                group=_STAKE_FLOW_WORKER_GROUP,
                exclusive=False,
                thread=False,
            )
        except _UI_CALLBACK_EXCEPTIONS as e:
            self._stake_flow_in_progress = False
            log_error("Failed to start stake flow worker", exception=e)
            self._set_status_styled("❌ Failed to start stake flow", style="error", duration=6.0)

    async def _run_stake_flow(self) -> None:
        try:
            await self._open_stake_flow()
        except asyncio.CancelledError:
            log_warning("action_stake cancelled")
        finally:
            log_info("action_stake finished")
            self._stake_flow_in_progress = False

    async def _open_stake_flow(self, ctx: Optional[dict] = None) -> None:
        """Open stake modal with optional context and handle the returned action."""
        if not self.accounts:
            self._set_status("🍕 Stake what, pizzas? Import a wallet first. ¬_¬")
            return

        # Filter watch-only wallets
        stakeable_accounts = [acc for acc in self.accounts if acc.enc is not None]

        if not stakeable_accounts:
            self._set_status("⚠️ No wallets with secret keys available. Cannot delegate or stake")
            return

        # Open StakeScreen and wait for returned data
        stake_data = await self.push_screen_wait(
            StakeScreen(
                accounts=self.accounts,
                rpc=self.rpc,
                wallet_info_cache=self._stake_wallet_info_cache,
                initial_ctx=ctx,
            )
        )
        if stake_data:
            log_info(
                "Stake flow modal dismissed with payload",
                action=stake_data.get("action"),
                has_account=bool(stake_data.get("account")),
                has_key=bool(stake_data.get("key")),
                has_amount=("amount" in stake_data),
            )
        else:
            log_info("Stake flow modal dismissed without payload")

        # If user cancelled or closed modal, stake_data will be None
        if not stake_data:
            return

        # Handle the action based on what was returned
        action = stake_data.get("action")
        account = stake_data.get("account")

        # Anchor main view to the source wallet immediately after StakeScreen closes.
        if account is not None:
            try:
                self._focus_history_on_address(
                    getattr(account, "address", ""),
                    ensure_loaded=True,
                    refresh_details=True,
                )
            except _UI_CALLBACK_EXCEPTIONS as e:
                log_warning(
                    "Failed to anchor source wallet after StakeScreen close",
                    exception=e,
                    address=getattr(account, "address", ""),
                )

        if action == "stake":
            await self._handle_stake_action(stake_data)
        elif action == "unstake":
            await self._handle_unstake_action(stake_data)
        elif action == "delegate":
            await self._handle_delegate_action(stake_data)
        elif action == "change_baker":
            await self._handle_change_baker_action(stake_data)

    async def _handle_stake_action(self, stake_data: dict) -> None:
        """
        Handle staking operation with new flow:
        1. Request passphrase (decrypt key)
        2. Estimate gas and show confirmation screen
        3. Execute stake operation
        """
        account = stake_data.get("account")
        amount = stake_data.get("amount")

        if not account or amount is None:
            log_error("Invalid stake data received", stake_data=stake_data)
            self._set_status("❌ Invalid stake data")
            return
        log_info(
            "Handling stake action",
            address=getattr(account, "address", ""),
            has_key=bool(stake_data.get("key")),
            amount=str(amount),
        )
        try:
            state = await asyncio.to_thread(
                get_wallet_chain_state,
                self.rpc,
                account.address,
                force_refresh=True,
                prefer_rpc=True,
            )
            pending_unstaked_mutez = int(state.get("unstaked_mutez") or 0)
            staked_mutez = int(state.get("staked_mutez") or 0)
            if pending_unstaked_mutez > 0 and staked_mutez <= 0:
                pending_unstake = format_xtz(mutez_to_xtz(pending_unstaked_mutez))
                self._set_status(
                    f"⚠️ Cannot stake yet. Pending unstake ({pending_unstake} XTZ) must finalize first (~4 cycles)."
                )
                return
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_warning("Failed to preflight unstaked balance before staking", exception=e, address=account.address)

        breathing_started = False
        watchdog_token = None
        try:
            confirm_result = None
            key = stake_data.get("key")
            fee_mutez = stake_data.get("fee_mutez")
            gas_limit = stake_data.get("gas_limit")
            storage_limit = stake_data.get("storage_limit")

            if key is None:
                error_note = ""
                while True:
                    passphrase = await self.push_screen_wait(
                        StakePassphraseScreen(
                            "Enter Your Encryption Password",
                            password=True,
                            placeholder="Your wallet encryption password",
                            wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                            ok_label="Next →",
                            fun_note="Keep your keys safe. Never share this encryption password. 🔐🥖",
                            show_back_button=True,
                            error_note=error_note,
                        )
                    )

                    if passphrase == BACK_NAV_MARKER:
                        self._set_status("⏸️ Staking cancelled")
                        return

                    if not passphrase:
                        self._set_status("👀 Chad mode has to wait — staking canceled.")
                        return

                    _, can_send, _ = self._ensure_working_rpc()
                    if not can_send:
                        log_warning(
                            "Stake RPC precheck reports no injection support; attempting anyway",
                            address=account.address,
                            rpc=self.rpc,
                        )

                    try:
                        secret_key = decrypt_secret(account.enc, passphrase)
                    except InvalidTag:
                        error_note = "❌ Wrong encryption password. Try again."
                        continue
                    except (ValueError, TypeError) as decrypt_err:
                        raise RuntimeError("Malformed encrypted wallet data") from decrypt_err
                    key = key_from_encoded_secret(secret_key)

                    key_pkh = key.public_key_hash()
                    if account.address != key_pkh:
                        self._set_status("❌ KEY MISMATCH! Wallet address doesn't match decrypted key")
                        return

                    # Preflight: refresh delegation state (best-effort).
                    # Do NOT block if indexer lags; allow chain to validate.
                    try:
                        state = await asyncio.to_thread(
                            get_wallet_chain_state,
                            self.rpc,
                            account.address,
                            force_refresh=True,
                            prefer_rpc=True,
                        )
                        if not state.get("delegate"):
                            log_warning(
                                "Delegation not indexed yet; proceeding with stake",
                                address=account.address,
                            )
                    except _FLOW_PRECHECK_EXCEPTIONS as e:
                        log_warning("Failed to preflight wallet delegation state", exception=e, address=account.address)

                    confirm_result = await self.push_screen_wait(
                        ConfirmStakeScreen(
                            rpc=self.rpc,
                            key=key,
                            address=account.address,
                            amount=amount,
                            show_back_button=True
                        )
                    )

                    if confirm_result and confirm_result.get(BACK_NAV_MARKER):
                        continue
                    if not confirm_result or not confirm_result.get("ok"):
                        self._set_status("👀 Chad mode has to wait — staking canceled.")
                        return

                    fee_mutez = confirm_result.get("fee_mutez")
                    gas_limit = confirm_result.get("gas_limit")
                    storage_limit = confirm_result.get("storage_limit")
                    break
            else:
                key_pkh = key.public_key_hash()
                if account.address != key_pkh:
                    log_warning(
                        "Stake key mismatch in app handler",
                        expected=account.address,
                        got=key_pkh,
                    )
                    self._set_status("❌ KEY MISMATCH! Wallet address doesn't match decrypted key")
                    return
                _, can_send, _ = self._ensure_working_rpc()
                if not can_send:
                    log_warning(
                        "Stake RPC precheck reports no injection support; attempting anyway",
                        address=account.address,
                        rpc=self.rpc,
                    )
                # Skip preflight when key/fees were already confirmed in StakeScreen
                # to avoid reopening the stake modal due to indexer lag.

            # Step 3: Execute staking operation with confirmed parameters

            # Ensure the source wallet is selected and its history is visible immediately.
            self._focus_history_on_address(account.address, ensure_loaded=True)

            pre_staked_mutez = None
            try:
                pre_staked_mutez = await asyncio.to_thread(get_staking_balance, self.rpc, account.address)
            except _FLOW_PRECHECK_EXCEPTIONS as e:
                log_warning("Failed to fetch staked balance before staking", exception=e, address=account.address)

            flow_start = time.time()
            self._ui(
                self._start_breathing_effect,
                "⏳ Staking... This may take a moment...",
                bright_class="status-stake",
                dim_class="status-stake-dim",
            )
            self._ui(self._set_busy, True)
            # Ensure the UI renders the new classes before we start awaiting work.
            await asyncio.sleep(0)
            breathing_started = True
            watchdog_token = self._ui(self._start_tx_watchdog, "stake", account.address)

            try:
                handled = {"done": False}
                wd_token = watchdog_token
                tx_task = asyncio.create_task(
                    asyncio.to_thread(
                        self._with_rpc_fallback,
                        action="stake",
                        rpc=self.rpc,
                        source_address=account.address,
                        require_stake_support=True,
                        fn=lambda r: stake_xtz(
                            r,
                            key,
                            amount,
                            fee_mutez=fee_mutez,
                            gas_limit=gas_limit,
                            storage_limit=storage_limit,
                        ),
                    )
                )

                def _late_done(task: "asyncio.Task") -> None:
                    # If the action timed out at the UI layer, still try to surface
                    # the injected op in history when we eventually get the hash.
                    if handled["done"]:
                        return
                    if wd_token is not None and self._tx_watchdog_token == wd_token:
                        # Still within the "normal" flow; main path will handle UI.
                        return
                    try:
                        _, late_oph = task.result()
                    except _FLOW_TASK_EXCEPTIONS as e:
                        log_warning("Stake task failed after UI timeout", exception=e, address=account.address)
                        return
                    try:
                        self._add_pending_tx(
                            address=account.address,
                            oph=late_oph,
                            direction="STK",
                            amount_xtz=amount,
                            counterparty="The baker",
                            kind="transaction",
                            entrypoint="stake",
                            history_delay_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                            processing_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                            select_wallet=False,
                        )
                        self._schedule_after(60.0, lambda: self._silent_refresh_history_for(account.address))
                    except _UI_CALLBACK_EXCEPTIONS as e:
                        log_warning("Failed to apply late stake UI update", exception=e, address=account.address)

                tx_task.add_done_callback(lambda t: self._ui(_late_done, t))

                _, op_hash = await asyncio.wait_for(
                    asyncio.shield(tx_task),
                    timeout=Config.TX_RPC_HARD_TIMEOUT_SECONDS,
                )
                handled["done"] = True
                log_info("Stake operation injected", address=account.address, op_hash=op_hash)
            except asyncio.TimeoutError:
                if watchdog_token is not None:
                    self._ui(self._tx_watchdog_fire, watchdog_token, "stake", account.address)
                self._ui(self._stop_breathing_effect)
                self._ui(self._set_busy, False)
                log_warning("Stake operation timed out waiting for injection", address=account.address)
                return
            finally:
                if watchdog_token is not None:
                    self._ui(self._stop_tx_watchdog, watchdog_token)
                    watchdog_token = None

            remaining = self._tx_flow_remaining_or_default(flow_start)
            baker_label = "The baker"
            self._ui(
                self._add_pending_tx,
                address=account.address,
                oph=op_hash,
                direction="STK",
                amount_xtz=amount,
                counterparty=baker_label,
                kind="transaction",
                entrypoint="stake",
                history_delay_seconds=0.0,
                processing_seconds=remaining,
            )
            # Resolve the actual baker address without blocking the UI.
            self.run_worker(
                lambda oph=op_hash, addr=account.address: self._resolve_delegate_for_pending(oph, addr),
                exclusive=False,
                thread=True,
            )

            self._ui(setattr, self, "_status_lock_until_refresh", True)
            # Keep breathing until the pending row resolves (synced with shimmer),
            # then stop breathing in the finalizer.
            self._ui(self._set_status, "⏳ Staking submitted - waiting for inclusion...", force=True)
            is_first_stake = pre_staked_mutez is not None and pre_staked_mutez <= 0
            baked_by_box = {"label": None}
            if not is_first_stake:
                def _resolve_label() -> None:
                    baked_by_box["label"] = self._resolve_baked_by_label(
                        self.rpc,
                        op_hash,
                        wait_seconds=remaining,
                    )
                self.run_worker(_resolve_label, exclusive=False, thread=True)

            def _finish_stake_status() -> None:
                self._stop_breathing_effect()
                self._set_busy(False)
                if is_first_stake:
                    label = baker_label
                    if label and label not in ("?", "The baker"):
                        msg = f"✅ Staked {format_xtz(amount)} XTZ with {label}! 💪🔥"
                    else:
                        msg = f"✅ Staked {format_xtz(amount)} XTZ successfully! 💪🔥"
                else:
                    label = baked_by_box["label"]
                    baked_msg = get_send_baked_message(label)
                    msg = f"✅ Staked {format_xtz(amount)} XTZ — {baked_msg}"
                self._set_status_styled(
                    msg,
                    style="stake",
                    duration=0.0,
                    force=True,
                )

            # Slight delay so the history row can flip from PROCESSING -> STAKED first.
            self._ui(self.set_timer, remaining + 0.05, _finish_stake_status)
            # Safety net: if finalize callback is skipped, do not leave breathing forever.
            self._ui(self._schedule_after, remaining + 5.0, lambda: self._tx_finalize_failsafe("stake", account.address))
            self._ui(self._schedule_after, remaining, lambda: self._refresh_account_status_only(account.address))
            self._ui(self._schedule_after, remaining + 60.0, lambda: self._silent_refresh_history_for(account.address))

        except asyncio.CancelledError:
            if breathing_started:
                self._ui(self._stop_breathing_effect)
                self._ui(self._set_busy, False)
            if watchdog_token is not None:
                self._ui(self._stop_tx_watchdog, watchdog_token)
            raise
        except _FLOW_TASK_EXCEPTIONS as e:

            error_msg = str(e)
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."

            log_error("Staking failed during execution", exception=e, address=getattr(account, "address", ""))
            self._ui(self._stop_breathing_effect)
            self._ui(self._set_busy, False)
            self._ui(self._set_status_styled, f"❌ Staking failed: {error_msg}", style="error", duration=6.0)
        except Exception as e:
            log_error("Unhandled staking error", exception=e, address=getattr(account, "address", ""))
            self._ui(self._stop_breathing_effect)
            self._ui(self._set_busy, False)
            self._ui(
                self._set_status_styled,
                "❌ Staking failed: unexpected error (check logs).",
                style="error",
                duration=6.0,
            )

    async def _handle_unstake_action(self, stake_data: dict) -> None:
        """
        Handle unstaking operation with new flow:
        1. Request passphrase (decrypt key)
        2. Estimate gas and show confirmation screen
        3. Execute unstake operation
        """
        account = stake_data.get("account")
        amount = stake_data.get("amount")

        if not account or amount is None:
            log_error("Invalid unstake data received", stake_data=stake_data)
            self._set_status("❌ Invalid unstake data")
            return

        breathing_started = False
        watchdog_token = None
        try:
            confirm_result = None
            key = stake_data.get("key")
            fee_mutez = stake_data.get("fee_mutez")
            gas_limit = stake_data.get("gas_limit")
            storage_limit = stake_data.get("storage_limit")

            if key is None:
                error_note = ""
                while True:
                    passphrase = await self.push_screen_wait(
                        StakePassphraseScreen(
                            "Enter Your Encryption Password",
                            password=True,
                            placeholder="Your wallet encryption password",
                            wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                            ok_label="Next →",
                            fun_note="Keep your keys safe. Never share this encryption password. 🔐🥖",
                            show_back_button=True,
                            error_note=error_note,
                        )
                    )

                    if passphrase == BACK_NAV_MARKER:
                        self._set_status("⏸️ Unstaking cancelled")
                        return

                    if not passphrase:
                        self._set_status("⏸️ Unstaking cancelled")
                        return

                    _, can_send, _ = self._ensure_working_rpc()
                    if not can_send:
                        self._set_status("[red]❌ No RPC available to inject operations[/red]")
                        return

                    try:
                        secret_key = decrypt_secret(account.enc, passphrase)
                    except InvalidTag:
                        error_note = "❌ Wrong encryption password. Try again."
                        continue
                    except (ValueError, TypeError) as decrypt_err:
                        raise RuntimeError("Malformed encrypted wallet data") from decrypt_err
                    key = key_from_encoded_secret(secret_key)

                    key_pkh = key.public_key_hash()
                    if account.address != key_pkh:
                        self._set_status("❌ KEY MISMATCH!")
                        return

                    # Preflight: refresh staking state (best-effort).
                    # Do NOT block if indexer lags; allow chain to validate.
                    try:
                        state = await asyncio.to_thread(
                            get_wallet_chain_state,
                            self.rpc,
                            account.address,
                            force_refresh=True,
                            prefer_rpc=True,
                        )
                        staked_mutez = int(state.get("staked_mutez") or 0)
                        staking_active = bool(state.get("staking_active")) or (staked_mutez > 0)
                        staked_xtz = mutez_to_xtz(staked_mutez)
                        if staked_xtz <= 0 and not staking_active:
                            log_warning(
                                "Staked balance not indexed yet; proceeding with unstake",
                                address=account.address,
                            )
                        if staked_xtz > 0 and amount > staked_xtz:
                            log_warning(
                                "Staked balance changed; proceeding with unstake",
                                address=account.address,
                            )
                    except _FLOW_PRECHECK_EXCEPTIONS as e:
                        log_warning("Failed to preflight wallet staking state", exception=e, address=account.address)

                    confirm_result = await self.push_screen_wait(
                        ConfirmUnstakeScreen(
                            rpc=self.rpc,
                            key=key,
                            address=account.address,
                            amount=amount,
                            show_back_button=True
                        )
                    )

                    if confirm_result and confirm_result.get(BACK_NAV_MARKER):
                        continue
                    if not confirm_result or not confirm_result.get("ok"):
                        self._set_status("↩️ Unstaking cancelled")
                        return

                    fee_mutez = confirm_result.get("fee_mutez")
                    gas_limit = confirm_result.get("gas_limit")
                    storage_limit = confirm_result.get("storage_limit")
                    break
            else:
                key_pkh = key.public_key_hash()
                if account.address != key_pkh:
                    self._set_status("❌ KEY MISMATCH!")
                    return
                _, can_send, _ = self._ensure_working_rpc()
                if not can_send:
                    self._set_status("[red]❌ No RPC available to inject operations[/red]")
                    return
                # Skip preflight when key/fees were already confirmed in StakeScreen
                # to avoid reopening the stake modal due to indexer lag.

            # Extra confirmation to discourage impulsive unstaking (skip if already confirmed in Stake HQ).
            if not stake_data.get("second_confirmed"):
                # Small delay avoids auto-accept from the previous button click.
                await asyncio.sleep(0.05)
                confirmed = await self.push_screen_wait(
                    ConfirmScreen(
                        "Unstaking is reversible, but your future self might judge you.\n\n"
                        "Still want to proceed?",
                        title="Second Thoughts",
                        yes_label="Yes, unstake",
                        no_label="Keep staking",
                    )
                )
                if not confirmed:
                    self._set_status("😒 Unstake canceled. Chad mode stays on.")
                    return

            # Ensure the source wallet is selected and its history is visible immediately.
            self._focus_history_on_address(account.address, ensure_loaded=True)

            flow_start = time.time()
            self._ui(
                self._start_breathing_effect,
                "⏳ Unstaking... This may take a moment...",
                bright_class="status-unstake",
                dim_class="status-unstake-dim",
            )
            self._ui(self._set_busy, True)
            # Ensure the UI renders the new classes before we start awaiting work.
            await asyncio.sleep(0)
            breathing_started = True
            watchdog_token = self._ui(self._start_tx_watchdog, "unstake", account.address)

            try:
                handled = {"done": False}
                wd_token = watchdog_token
                tx_task = asyncio.create_task(
                    asyncio.to_thread(
                        self._with_rpc_fallback,
                        action="unstake",
                        rpc=self.rpc,
                        source_address=account.address,
                        require_stake_support=True,
                        fn=lambda r: unstake_xtz(
                            r,
                            key,
                            amount,
                            fee_mutez=fee_mutez,
                            gas_limit=gas_limit,
                            storage_limit=storage_limit,
                        ),
                    )
                )

                def _late_done(task: "asyncio.Task") -> None:
                    if handled["done"]:
                        return
                    if wd_token is not None and self._tx_watchdog_token == wd_token:
                        return
                    try:
                        _, late_oph = task.result()
                    except _FLOW_TASK_EXCEPTIONS as e:
                        log_warning("Unstake task failed after UI timeout", exception=e, address=account.address)
                        return
                    try:
                        self._add_pending_tx(
                            address=account.address,
                            oph=late_oph,
                            direction="UST",
                            amount_xtz=amount,
                            counterparty="The baker",
                            kind="transaction",
                            entrypoint="unstake",
                            history_delay_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                            processing_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                            select_wallet=False,
                        )
                        self._schedule_after(60.0, lambda: self._silent_refresh_history_for(account.address))
                    except _UI_CALLBACK_EXCEPTIONS as e:
                        log_warning("Failed to apply late unstake UI update", exception=e, address=account.address)

                tx_task.add_done_callback(lambda t: self._ui(_late_done, t))

                _, op_hash = await asyncio.wait_for(
                    asyncio.shield(tx_task),
                    timeout=Config.TX_RPC_HARD_TIMEOUT_SECONDS,
                )
                handled["done"] = True
            except asyncio.TimeoutError:
                if watchdog_token is not None:
                    self._ui(self._tx_watchdog_fire, watchdog_token, "unstake", account.address)
                self._ui(self._stop_breathing_effect)
                self._ui(self._set_busy, False)
                return
            finally:
                if watchdog_token is not None:
                    self._ui(self._stop_tx_watchdog, watchdog_token)
                    watchdog_token = None

            remaining = self._tx_flow_remaining_or_default(flow_start)
            baker_label = "The baker"
            self._ui(
                self._add_pending_tx,
                address=account.address,
                oph=op_hash,
                direction="UST",
                amount_xtz=amount,
                counterparty=baker_label,
                kind="transaction",
                entrypoint="unstake",
                history_delay_seconds=0.0,
                processing_seconds=remaining,
            )
            # Resolve the actual baker address without blocking the UI.
            self.run_worker(
                lambda oph=op_hash, addr=account.address: self._resolve_delegate_for_pending(oph, addr),
                exclusive=False,
                thread=True,
            )

            self._ui(setattr, self, "_status_lock_until_refresh", True)
            # Keep breathing until the pending row resolves (synced with shimmer),
            # then stop breathing in the finalizer.
            self._ui(
                self._set_status,
                f"⏳ Unstake submitted - waiting for inclusion ({format_xtz(amount)} XTZ)",
                force=True,
            )
            baked_by_box = {"label": None}
            def _resolve_label() -> None:
                baked_by_box["label"] = self._resolve_baked_by_label(
                    self.rpc,
                    op_hash,
                    wait_seconds=remaining,
                )
            self.run_worker(_resolve_label, exclusive=False, thread=True)

            def _finish_unstake_status() -> None:
                self._stop_breathing_effect()
                self._set_busy(False)
                label = baked_by_box["label"]
                baked_msg = get_send_baked_message(label)
                self._set_status_styled(
                    f"⚰️ Unstaked {format_xtz(amount)} XTZ — {baked_msg}",
                    style="unstake",
                    duration=0.0,
                    force=True,
                )

            # Slight delay so the history row can flip from PROCESSING -> UNSTAKED first.
            self._ui(self.set_timer, remaining + 0.05, _finish_unstake_status)
            # Safety net: if finalize callback is skipped, do not leave breathing forever.
            self._ui(self._schedule_after, remaining + 5.0, lambda: self._tx_finalize_failsafe("unstake", account.address))
            self._ui(self._schedule_after, remaining, lambda: self._refresh_account_status_only(account.address))
            self._ui(self._schedule_after, remaining + 60.0, lambda: self._silent_refresh_history_for(account.address))

        except asyncio.CancelledError:
            if breathing_started:
                self._ui(self._stop_breathing_effect)
                self._ui(self._set_busy, False)
            if watchdog_token is not None:
                self._ui(self._stop_tx_watchdog, watchdog_token)
            raise
        except _FLOW_TASK_EXCEPTIONS as e:

            error_msg = str(e)
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."

            self._ui(self._stop_breathing_effect)
            self._ui(self._set_busy, False)
            self._ui(self._set_status_styled, f"❌ Unstaking failed: {error_msg}", style="error", duration=6.0)

    async def _handle_delegate_action(self, stake_data: dict) -> None:
        """Handle delegation operation with passphrase from app level."""
        account = stake_data.get("account")
        baker_address = stake_data.get("baker_address")
        baker_name = stake_data.get("baker_name", "Unknown Baker")

        if not account or not baker_address:
            log_error("Invalid delegation data received", stake_data=stake_data)
            self._set_status("❌ Invalid delegation data")
            return


        baker_display = self._format_baker_label(baker_address)
        if baker_name and baker_name != "Unknown Baker":
            baker_display = baker_name

        key = stake_data.get("key")
        fee_mutez = stake_data.get("fee_mutez")
        gas_limit = stake_data.get("gas_limit")
        storage_limit = stake_data.get("storage_limit")

        if key is None:
            error_note = ""
            while True:
                passphrase = await self.push_screen_wait(
                    WarningPassphraseScreen(
                        "Enter Your Encryption Password",
                        password=True,
                        placeholder="Your wallet encryption password",
                        wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                        ok_label="Next →",
                        fun_note="Delegate like a boss! Your XTZ will thank you! 🎯",
                        show_back_button=True,
                        error_note=error_note,
                    )
                )

                if passphrase == BACK_NAV_MARKER:
                    await self._open_stake_flow({"account": account, "action": "delegate"})
                    return

                if not passphrase:
                    self._set_status("⏸️ Delegation cancelled")
                    return

                try:
                    secret_key = decrypt_secret(account.enc, passphrase)
                    key = key_from_encoded_secret(secret_key)
                except InvalidTag:
                    error_note = "❌ Wrong encryption password. Try again."
                    continue
                except (ValueError, TypeError) as decrypt_err:
                    raise RuntimeError("Malformed encrypted wallet data") from decrypt_err

                fee_result = await self.push_screen_wait(
                    ConfirmDelegateScreen(
                        self.rpc,
                        account.address,
                        baker_address,
                        show_back_button=True,
                    )
                )

                if fee_result and fee_result.get(BACK_NAV_MARKER):
                    continue

                if not fee_result or not fee_result.get("ok"):
                    self._set_status("⏸️ Delegation cancelled")
                    return

                fee_mutez = fee_result.get("fee_mutez")
                gas_limit = fee_result.get("gas_limit")
                storage_limit = fee_result.get("storage_limit")
                break
        else:
            if account.address != key.public_key_hash():
                self._set_status("❌ KEY MISMATCH!")
                return

        breathing_started = False
        watchdog_token = None
        try:
            _, can_send, _ = self._ensure_working_rpc()
            if not can_send:
                self._set_status("[red]❌ No RPC available to inject operations[/red]")
                return

            key_pkh = key.public_key_hash()
            if account.address != key_pkh:
                self._set_status("❌ KEY MISMATCH!")
                return

            # Ensure the source wallet is selected and its history is visible immediately.
            self._focus_history_on_address(account.address, ensure_loaded=True)

            flow_start = time.time()
            self._ui(
                self._start_breathing_effect,
                "⏳ Delegating... This may take a moment...",
                bright_class="status-warning",
                dim_class="status-warning-dim",
            )
            self._ui(self._set_busy, True)
            await asyncio.sleep(0)
            breathing_started = True
            watchdog_token = self._ui(self._start_tx_watchdog, "delegate", account.address)

            try:
                handled = {"done": False}
                wd_token = watchdog_token
                tx_task = asyncio.create_task(
                    asyncio.to_thread(
                        self._with_rpc_fallback,
                        action="delegate",
                        rpc=self.rpc,
                        fn=lambda r: delegate_to_baker(
                            r,
                            key,
                            baker_address,
                            fee_mutez=fee_mutez,
                            gas_limit=gas_limit,
                            storage_limit=storage_limit,
                        ),
                    )
                )

                def _late_done(task: "asyncio.Task") -> None:
                    if handled["done"]:
                        return
                    if wd_token is not None and self._tx_watchdog_token == wd_token:
                        return
                    try:
                        _, late_oph = task.result()
                    except _FLOW_TASK_EXCEPTIONS as e:
                        log_warning("Delegation task failed after UI timeout", exception=e, address=account.address)
                        return
                    try:
                        self._add_pending_tx(
                            address=account.address,
                            oph=late_oph,
                            direction="DEL",
                            amount_xtz=Decimal(0),
                            counterparty=baker_display,
                            kind="delegation",
                            entrypoint="delegation",
                            history_delay_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                            processing_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                            select_wallet=False,
                        )
                        self._schedule_after(60.0, lambda: self._silent_refresh_history_for(account.address))
                    except _UI_CALLBACK_EXCEPTIONS as e:
                        log_warning("Failed to apply late delegation UI update", exception=e, address=account.address)

                tx_task.add_done_callback(lambda t: self._ui(_late_done, t))

                _, op_hash = await asyncio.wait_for(
                    asyncio.shield(tx_task),
                    timeout=Config.TX_RPC_HARD_TIMEOUT_SECONDS,
                )
                handled["done"] = True
            except asyncio.TimeoutError:
                if watchdog_token is not None:
                    self._ui(self._tx_watchdog_fire, watchdog_token, "delegate", account.address)
                self._ui(self._stop_breathing_effect)
                self._ui(self._set_busy, False)
                return
            finally:
                if watchdog_token is not None:
                    self._ui(self._stop_tx_watchdog, watchdog_token)
                    watchdog_token = None

            remaining = self._tx_flow_remaining_or_default(flow_start)
            self._ui(
                self._add_pending_tx,
                address=account.address,
                oph=op_hash,
                direction="DEL",
                amount_xtz=Decimal(0),
                counterparty=baker_display,
                kind="delegation",
                entrypoint="delegation",
                history_delay_seconds=0.0,
                processing_seconds=remaining,
            )

            self._ui(
                self._set_status,
                f"⏳ Delegation submitted to {baker_display} - waiting for inclusion...",
                force=True,
            )
            def _finish_delegate_status() -> None:
                self._stop_breathing_effect()
                self._set_busy(False)
                self._set_status_styled_locked(
                    f"✅ Delegation sent to {baker_display}! 🎯",
                    style="warning",
                )
            self._ui(self._schedule_after, remaining, _finish_delegate_status)
            self._ui(
                self._schedule_after,
                remaining + 5.0,
                lambda: self._tx_finalize_failsafe("delegate", account.address),
            )
            self._ui(self._schedule_after, remaining, lambda: self._refresh_account_status_only(account.address))
            self._ui(self._schedule_after, remaining + 60.0, lambda: self._silent_refresh_history_for(account.address))

        except asyncio.CancelledError:
            if breathing_started:
                self._ui(self._stop_breathing_effect)
                self._ui(self._set_busy, False)
            if watchdog_token is not None:
                self._ui(self._stop_tx_watchdog, watchdog_token)
            raise
        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Delegation failed", exception=e)
            self._ui(self._stop_breathing_effect)
            self._ui(self._set_busy, False)
            error_msg = str(e).strip()
            if not error_msg:
                error_msg = "Unknown error (check logs)"
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."

            self._ui(self._set_status_styled, f"❌ Delegation failed: {error_msg}", style="error", duration=6.0)

    async def _handle_change_baker_action(self, stake_data: dict, *, from_stake_screen: bool = False) -> bool:
        """Handle change-baker operation (delegation under the hood) with a dedicated confirm screen."""
        account = stake_data.get("account")
        new_baker_address = stake_data.get("baker_address")
        current_baker_address = stake_data.get("current_baker") or ""
        pre_change_staked_mutez = 0

        if not account or not new_baker_address:
            log_error("Invalid change_baker data received", stake_data=stake_data)
            self._set_status("❌ Invalid change baker data")
            return False

        # Preflight: refresh current delegate from chain to handle external changes.
        try:
            state = await asyncio.to_thread(
                get_wallet_chain_state,
                self.rpc,
                account.address,
                force_refresh=True,
                prefer_rpc=True,
            )
            chain_current = state.get("delegate") or ""
            pre_change_staked_mutez = int(state.get("staked_mutez") or 0)
            if chain_current:
                current_baker_address = chain_current
        except _FLOW_PRECHECK_EXCEPTIONS as e:
            log_warning("Failed to preflight current baker", exception=e, address=account.address)

        if current_baker_address and current_baker_address == new_baker_address:
            self._set_status("ℹ️ Already delegated to that baker.")
            return True

        key = stake_data.get("key")
        fee_mutez = stake_data.get("fee_mutez")
        gas_limit = stake_data.get("gas_limit")
        storage_limit = stake_data.get("storage_limit")

        if key is None:
            error_note = ""
            while True:
                passphrase = await self.push_screen_wait(
                    WarningPassphraseScreen(
                        "Enter Your Encryption Password",
                        password=True,
                        placeholder="Your wallet encryption password",
                        wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                        ok_label="Next →",
                        fun_note="Switching bakers is still a delegation op (but spicier). 🔁🥐",
                        show_back_button=True,
                        error_note=error_note,
                    )
                )

                if passphrase == BACK_NAV_MARKER:
                    if from_stake_screen:
                        return False
                    await self._open_stake_flow({"account": account, "action": "change_baker"})
                    return False

                if not passphrase:
                    self._set_status("⏸️ Change baker cancelled")
                    return False

                try:
                    secret_key = decrypt_secret(account.enc, passphrase)
                    key = key_from_encoded_secret(secret_key)
                except InvalidTag:
                    error_note = "❌ Wrong encryption password. Try again."
                    continue
                except (ValueError, TypeError) as decrypt_err:
                    raise RuntimeError("Malformed encrypted wallet data") from decrypt_err

                confirm_result = await self.push_screen_wait(
                    ConfirmChangeBakerScreen(
                        rpc=self.rpc,
                        from_addr=account.address,
                        current_baker_address=current_baker_address,
                        new_baker_address=new_baker_address,
                        show_back_button=True,
                    )
                )
                if confirm_result and confirm_result.get(BACK_NAV_MARKER):
                    continue
                if not confirm_result or not confirm_result.get("ok"):
                    self._set_status("↩️ Change baker cancelled")
                    return False

                fee_mutez = confirm_result.get("fee_mutez")
                gas_limit = confirm_result.get("gas_limit")
                storage_limit = confirm_result.get("storage_limit")
                break
        else:
            if account.address != key.public_key_hash():
                self._set_status("❌ KEY MISMATCH!")
                return False
        new_baker_display = self._format_baker_label(new_baker_address)

        # Ensure the source wallet is selected and its history is visible immediately.
        self._focus_history_on_address(account.address, ensure_loaded=True)

        flow_start = time.time()
        self._ui(
            self._start_breathing_effect,
            "⏳ Changing baker... This may take a moment...",
            bright_class="status-warning",
            dim_class="status-warning-dim",
        )
        self._ui(self._set_busy, True)
        await asyncio.sleep(0)
        breathing_started = True
        watchdog_token = self._ui(self._start_tx_watchdog, "change_baker", account.address)
        op_hash = ""

        try:
            handled = {"done": False}
            wd_token = watchdog_token
            def _delegate_with_fallback(rpc: str):
                def _attempt_delegate(target_rpc: str) -> str:
                    try:
                        return delegate_to_baker(
                            target_rpc,
                            key,
                            new_baker_address,
                            fee_mutez=fee_mutez,
                            gas_limit=gas_limit,
                            storage_limit=storage_limit,
                        )
                    except Exception as e:
                        if not is_gas_exhausted_error(e):
                            raise
                        log_warning("Gas exhausted on change baker; retrying with autofill", exception=e, rpc=target_rpc)
                        try:
                            return delegate_to_baker(target_rpc, key, new_baker_address)
                        except Exception as retry_e:
                            if not is_gas_exhausted_error(retry_e):
                                raise
                            # Last resort on this RPC: force conservative high limits.
                            log_warning(
                                "Gas exhausted on change baker with autofill; retrying with safety overrides",
                                exception=retry_e,
                                rpc=target_rpc,
                            )
                            safe_fee = max(int(fee_mutez or 0), 15_000)
                            safe_gas = max(int(gas_limit or 0), 120_000)
                            return delegate_to_baker(
                                target_rpc,
                                key,
                                new_baker_address,
                                fee_mutez=safe_fee,
                                gas_limit=safe_gas,
                                storage_limit=0,
                            )
                try:
                    return _attempt_delegate(rpc)
                except Exception as e:
                    if is_gas_exhausted_error(e):
                        # Automatic multi-RPC fallback for persistent gas-exhausted errors.
                        net = network_from_rpc(rpc)
                        candidates = _MAINNET_RPC_CANDIDATES if net == "mainnet" else _GHOSTNET_RPC_CANDIDATES
                        for alt_rpc in candidates:
                            if alt_rpc == rpc:
                                continue
                            if not rpc_supports_send(alt_rpc):
                                continue
                            try:
                                log_warning(
                                    "Retrying change baker on alternate RPC after gas exhaustion",
                                    from_rpc=rpc,
                                    to_rpc=alt_rpc,
                                )
                                return _attempt_delegate(alt_rpc)
                            except Exception as alt_e:
                                if is_gas_exhausted_error(alt_e):
                                    log_warning("Alternate RPC also gas exhausted for change baker", exception=alt_e, rpc=alt_rpc)
                                    continue
                                raise
                    raise
            tx_task = asyncio.create_task(
                asyncio.to_thread(
                    self._with_rpc_fallback,
                    action="change_baker",
                    rpc=self.rpc,
                    fn=_delegate_with_fallback,
                )
            )

            def _late_done(task: "asyncio.Task") -> None:
                if handled["done"]:
                    return
                if wd_token is not None and self._tx_watchdog_token == wd_token:
                    return
                try:
                    _, late_oph = task.result()
                except asyncio.CancelledError:
                    log_warning("Change baker task cancelled after UI timeout", address=account.address)
                    return
                except Exception as e:
                    log_warning("Change baker task failed after UI timeout", exception=e, address=account.address)
                    return
                try:
                    self._add_pending_tx(
                        address=account.address,
                        oph=late_oph,
                        direction="DEL",
                        amount_xtz=Decimal(0),
                        counterparty=new_baker_display,
                        kind="delegation",
                        entrypoint="change_baker",
                        history_delay_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                        processing_seconds=Config.TX_FLOW_TOTAL_SECONDS,
                        select_wallet=False,
                    )
                    self._schedule_after(60.0, lambda: self._silent_refresh_history_for(account.address))
                except _UI_CALLBACK_EXCEPTIONS as e:
                    log_warning("Failed to apply late change-baker UI update", exception=e, address=account.address)

            tx_task.add_done_callback(lambda t: self._ui(_late_done, t))

            _, op_hash = await asyncio.wait_for(
                asyncio.shield(tx_task),
                timeout=Config.TX_RPC_HARD_TIMEOUT_SECONDS,
            )
            handled["done"] = True
        except asyncio.TimeoutError:
            if watchdog_token is not None:
                self._ui(self._tx_watchdog_fire, watchdog_token, "change_baker", account.address)
            self._ui(self._stop_breathing_effect)
            self._ui(self._set_busy, False)
            return False
        except asyncio.CancelledError:
            # Keep UI consistent if the task is cancelled by the event loop/worker lifecycle.
            self._ui(self._stop_breathing_effect)
            self._ui(self._set_busy, False)
            if watchdog_token is not None:
                self._ui(self._stop_tx_watchdog, watchdog_token)
                watchdog_token = None
            return False
        except Exception as e:
            log_error("Change baker failed", exception=e)
            if is_gas_exhausted_error(e):
                log_warning(
                    "Retrying change baker with final autofill fallback",
                    address=account.address,
                    rpc=self.rpc,
                )
                try:
                    _, op_hash = await asyncio.to_thread(
                        self._with_rpc_fallback,
                        action="delegate",
                        rpc=self.rpc,
                        fn=lambda r: delegate_to_baker(r, key, new_baker_address),
                    )
                    log_info(
                        "Change baker succeeded via final autofill fallback",
                        address=account.address,
                        op_hash=op_hash,
                    )
                except Exception as fallback_e:
                    log_error("Final change baker fallback failed", exception=fallback_e)
                    self._ui(self._stop_breathing_effect)
                    self._ui(self._set_busy, False)
                    error_msg = (
                        "Gas limit exhausted on this RPC after automatic fallback. "
                        "Try again in a moment or switch RPC."
                    )
                    if len(error_msg) > 150:
                        error_msg = error_msg[:150] + "..."
                    self._ui(self._set_status_styled, f"❌ Change baker failed: {error_msg}", style="error", duration=6.0)
                    return False
            else:
                self._ui(self._stop_breathing_effect)
                self._ui(self._set_busy, False)
                error_msg = str(e).strip() or "Unknown error (check logs)"
                if len(error_msg) > 150:
                    error_msg = error_msg[:150] + "..."
                self._ui(self._set_status_styled, f"❌ Change baker failed: {error_msg}", style="error", duration=6.0)
                return False
        finally:
            if watchdog_token is not None:
                self._ui(self._stop_tx_watchdog, watchdog_token)
                watchdog_token = None

        remaining = self._tx_flow_remaining_or_default(flow_start)
        self._ui(
            self._add_pending_tx,
            address=account.address,
            oph=op_hash,
            direction="DEL",
            amount_xtz=Decimal(0),
            counterparty=new_baker_display,
            kind="delegation",
            entrypoint="change_baker",
            history_delay_seconds=0.0,
            processing_seconds=remaining,
        )
        self.run_worker(
            lambda oph=op_hash, addr=account.address: self._resolve_delegate_for_pending(oph, addr),
            exclusive=False,
            thread=True,
        )

        # Fast local cache hint for StakeScreen reopen: after changing baker, existing stake
        # transitions to unstaking and cannot be re-staked until finalization.
        if pre_change_staked_mutez > 0:
            cached = self._stake_wallet_info_cache.get(account.address) or {}
            cached["delegate_addr"] = new_baker_address
            cached["staked_mutez"] = 0
            cached["unstaked_mutez"] = max(int(cached.get("unstaked_mutez") or 0), pre_change_staked_mutez)
            cached["staking_active"] = True
            cached["fetched_at"] = time.time()
            self._stake_wallet_info_cache[account.address] = cached

        self._ui(
            self._set_status,
            "⏳ Baker change submitted. Previous stake (if any) is now unstaking until finalization...",
            force=True,
        )

        def _finish_change_baker_status() -> None:
            self._stop_breathing_effect()
            self._set_busy(False)
            if pre_change_staked_mutez > 0:
                self._set_status_styled_locked(
                    "✅ Baker changed. Previous stake is now unstaking; restake after finalization.",
                    style="warning",
                )
            else:
                self._set_status_styled_locked("✅ Baker changed. Fresh oven, fresh rewards.", style="warning")

        self._ui(self._schedule_after, remaining, _finish_change_baker_status)
        self._ui(
            self._schedule_after,
            remaining + 5.0,
            lambda: self._tx_finalize_failsafe("change_baker", account.address),
        )
        self._ui(self._schedule_after, remaining, lambda: self._refresh_account_status_only(account.address))
        self._ui(self._schedule_after, remaining + 60.0, lambda: self._silent_refresh_history_for(account.address))
        return True

    def action_show_address(self) -> None:
        """Show full address details in a modal."""
        self._status_lock_until_refresh = False
        if not self.selected:
            self._set_status("ℹ️ No account selected")
            return
        self.push_screen(AddressDetailScreen(self.selected.name, self.selected.address))

    @work(exclusive=True)
    async def action_backup(self) -> None:
        """Create a timestamped encrypted backup (single wallet or all)."""
        self._status_lock_until_refresh = False
        if not self.accounts:
            self._ui(self._set_status, "🥐 Back up the void? Import a wallet first. ¬_¬")
            return

        try:
            selected_account = None
            selected_accounts: list[Account] = []

            selection = await self.push_screen_wait(BackupMultiSelectorScreen(self.accounts))
            if not selection:
                self._ui(self._set_status, "📦 Backup cancelled - Recipe stays in the kitchen! 🍳")
                return

            mode = selection.get("mode")
            if mode == "selected":
                selected_accounts = selection.get("accounts") or []
                if len(selected_accounts) == 1:
                    selected_account = selected_accounts[0]
            elif mode != "all":
                self._ui(self._set_status, "📦 Backup cancelled - Recipe stays in the kitchen! 🍳")
                return

            passphrase = (selection.get("passphrase") or "").strip()
            confirm_passphrase = (selection.get("confirm") or "").strip()
            if not passphrase or confirm_passphrase != passphrase:
                self._ui(self._set_status, "❌ Backup cancelled - Encryption password mismatch")
                return

            # Create backup directory
            backup_dir = Path(selection.get("backup_dir") or "data/backups").expanduser()
            if backup_dir.is_file():
                backup_dir = backup_dir.parent
            ensure_private_dir(backup_dir)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if selected_account:
                wallet_name = selected_account.name.replace(" ", "_")
                backup_filename = f"wallet_{wallet_name}_{timestamp}.json"
            elif selected_accounts:
                backup_filename = f"wallets_selected_{timestamp}.json"
            else:
                backup_filename = f"wallets_backup_{timestamp}.json"
            backup_path = backup_dir / backup_filename

            # Create backup structure
            if selected_account:
                wallet_data = None
                accounts_data = self.store.get("accounts", [])
                for acc_data in accounts_data:
                    if acc_data.get("address") == selected_account.address:
                        wallet_data = acc_data
                        break
                if not wallet_data:
                    self._ui(self._set_status, f"❌ Wallet data not found for {selected_account.name}")
                    return
                payload = {
                    "wallet": wallet_data,
                    "recent_destinations": self.recent_to_by_wallet.get(selected_account.address, []),
                }
                backup_type_label = "single_wallet_encrypted"
            elif selected_accounts:
                wanted = {acc.address for acc in selected_accounts}
                accounts_data = [a for a in self.store.get("accounts", []) if a.get("address") in wanted]
                payload = {
                    "accounts": accounts_data,
                    "recent_to_by_wallet": {k: v for k, v in self.recent_to_by_wallet.items() if k in wanted},
                }
                backup_type_label = "multi_wallets_encrypted"
            else:
                payload = {
                    "accounts": self.store.get("accounts", []),
                    "recent_to_by_wallet": self.recent_to_by_wallet,
                }
                backup_type_label = "all_wallets_encrypted"

            payload_json = json.dumps(payload, ensure_ascii=False)
            blob = encrypt_secret(payload_json, passphrase)

            backup_content = {
                "backup_timestamp": timestamp,
                "backup_type": backup_type_label,
                "encrypted": True,
                "blob": {
                    "salt_b64": blob.salt_b64,
                    "nonce_b64": blob.nonce_b64,
                    "ct_b64": blob.ct_b64,
                },
            }

            # Write backup file with private permissions.
            write_private_json_atomic(backup_path, backup_content, indent=2, ensure_ascii=False)

            # Get file size for confirmation
            size_kb = backup_path.stat().st_size / 1024
            # Get absolute path for display
            abs_backup_path = backup_path.resolve()

            if selected_account:
                logging.info(f"Created backup for {selected_account.name}: {backup_path}")
                backup_msg = get_message("backup_success", name=selected_account.name)
            elif selected_accounts:
                logging.info(f"Created backup for {len(selected_accounts)} wallet(s): {backup_path}")
                names = ", ".join(acc.name for acc in selected_accounts[:3])
                more = "" if len(selected_accounts) <= 3 else f" +{len(selected_accounts) - 3} more"
                if len(selected_accounts) == len(self.accounts):
                    backup_msg = f"✅ Backed up ALL wallets: {names}{more}"
                else:
                    backup_msg = f"✅ Backed up: {names}{more}"
            else:
                logging.info(f"Created backup for {len(self.accounts)} wallet(s): {backup_path}")
                names = ", ".join(acc.name for acc in self.accounts[:3])
                more = "" if len(self.accounts) <= 3 else f" +{len(self.accounts) - 3} more"
                backup_msg = f"✅ Backed up ALL wallets: {names}{more}"
            self._ui(
                self._set_status_styled,
                f"{backup_msg} ({size_kb:.1f} KB) → {abs_backup_path}",
                "warning",
                5.0,
            )
            return

        except _LOCAL_IO_EXCEPTIONS + (ValueError, TypeError) as e:
            log_error("Backup failed", exception=e)
            self._ui(self._set_status_styled, f"❌ Backup failed: {e}", "error", 5.0)

    @work(exclusive=True)
    async def action_delete_wallet(self) -> None:
        """Delete a wallet after selection and confirmation."""
        self._status_lock_until_refresh = False
        if not self.accounts:
            self._set_status("🥐 Can't delete nothing. Import a wallet first. ¬_¬")
            return

        selected_accounts = await self.push_screen_wait(DeleteMultiSelectorScreen(self.accounts))
        if not selected_accounts:
            self._set_status("🔥 Delete cancelled - Saved from the flames! 😅")
            return

        count = len(selected_accounts)
        names = ", ".join(acc.name for acc in selected_accounts[:3])
        more = "" if count <= 3 else f" +{count - 3} more"
        confirmed = await self.push_screen_wait(
            ConfirmScreen(
                f"Delete {count} wallet(s)?\n\n"
                f"[dim]{names}{more}[/dim]\n\n"
                f"[yellow]⚠️ This will burn the wallet(s) out of the app.[/yellow]\n"
                f"[yellow]No unburning. 🔥🍞[/yellow]\n\n"
                f"[dim](This only removes local data, not on-chain)[/dim]",
                title="🔥 Burn Wallets?",
                yes_label="Burn It! 🔥",
                no_label="No, Keep Them!"
            )
        )
        if not confirmed:
            self._set_status("🔥 Delete cancelled - Wallets saved from the flames! 😅")
            return

        # Remove from accounts list
        try:
            accounts_data = self.store.get("accounts", [])
            delete_addrs = {acc.address for acc in selected_accounts}
            accounts_data = [a for a in accounts_data if a.get("address") not in delete_addrs]
            self.store["accounts"] = accounts_data
            save_store(self.store)

            # Reload accounts
            self.accounts = list_accounts(self.store)

            # Clear selection only if we deleted the currently selected wallet
            if self.selected and self.selected.address in delete_addrs:
                self.selected = None
                # Clear UI
                self._update_status_balance()
                self._render_history([])

            # Show success message first
            logging.info(f"Deleted {len(delete_addrs)} wallet(s)")
            if count == 1:
                delete_msg = get_message("delete_success", name=selected_accounts[0].name)
            else:
                delete_msg = f"🔥 Deleted {count} wallets"
            self._set_status_styled_locked(delete_msg, style="error")

            # Wait a moment so user can see the message
            time.sleep(0.8)

            # Re-render accounts list
            self._render_accounts()

        except _LOCAL_IO_EXCEPTIONS + (ValueError, TypeError) as e:
            log_error("Failed to delete wallet", exception=e)
            self._set_status_styled(f"❌ Failed to delete wallet: {e}", style="error", duration=5.0)

    @work(exclusive=True)
    async def action_import_wallet(self) -> None:
        self._status_lock_until_refresh = False
        self._set_busy(True)
        try:
            selection = await self.push_screen_wait(ImportWizardScreen())
            if not selection:
                self._set_status(get_message("import_cancel"))
                return

            mode = selection.get("mode")
            if mode == "secret":
                await self._import_with_secret_key_data(
                    selection.get("name", ""),
                    selection.get("secret", ""),
                    selection.get("passphrase", ""),
                    selection.get("secret_passphrase", ""),
                )
            elif mode == "mnemonic":
                await self._import_with_mnemonic_data(
                    selection.get("name", ""),
                    selection.get("mnemonic", ""),
                    selection.get("bip39_passphrase", ""),
                    selection.get("passphrase", ""),
                    selection.get("derivation_path", ""),
                    int(selection.get("words") or 12),
                )
            elif mode == "watch":
                await self._import_watch_only_data(
                    selection.get("name", ""),
                    selection.get("address", ""),
                )
            elif mode == "backup":
                await self._import_from_backup_payload(selection.get("backup_data") or {})
        finally:
            self._set_busy(False)

    async def _import_from_backup(self) -> bool:
        """Import wallet from a backup JSON file."""
        try:
            # Determine backup directory
            backup_dir = Path("data/backups")
            ensure_private_dir(backup_dir)
            backup_dir_abs = backup_dir.absolute()

            # Step 1: Ask for backup file path
            backup_path_str = await self.push_screen_wait(
                PromptScreen(
                    "📦 Step 1: Backup File Path",
                    placeholder=f"{backup_dir_abs}/wallet_backup_YYYY-MM-DD.json",
                    ok_label="Next →",
                    fun_note=f"Time to reheat some fresh bread from the pantry! 🥖📂\nDefault location: {backup_dir_abs}",
                    show_back_button=True
                )
            )
            if backup_path_str == BACK_NAV_MARKER:
                return True
            if not backup_path_str:
                self._set_status("↩️ Import cancelled - Bread stays in storage! 📦")
                return False

            backup_path = Path(backup_path_str.strip()).expanduser()

            # Validate file exists
            if not backup_path.exists():
                self._set_status(f"❌ Backup file not found: {backup_path}")
                return False

            if not backup_path.is_file():
                self._set_status(f"❌ Path is not a file: {backup_path}")
                return False

            try:
                backup_size_bytes = backup_path.stat().st_size
            except _LOCAL_IO_EXCEPTIONS as e:
                log_error("Failed to read backup file metadata", exception=e)
                self._set_status(f"❌ Failed to read backup metadata: {e}")
                return False
            if backup_size_bytes > Config.BACKUP_MAX_FILE_BYTES:
                self._set_status(
                    f"❌ Backup too large ({backup_size_bytes // 1024} KB). "
                    f"Max {Config.BACKUP_MAX_FILE_BYTES // 1024} KB."
                )
                return False

            # Read and parse backup file
            self._set_status("🔍 Reading the recipe from the pantry...")
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
            except json.JSONDecodeError as e:
                log_error("Invalid JSON in backup file", exception=e)
                self._set_status(f"❌ Invalid backup file format! Recipe got soggy! 💧")
                return False
            except _LOCAL_IO_EXCEPTIONS as e:
                log_error("Failed to read backup file", exception=e)
                self._set_status(f"❌ Failed to read backup: {e}")
                return False

            # Validate backup structure
            if not isinstance(backup_data, dict):
                self._set_status("❌ Invalid backup: Not a valid recipe book! 📖")
                return False

            if backup_data.get("encrypted"):
                backup_type = backup_data.get("backup_type")
                passphrase = await self.push_screen_wait(
                    PromptScreen(
                        "🔐 Backup Encryption Password",
                        placeholder="Enter backup encryption password",
                        password=True,
                        ok_label="Unlock →",
                        fun_note="Unlock the recipe book.",
                        show_back_button=True,
                    )
                )
                if passphrase == BACK_NAV_MARKER:
                    return True
                if not passphrase:
                    self._set_status("↩️ Import cancelled - Bread stays in storage! 📦")
                    return False

                blob_dict = backup_data.get("blob") or {}
                try:
                    blob = EncryptedBlob(
                        salt_b64=blob_dict.get("salt_b64", ""),
                        nonce_b64=blob_dict.get("nonce_b64", ""),
                        ct_b64=blob_dict.get("ct_b64", ""),
                    )
                    payload_json = decrypt_secret(blob, passphrase)
                    if len(payload_json.encode("utf-8")) > Config.BACKUP_MAX_DECRYPTED_BYTES:
                        self._set_status(
                            "❌ Backup payload too large after decryption. "
                            "Import aborted for safety."
                        )
                        return False
                    backup_data = json.loads(payload_json)
                    if backup_type and not backup_data.get("backup_type"):
                        backup_data["backup_type"] = backup_type
                except _CRYPTO_DECODE_EXCEPTIONS + _LOCAL_IO_EXCEPTIONS as e:
                    log_error("Failed to decrypt backup file", exception=e)
                    self._set_status("❌ Failed to decrypt backup. Wrong encryption password?")
                    return False
            return await self._import_from_backup_payload(backup_data)

        except _FLOW_TASK_EXCEPTIONS + _LOCAL_IO_EXCEPTIONS + _CRYPTO_DECODE_EXCEPTIONS as e:
            log_error("Backup import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    async def _import_with_secret_key(self) -> bool:
        """Import wallet with secret key (auto-derives address)."""
        try:
            resp = await self.push_screen_wait(ImportSecretScreen())
            if resp and resp.get(BACK_NAV_MARKER):
                return True
            if not resp:
                self._set_status(get_message("import_cancel"))
                return False
            await self._import_with_secret_key_data(
                resp.get("name", ""),
                resp.get("secret", ""),
                resp.get("passphrase", ""),
                resp.get("secret_passphrase", ""),
            )
            return False

        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Secret key import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    async def _import_watch_only(self) -> bool:
        """Import watch-only wallet (no secret key)."""
        try:
            resp = await self.push_screen_wait(ImportWatchScreen())
            if resp and resp.get(BACK_NAV_MARKER):
                return True
            if not resp:
                self._set_status(get_message("import_cancel"))
                return False
            await self._import_watch_only_data(resp.get("name", ""), resp.get("address", ""))
            return False

        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Watch-only import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    def _require_import_field(self, value: str, cancel_status: str) -> Optional[str]:
        normalized = (value or "").strip()
        if normalized:
            return normalized
        self._set_status(cancel_status)
        return None

    def _validate_import_account_address(self, addr: str, *, allow_kt1: bool = False) -> Optional[str]:
        normalized = (addr or "").strip()
        valid, err = validate_tezos_address(normalized, allow_kt1=allow_kt1)
        if not valid:
            self._set_status(f"❌ Invalid account address: {err}")
            return None
        return normalized

    async def _import_with_secret_key_data(
        self,
        name: str,
        secret: str,
        pw: str,
        secret_passphrase: str = "",
    ) -> None:
        name = self._require_import_field(name, "↩️ Import cancelled - Name required! 🏷️")
        if name is None:
            return
        secret = self._require_import_field(secret, "↩️ Import cancelled - No secret key provided! 🌾")
        if secret is None:
            return
        pw = pw or ""
        secret_passphrase = secret_passphrase or ""
        if not pw:
            self._set_status("↩️ Import cancelled - Password required! 🔐")
            return

        if secret.startswith("edesk") and not secret_passphrase:
            self._set_status("↩️ Import cancelled - Passphrase required for encrypted secret key! 🔐")
            return

        self._set_status("🔮 Deriving your address from the secret key...")
        try:
            key = key_from_encoded_secret(secret, passphrase=secret_passphrase)
            addr = key.public_key_hash()
            self._set_status(f"✨ Address derived: {addr}")
        except _FLOW_PRECHECK_EXCEPTIONS + (AttributeError,) as e:
            log_error("Failed to derive address from secret key", exception=e)
            self._set_status(f"❌ Invalid secret key! Can't bake bread with bad flour! 😅 Error: {e}")
            return

        enc = encrypt_secret(secret, pw)
        upsert_account(self.store, Account(name=name, address=addr, enc=enc))
        save_store(self.store)
        self._render_accounts()
        self._select_account_by_address(addr)

        success_msg = get_message("import_secret", name=name)
        self._set_status_styled_locked(
            f"✓ {success_msg} Full wallet powers unlocked! 🔥",
            style="info",
        )

    async def _import_with_mnemonic_data(
        self,
        name: str,
        mnemonic: str,
        bip39_pass: str,
        pw: str,
        derivation_path: str,
        expected_words: int,
    ) -> None:
        name = self._require_import_field(name, "↩️ Import cancelled - Name required! 🏷️")
        if name is None:
            return
        mnemonic = self._require_import_field(mnemonic, "↩️ Import cancelled - Mnemonic required! 🧠")
        if mnemonic is None:
            return
        bip39_pass = bip39_pass or ""
        pw = pw or ""
        derivation_path = (derivation_path or "").strip()
        if not pw:
            self._set_status("↩️ Import cancelled - Password required! 🔐")
            return

        try:
            from mnemonic import Mnemonic
        except ImportError:
            self._set_status("❌ Missing 'mnemonic' package. Install dependencies.")
            return

        words = [w for w in mnemonic.split() if w.strip()]
        if len(words) != expected_words:
            self._set_status(f"❌ Mnemonic must be exactly {expected_words} words.")
            return
        if not Mnemonic("english").check(" ".join(words)):
            self._set_status("❌ Invalid mnemonic words.")
            return

        try:
            key = key_from_mnemonic_ledger(" ".join(words), bip39_pass, derivation_path)
            secret = key.secret_key()
            addr = key.public_key_hash()
        except _FLOW_PRECHECK_EXCEPTIONS + (AttributeError,) as e:
            log_error("Failed to derive key from mnemonic", exception=e)
            self._set_status(f"❌ Failed to derive key from mnemonic: {e}")
            return

        enc = encrypt_secret(secret, pw)
        upsert_account(self.store, Account(name=name, address=addr, enc=enc))
        save_store(self.store)
        self._render_accounts()
        self._select_account_by_address(addr)

        self._set_status_styled_locked(
            "✓ Mnemonic imported — oven preheated and ready! 🔥",
            style="info",
        )

    async def _import_watch_only_data(self, name: str, addr: str) -> None:
        name = self._require_import_field(name, "↩️ Import cancelled - Name required! 🏷️")
        if name is None:
            return
        if not (addr or "").strip():
            self._set_status("↩️ Import cancelled - Address required! 🥐")
            return
        addr_validated = self._validate_import_account_address(addr, allow_kt1=False)
        if addr_validated is None:
            return
        addr = addr_validated

        upsert_account(self.store, Account(name=name, address=addr, enc=None))
        save_store(self.store)
        self._render_accounts()
        self._select_account_by_address(addr)

        success_msg = get_message("import_watch", name=name)
        self._set_status_styled_locked(
            f"✓ {success_msg} Watch-only mode activated! 🥖",
            style="info",
        )

    def _validate_backup_wallet_address(self, addr: Any) -> Optional[str]:
        normalized = (addr or "").strip()
        if not normalized:
            self._set_status("❌ Invalid backup: Missing address in wallet data!")
            return None
        valid, err = validate_tezos_address(normalized, allow_kt1=False)
        if not valid:
            self._set_status(f"❌ Invalid address in backup: {err}")
            return None
        return normalized

    def _parse_backup_enc_blob(self, enc: Any) -> tuple[bool, Optional[EncryptedBlob]]:
        if enc is None:
            return True, None
        if not isinstance(enc, dict):
            self._set_status("❌ Invalid backup: encrypted wallet payload is malformed.")
            return False, None
        required = ("salt_b64", "nonce_b64", "ct_b64")
        if any(not isinstance(enc.get(k), str) or not enc.get(k) for k in required):
            self._set_status("❌ Invalid backup: encrypted wallet payload is incomplete.")
            return False, None
        try:
            return True, EncryptedBlob(
                salt_b64=enc["salt_b64"],
                nonce_b64=enc["nonce_b64"],
                ct_b64=enc["ct_b64"],
            )
        except (TypeError, ValueError, KeyError) as e:
            log_error("Failed to parse encrypted wallet payload from backup", exception=e)
            self._set_status("❌ Invalid backup: encrypted wallet payload is corrupted.")
            return False, None

    def _sanitize_backup_recent_destinations(self, recent_dests: Any) -> list[str]:
        if not isinstance(recent_dests, list):
            return []
        sanitized: list[str] = []
        for item in recent_dests:
            if not isinstance(item, str):
                continue
            candidate = item.strip()
            if not candidate:
                continue
            valid, _ = validate_tezos_address(candidate, allow_kt1=True)
            if not valid or candidate in sanitized:
                continue
            sanitized.append(candidate)
            if len(sanitized) >= Config.RECENT_DESTINATIONS_MAX:
                break
        return sanitized

    def _sanitize_backup_recent_map(self, recent_map: Any) -> dict[str, list[str]]:
        if not isinstance(recent_map, dict):
            return {}
        sanitized: dict[str, list[str]] = {}
        for raw_addr, recent_dests in recent_map.items():
            if not isinstance(raw_addr, str):
                continue
            addr = raw_addr.strip()
            valid, _ = validate_tezos_address(addr, allow_kt1=False)
            if not valid:
                continue
            safe_dests = self._sanitize_backup_recent_destinations(recent_dests)
            if safe_dests:
                sanitized[addr] = safe_dests
            if len(sanitized) >= Config.BACKUP_MAX_ACCOUNTS:
                break
        return sanitized

    def _finalize_backup_wallet_import(self, *, name: str, addr: str, enc: Optional[EncryptedBlob], backup_data: dict) -> None:
        upsert_account(self.store, Account(name=name, address=addr, enc=enc))

        recent_dests = backup_data.get("recent_destinations", [])
        safe_recent_dests = self._sanitize_backup_recent_destinations(recent_dests)
        if safe_recent_dests:
            self.recent_to_by_wallet[addr] = safe_recent_dests

        save_store(self.store)
        self._render_accounts()
        self._select_account_by_address(addr)

        success_msg = get_message("import_backup", name=name)
        if enc:
            backup_msg = "Restored pastry with full powers! Ready to send! 🔥"
        else:
            backup_msg = "Restored as display-only! Watch mode activated! 👀"
        self._set_status_styled_locked(
            f"✓ {success_msg} {backup_msg} ✨",
            style="info",
        )
        logging.info(f"Imported wallet from backup: {name} ({addr})")

    def _extract_backup_wallet_data(
        self,
        backup_data: dict,
    ) -> Optional[tuple[str, str, Optional[EncryptedBlob]]]:
        wallet_data = backup_data.get("wallet")
        if not isinstance(wallet_data, dict):
            self._set_status("❌ Invalid backup: No wallet data found in recipe! 🤷")
            return None

        name = wallet_data.get("name", "Imported Wallet")
        if not isinstance(name, str):
            self._set_status("❌ Invalid backup: wallet name is malformed.")
            return None
        addr = wallet_data.get("address")
        ok_enc, enc = self._parse_backup_enc_blob(wallet_data.get("enc"))
        if not ok_enc:
            return None

        addr_validated = self._validate_backup_wallet_address(addr)
        if addr_validated is None:
            return None
        return name.strip() or "Imported Wallet", addr_validated, enc

    async def _import_from_backup_payload(self, backup_data: dict) -> bool:
        """Import from already parsed (and decrypted) backup data."""
        try:
            if not isinstance(backup_data, dict) or not backup_data:
                self._set_status("❌ Invalid backup: Not a valid recipe book! 📖")
                return False

            if backup_data.get("backup_type") in ("all_wallets_encrypted", "multi_wallets_encrypted"):
                accounts_data = backup_data.get("accounts", [])
                if not isinstance(accounts_data, list) or not accounts_data:
                    self._set_status("❌ Invalid backup: No accounts found.")
                    return False
                if len(accounts_data) > Config.BACKUP_MAX_ACCOUNTS:
                    self._set_status(
                        f"❌ Backup has too many wallets ({len(accounts_data)}). "
                        f"Max allowed is {Config.BACKUP_MAX_ACCOUNTS}."
                    )
                    return False

                imported = 0
                skipped = 0
                first_addr = ""
                for acc_data in accounts_data:
                    if not isinstance(acc_data, dict):
                        skipped += 1
                        continue
                    addr = self._validate_backup_wallet_address(acc_data.get("address"))
                    if addr is None:
                        skipped += 1
                        continue
                    name = acc_data.get("name", "Imported Wallet")
                    if not isinstance(name, str):
                        skipped += 1
                        continue
                    ok_enc, enc = self._parse_backup_enc_blob(acc_data.get("enc"))
                    if not ok_enc:
                        skipped += 1
                        continue
                    upsert_account(self.store, Account(name=name, address=addr, enc=enc))
                    if not first_addr:
                        first_addr = addr
                    imported += 1

                if imported == 0:
                    self._set_status("❌ Backup contains no valid wallet entries.")
                    return False

                recent_map = backup_data.get("recent_to_by_wallet", {})
                self.recent_to_by_wallet.update(self._sanitize_backup_recent_map(recent_map))

                save_store(self.store)
                self._render_accounts()
                if first_addr:
                    self._select_account_by_address(first_addr)

                self._set_status_styled_locked(
                    f"✅ Restored {imported} wallet(s). Skipped {skipped}.",
                    style="info",
                )
                logging.info(f"Imported {imported} wallet(s) from backup")
                return False

            if backup_data.get("backup_type") == "single_wallet_encrypted":
                extracted = self._extract_backup_wallet_data(backup_data)
                if extracted is None:
                    return False
                name, addr, enc = extracted

                for existing in self.accounts:
                    if existing.address == addr:
                        self._set_status(f"⚠️ Wallet with address {addr} already exists!")
                        return False

                self._set_status(f"✨ Found wallet: {name}")
                new_name = await self.push_screen_wait(
                    PromptScreen(
                        "📝 Confirm/Rename Wallet",
                        placeholder=name,
                        ok_label="🥖 Import!",
                        wallet_info=f"[b cyan]Original:[/b cyan] {name} | [b cyan]Address:[/b cyan] {addr[:10]}...{addr[-8:]}",
                        fun_note="Keep the name or give it a fresh label!",
                    )
                )
                if new_name:
                    name = new_name.strip()

                if not name:
                    self._set_status("↩️ Import cancelled - Nameless bread stays in the pantry! 🏷️")
                    return False

                self._finalize_backup_wallet_import(name=name, addr=addr, enc=enc, backup_data=backup_data)
                return False

            extracted = self._extract_backup_wallet_data(backup_data)
            if extracted is None:
                return False
            name, addr, enc = extracted

            self._finalize_backup_wallet_import(name=name, addr=addr, enc=enc, backup_data=backup_data)
            return False
        except _FLOW_TASK_EXCEPTIONS + _LOCAL_IO_EXCEPTIONS + _CRYPTO_DECODE_EXCEPTIONS as e:
            log_error("Backup import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    @work(exclusive=True)
    async def action_send(self) -> None:
        """Simplified send flow using unified SendScreen with back navigation."""
        self._status_lock_until_refresh = False
        if self._send_in_progress:
            self._set_status("⏳ Send operation already in progress…")
            return
        if not self.accounts:
            self._set_status("🥐 You can't send what you don't have—yet, son. Import a wallet first. ¬_¬")
            return

        wallet_recents = self._get_recent_to_for_wallet(self.selected.address) if self.selected else []
        send_data = await self.push_screen_wait(SendScreen(self.accounts, self.rpc, wallet_recents))

        if not send_data:
            self._set_status("🚫 Send canceled — keeping my baguettes. 🥖")
            return

        from_account = send_data["from_account"]
        to_addr = send_data["to_addr"]
        amount = send_data["amount"]
        key = send_data["key"]
        try:
            key_pkh = key.public_key_hash()
            if key_pkh != from_account.address:
                self._set_status(
                    "❌ KEY MISMATCH! Wallet address doesn't match decrypted key. Re-import the wallet.",
                    force=True,
                )
                return
        except _FLOW_PRECHECK_EXCEPTIONS + (AttributeError,) as e:
            log_error("Failed to validate decrypted key", exception=e, address=from_account.address)
            self._set_status("❌ Failed to validate wallet key. Try again.", force=True)
            return

        # Ensure source wallet is anchored before send flow starts.
        self._focus_history_on_address(
            from_account.address,
            ensure_loaded=True,
            refresh_details=True,
        )

        self._send_in_progress = True
        self._send_in_progress_token = time.time()
        token = self._send_in_progress_token
        if token is not None:
            self.set_timer(
                Config.SEND_FAILSAFE_SECONDS,
                lambda: self._send_failsafe(token, from_account.address),
            )
        self._send_and_refresh(
            from_account.address,
            key,
            to_addr,
            amount,
            fee_mutez=send_data.get("fee_mutez"),
            gas_limit=send_data.get("gas_limit"),
            storage_limit=send_data.get("storage_limit"),
        )
        return

    @work(exclusive=True, thread=True)
    def _send_and_refresh(
        self,
        from_addr: str,
        key,
        to_addr: str,
        amount: Decimal,
        fee_mutez: Optional[int] = None,
        gas_limit: Optional[int] = None,
        storage_limit: Optional[int] = None,
    ) -> None:
        logging.info(f"Sending {amount} XTZ from {from_addr} to {to_addr}")
        logging.debug(f"  fee_mutez={fee_mutez}, gas_limit={gas_limit}, storage_limit={storage_limit}")
        self._ui(setattr, self, "_status_lock_until_refresh", False)
        self._ui(self._set_busy, True)
        self._ui(self._clear_tx_link)  # Clear any previous transaction link

        # Pre-flight: keep the fun prep messages before the tx action starts.
        self._ui(
            self._set_status_styled,
            "🌾 Getting the dough ready…",
            style="success",
            duration=0.0,
            force=True,
        )
        self._ui(self._start_spinner, "🌾 Getting the dough ready…")
        time.sleep(0.1)
        self._ui(self._start_spinner, "🔥 Heating the oven…")
        time.sleep(0.1)
        self._ui(self._start_spinner, "👐 Kneading the dough…")
        time.sleep(0.1)

        finalize_scheduled = False
        try:
            original_rpc = self.rpc
            rpc_to_use, can_send, _ = choose_working_rpc(original_rpc)
            if not can_send:
                self._ui(self._set_status, "❌ No RPC available to inject operations")
                return

            flow_start = time.time()
            self._ui(self._stop_spinner)
            def _rpc_with_timeout(fn: Callable[[], tuple[str, Any]]) -> tuple[str, Any]:
                """
                Run a potentially-blocking RPC call with a soft + hard timeout.

                Note: we use a daemon thread so a stuck network call won't prevent
                the app from exiting cleanly.
                """
                result_q: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

                def _runner() -> None:
                    try:
                        result_q.put((True, fn()))
                    except BaseException as e:
                        result_q.put((False, e))

                t = threading.Thread(target=_runner, daemon=True)
                t.start()

                t.join(timeout=Config.TX_RPC_TIMEOUT_SECONDS)
                if t.is_alive():
                    # Soft timeout: keep breathing, but let the user know it's still working.
                    self._ui(self._set_status, "⏳ Send is taking longer than usual… still working.", force=True)
                    remaining = max(
                        0.0,
                        Config.TX_RPC_HARD_TIMEOUT_SECONDS - Config.TX_RPC_TIMEOUT_SECONDS,
                    )
                    t.join(timeout=remaining)

                if t.is_alive():
                    raise concurrent.futures.TimeoutError()

                ok, payload = result_q.get_nowait()
                if ok:
                    return payload
                raise payload
            try:
                balance_mutez = get_balance_mutez(rpc_to_use, from_addr)
                fee_guess = fee_mutez if fee_mutez is not None else 1200
                if not is_revealed(rpc_to_use, from_addr):
                    fee_guess += 1300
                total_needed = _xtz_to_mutez(amount) + int(fee_guess)
                if balance_mutez < total_needed:
                    msg = "❌ Saldo insuficiente para enviar."
                    try:
                        staked_mutez = get_staking_balance(rpc_to_use, from_addr)
                        if staked_mutez > 0:
                            msg = "❌ Saldo disponible insuficiente (tienes fondos en staking)."
                    except _FLOW_PRECHECK_EXCEPTIONS as e:
                        log_debug(
                            "Failed to read staked balance during pre-send check",
                            exception=str(e),
                            address=from_addr,
                        )
                    self._ui(self._set_status, msg, force=True)
                    return
            except _FLOW_PRECHECK_EXCEPTIONS as e:
                log_warning("Pre-send balance check failed", exception=e, address=from_addr)
            self._ui(
                self._start_breathing_effect,
                "🥐 Into the oven we go… your baker’s on it!",
                bright_class="status-success",
                dim_class="status-success-dim",
            )

            try:
                rpc_used, oph = _rpc_with_timeout(
                    lambda: self._with_rpc_fallback(
                        action="send",
                        rpc=rpc_to_use,
                        fn=lambda r: send_xtz(
                            r,
                            key,
                            to_addr,
                            amount,
                            fee_mutez=fee_mutez,
                            gas_limit=gas_limit,
                            storage_limit=storage_limit,
                        ),
                    )
                )
            except concurrent.futures.TimeoutError:
                self._ui(self._stop_breathing_effect)
                self._ui(
                    self._set_status_styled,
                    "⏳ Send timed out - check history; retry in 1-2 min if no op.",
                    style="error",
                    duration=6.0,
                    force=True,
                )
                return
            except _FLOW_TASK_EXCEPTIONS as e:
                if fee_mutez is not None or gas_limit is not None or storage_limit is not None:
                    log_warning("Send with overrides failed; retrying with autofill", exception=e)
                    try:
                        rpc_used, oph = _rpc_with_timeout(
                            lambda: self._with_rpc_fallback(
                                action="send",
                                rpc=rpc_to_use,
                                fn=lambda r: send_xtz(
                                    r,
                                    key,
                                    to_addr,
                                    amount,
                                    fee_mutez=None,
                                    gas_limit=None,
                                    storage_limit=None,
                                ),
                            )
                        )
                    except concurrent.futures.TimeoutError:
                        self._ui(self._stop_breathing_effect)
                        self._ui(
                            self._set_status_styled,
                            "⏳ Send timed out - check history; retry in 1-2 min if no op.",
                            style="error",
                            duration=6.0,
                            force=True,
                        )
                        return
                else:
                    raise
            logging.info(f"Transaction injected: {oph}")

            self._push_recent_to(from_addr, to_addr)
            baker_label_box = {"label": None}
            remaining = self._tx_flow_remaining_or_default(flow_start)
            self._ui(
                self._add_pending_tx,
                address=from_addr,
                oph=oph,
                direction="OUT",
                amount_xtz=amount,
                counterparty=to_addr,
                kind="transaction",
                entrypoint="",
                history_delay_seconds=0.0,
                processing_seconds=remaining,
            )
            # Keep breathing (green) until the processing shimmer resolves.
            self._ui(self._set_status, "⏳ Send submitted - waiting for inclusion...", force=True)
            # History prefetched earlier; pending row is added via _add_pending_tx.

            tzkt = tzkt_ui_base_from_rpc(rpc_used)
            oph_short = f"{oph[:10]}...{oph[-8:]}" if len(oph) > 20 else oph
            tzkt_link = f"{tzkt}/{oph}"

            def _finish_send() -> None:
                try:
                    self._stop_breathing_effect()
                    label = baker_label_box["label"]
                    baked_msg = get_send_baked_message(label)
                    self._set_status_styled_locked(
                        f"✅ {baked_msg}",
                        "success",
                    )
                    self._show_tx_link(oph_short, tzkt_link)
                    self._invalidate_history_cache(from_addr)
                    self._invalidate_balance_cache(from_addr)
                    self._schedule_after(60.0, lambda: self._silent_refresh_history_for(from_addr))
                    try:
                        self.query_one("#history", ListView).focus()
                    except _UI_CALLBACK_EXCEPTIONS as e:
                        log_error("Failed to focus history after send", exception=e)
                except _UI_CALLBACK_EXCEPTIONS as e:
                    log_error("Failed to finalize send status", exception=e)
                    self._set_status("✅ TX sent — check history", force=True)
                finally:
                    self._clear_account_loading(from_addr)
                    self._refresh_account_row(from_addr)
                    self._set_busy(False)
                    self._send_in_progress = False
                    self._send_in_progress_token = None

            self._ui(self._schedule_after, remaining, _finish_send)
            finalize_scheduled = True
            try:
                resolved_label = self._resolve_baked_by_label(
                    rpc_used,
                    oph,
                    wait_seconds=remaining,
                )
                baker_label_box["label"] = resolved_label
            except _FLOW_TASK_EXCEPTIONS as e:
                log_warning("Failed to resolve baked-by baker for send", exception=e, oph=oph)

        except _FLOW_TASK_EXCEPTIONS as e:
            log_error("Transaction failed", exception=e)
            self._ui(self._stop_breathing_effect)
            msg = f"❌ Baking failed: {e}"
            s = str(e)
            if "subtraction_underflow" in s:
                msg = "❌ Saldo insuficiente para enviar."
            self._ui(self._set_status, msg, force=True)
            self._ui(self._clear_tx_link)  # Clear link on error
        finally:
            if not finalize_scheduled:
                # Ensure the send lock is released even if UI callbacks fail.
                self._send_in_progress = False
                self._send_in_progress_token = None
                try:
                    self._ui(self._stop_breathing_effect)
                    self._ui(self._clear_account_loading, from_addr)
                    self._ui(self._refresh_account_row, from_addr)
                    self._ui(self._set_busy, False)
                except _UI_CALLBACK_EXCEPTIONS as e:
                    log_warning("Failed to finalize send cleanup", exception=e, address=from_addr)

    # --- Button wiring ---
    @on(Button.Pressed, "#add")
    def on_add_pressed(self) -> None:
        self.action_import_wallet()

    @on(Button.Pressed, "#refresh")
    def on_refresh_pressed(self) -> None:
        self.action_refresh()

    @on(Button.Pressed, "#send")
    def on_send_pressed(self) -> None:
        self.action_send()

    @on(Button.Pressed, "#recv")
    def on_recv_pressed(self) -> None:
        self.action_receive()

    @on(Button.Pressed, "#stake")
    def on_stake_pressed(self) -> None:
        now = time.time()
        if now < self._stake_button_cooldown_until:
            log_info("Main stake button press ignored by cooldown")
            return
        self._stake_button_cooldown_until = now + 1.5
        log_info("Main stake button pressed")
        self.action_stake()

    @on(Button.Pressed, "#backup")
    def on_backup_pressed(self) -> None:
        self.action_backup()

    @on(Button.Pressed, "#export")
    def on_export_pressed(self) -> None:
        self.action_export_history()

    @on(Button.Pressed, "#delete")
    def on_delete_pressed(self) -> None:
        self.action_delete_wallet()

    @on(Button.Pressed, "#exit")
    def on_exit_pressed(self) -> None:
        self.action_quit()


if __name__ == "__main__":
    setup_logging()
    try:
        WalletApp().run()
    except BaseException as e:
        log_error("Application crashed", exception=e)
        logging.critical(f"Application crashed: {e}", exc_info=True)
        raise
