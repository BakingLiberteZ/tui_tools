from __future__ import annotations
from decimal import Decimal
import decimal
import re
import threading
from threading import RLock
from functools import lru_cache
import urllib.request
import urllib.error
import time
import json
import webbrowser
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, ListView, ListItem, Label, Button, Input, Static, DirectoryTree, Tree

from sassy_wallet.core.store import load_store, save_store, list_accounts, upsert_account, Account
from sassy_wallet.core.crypto import encrypt_secret, decrypt_secret
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
    get_baker_info,
    get_baker_staking_balance,
    get_public_bakers,
    delegate_to_baker,
    stake_xtz,
    unstake_xtz,
)
from sassy_wallet.core.logger import log_exception, safe_log_exception, log_error, log_info, log_warning
from sassy_wallet.core.validation import (
    validate_baker_address,
    validate_tezos_address,
    validate_amount,
    validate_fee,
    validate_gas_limit,
    validate_storage_limit,
    sanitize_input,
    is_valid_tezos_address,
    is_valid_baker_address,
)
from sassy_wallet.messages.bakery import get_message, SPINNER_MESSAGES, BAKER_MESSAGES, get_baker_message, get_wallet_loading_message
from sassy_wallet.messages.staking import get_staking_message
from sassy_wallet.messages.empty_wallet import get_empty_wallet_message
from sassy_wallet.messages.balance import get_balance_message
from sassy_wallet.messages.modal import get_modal_message
from sassy_wallet.messages.baker_commentary import (
    get_baker_commentary,
    get_baker_tier_emoji,
    format_baker_balance_info,
    should_show_decentralization_warning,
    get_decentralization_recommendation,
)
from sassy_wallet.messages.baker_commentary_short import get_baker_commentary_short
from sassy_wallet.messages.send_commentary import get_recipient_comment, get_amount_comment, get_confirmation_comment
from sassy_wallet.messages.advanced_mode import get_advanced_mode_message


# --- Configuration constants ---
class Config:
    """Application configuration constants."""
    # RPC URLs
    RPC_DEFAULT_MAINNET = "https://rpc.tzkt.io/mainnet"
    RPC_DEFAULT_GHOSTNET = "https://ghostnet.tezos.marigold.dev"

    RPC_MAINNET_CANDIDATES = [
        "https://mainnet.api.tez.ie",
        "https://mainnet.smartpy.io",
        "https://mainnet.tezos.ecadinfra.com",
        # Fallbacks (may be read-only / throttled / flaky depending on policy/region):
        "https://rpc.tzbeta.net",
        "https://rpc.tzkt.io/mainnet",
    ]

    RPC_GHOSTNET_CANDIDATES = [
        "https://ghostnet.tezos.marigold.dev",
        "https://ghostnet.tezos.ecadinfra.com",
        "https://ghostnet.smartpy.io",
        "https://rpc.tzkt.io/ghostnet",
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


def _xtz_to_mutez(x: Decimal) -> int:
    return int((x * Decimal(1_000_000)).to_integral_value())


def setup_logging() -> None:
    """Configure application logging with rotation."""
    from logging.handlers import RotatingFileHandler

    # Create logs directory if it doesn't exist
    log_path = Path(Config.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(Config.LOG_LEVEL)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # File handler with rotation (NO console handler - breaks Textual UI)
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(Config.LOG_LEVEL)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)

    # Add ONLY file handler (no console output to avoid breaking Textual UI)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger (which might have StreamHandler)
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


def format_relative_time(timestamp_iso: str) -> str:
    """Format ISO timestamp as relative time (e.g., '5 min ago', '2 hours ago').

    Args:
        timestamp_iso: ISO 8601 timestamp string

    Returns:
        Relative time string or original timestamp if parsing fails
    """
    try:
        from datetime import datetime, timezone

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

    except Exception as e:
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
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=headers
            or {
                "User-Agent": "tui-tezos-wallet/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return int(getattr(resp, "status", 0) or 0)
    except urllib.error.HTTPError as e:
        try:
            return int(getattr(e, "code", 0) or 0)
        except Exception as ex:
            log_error("Failed to extract HTTP error code", exception=ex)
            return 0
    except Exception as e:
        log_error("HTTP code check failed", exception=e, url=url)
        return 0




def _fetch_json(url: str, timeout_s: float = Config.RPC_FETCH_TIMEOUT) -> Any:
    """Fetch JSON from URL (GET)."""
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "tui-tezos-wallet/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def find_baker_for_operation(rpc: str, oph: str, max_depth: int = Config.BAKER_SEARCH_MAX_DEPTH) -> Optional[str]:
    """Best-effort: find the baker of the block that included operation hash `oph`.

    Scans head, head~1, ... head~max_depth using `operation_hashes` (cheap),
    then reads the block header to get `baker`.
    """
    rpc = (rpc or "").rstrip("/")
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
        except Exception as e:
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
                except Exception as e:
                    log_error("Failed to fetch block header for baker", exception=e, block_id=block_id)
                    return None
                return None
        except Exception as e:
            log_error("Failed to search for operation in block", exception=e, block_id=block_id)
            continue

    return None
def rpc_supports_send(rpc: str) -> bool:
    url = f"{rpc.rstrip('/')}/injection/operation"
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
    url = f"{rpc.rstrip('/')}/chains/main/blocks/head/helpers/scripts/run_operation"
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
        head = _fetch_json(f"{rpc.rstrip('/')}/chains/main/blocks/head/hash")
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
            f"{rpc.rstrip('/')}/chains/main/blocks/head/helpers/forge/operations",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=Config.RPC_LONG_TIMEOUT) as resp:
            return int(getattr(resp, "status", 0) or 0) == 200
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        if "No case matched" in body and "At /kind" in body:
            return False
        log_warning("Stake support probe failed", exception=e, rpc=rpc)
        return False
    except Exception as e:
        log_warning("Stake support probe failed", exception=e, rpc=rpc)
        return False


def choose_working_rpc(current_rpc: str) -> tuple[str, bool, bool]:
    """Pick the first RPC that supports injection and (ideally) simulation.

    Returns (rpc, supports_send, supports_simulation).
    """
    net = network_from_rpc(current_rpc)
    candidates = _MAINNET_RPC_CANDIDATES if net == "mainnet" else _GHOSTNET_RPC_CANDIDATES

    # Prefer candidates order; only try current if it's not already listed.
    ordered = candidates + ([current_rpc] if current_rpc not in candidates else [])

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


class ConfirmScreen(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    CSS = """
    ConfirmScreen {
        align: center middle;
    }

    ConfirmScreen > Vertical {
        width: auto;
        min-width: 50;
        max-width: 70;
        height: auto;
        max-height: 22;
        overflow-y: auto;
        background: $surface;
        border: heavy #ef4444;
        padding: 1 2;
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
            yield Static(f"[b]{self.title}[/b]\n{self.message}", markup=True)
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
            except Exception:
                self.screen.focus_next()
            event.stop()
            return
        if key == "enter":
            try:
                if self.query_one("#no", Button).has_focus:
                    self.dismiss(False)
                else:
                    self.dismiss(True)
            except Exception:
                self.dismiss(True)
            event.stop()


class PromptScreen(ModalScreen[str]):
    CSS = """
    PromptScreen {
        align: center middle;
    }

    PromptScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
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

    @on(Input.Changed, "#inp")
    def input_changed(self, event: Input.Changed) -> None:
        pass  # Input changes handled by Textual

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
            self.dismiss("__BACK__")
        else:
            self.dismiss("")

    def on_unmount(self) -> None:
        pass

    def on_key(self, event) -> None:
        from textual.widgets import Input

        key = getattr(event, "key", None)

        # 🚫 If focus is on the Input widget, let it handle keys naturally
        # Only intercept Escape for cancel functionality
        if isinstance(self.app.focused, Input):
            if key == "ctrl+b" and self._show_back_button:
                self.dismiss("__BACK__")
                event.stop()
                return
            if key == "escape":
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
                return
            # For all other keys, let Input handle them naturally (NO event.stop())
            return


        if key == "ctrl+b" and self._show_back_button:
            self.dismiss("__BACK__")
            event.stop()
            return
        if key == "backspace" and self._show_back_button:
            self.dismiss("__BACK__")
            event.stop()
            return
        if key == "escape":
            self.dismiss("")
            event.stop()

    def dismiss(self, result=None) -> None:
        import traceback
        stack_lines = traceback.format_stack()
        # Show last 5 frames (excluding this one)
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
        # Call parent's input_changed first
        super().input_changed(event)

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

            # Show sassy comment based on amount
            comment = get_amount_comment(amount)
            comment_widget.update(f"[dim italic]{comment}[/dim italic]")
        except (ValueError, decimal.InvalidOperation):
            comment_widget.update("")


class SendPassphraseScreen(PromptScreen):
    """Prompt screen for entering passphrase for send - Green border to match SEND button."""
    CSS = """
    SendPassphraseScreen {
        align: center middle;
    }

    SendPassphraseScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #10b981;
        padding: 1 2;
    }

    SendPassphraseScreen Static {
        margin-bottom: 0;
    }

    SendPassphraseScreen #wallet_info {
        color: $accent;
        margin-bottom: 0;
    }

    SendPassphraseScreen #inp {
        margin-bottom: 0;
    }

    SendPassphraseScreen Horizontal {
        align: center middle;
    }
    """


class BackupConfirmPassphraseScreen(PromptScreen):
    """Prompt screen for confirming backup passphrase (yellow confirm button)."""
    CSS = """
    BackupConfirmPassphraseScreen #ok {
        background: #eab308;
        color: white;
    }

    BackupConfirmPassphraseScreen #ok:hover {
        background: #ca8a04;
        color: white;
    }
    """


class BackupPassphraseScreen(ModalScreen[Optional[dict]]):
    """Single-step backup passphrase + confirm."""

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
        background: #eab308;
        color: white;
    }

    BackupPassphraseScreen #ok:hover {
        background: #ca8a04;
        color: white;
    }
    """

    def __init__(self, hint: str):
        super().__init__()
        self._hint = hint

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]🔐 Backup Passphrase[/b]", id="title", markup=True)
            yield Input(placeholder="Create passphrase", password=True, id="inp_pass")
            yield Input(placeholder="Confirm passphrase", password=True, id="inp_confirm")
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
        self.dismiss({"__BACK__": True})

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
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
                return
            return
        if key == "escape":
            self.dismiss(None)
            event.stop()
            return
        if key in ("left", "right") and isinstance(self.app.focused, Button):
            parent = self.app.focused.parent
            if isinstance(parent, Horizontal):
                focusables = [c for c in parent.children if isinstance(c, Button)]
                if self.app.focused in focusables:
                    idx = focusables.index(self.app.focused)
                    if key == "left" and idx > 0:
                        focusables[idx - 1].focus()
                        event.stop()
                        return
                    if key == "right" and idx < len(focusables) - 1:
                        focusables[idx + 1].focus()
                        event.stop()
                        return
        if key == "backspace":
            self.dismiss({"__BACK__": True})
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
        # Call parent's input_changed first
        super().input_changed(event)

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
    CSS = """
    StakePassphraseScreen {
        align: center middle;
    }

    StakePassphraseScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #8b5cf6;
        padding: 1 2;
    }

    StakePassphraseScreen Static {
        margin-bottom: 0;
    }

    StakePassphraseScreen #wallet_info {
        color: $accent;
        margin-bottom: 0;
    }

    StakePassphraseScreen #inp {
        margin-bottom: 0;
    }

    StakePassphraseScreen Horizontal {
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
        baker_addr = get_delegation_info(self.rpc, self.address) or ""
        if not baker_addr:
            return "—"
        info = get_baker_info(self.rpc, baker_addr)
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

        self.query_one("#stake", Button).focus()
        self._estimate_worker()

    def on_unmount(self) -> None:
        self._stop_est_pulse()

    def _start_est_pulse(self) -> None:
        self._estimating = True
        self._est_i = 0
        if self._est_timer is None:
            self._est_timer = self.set_interval(Config.ESTIMATION_PULSE_INTERVAL, self._tick_est_pulse)

    def _stop_est_pulse(self) -> None:
        self._estimating = False
        if self._est_timer is not None:
            self._est_timer.stop()
            self._est_timer = None

    def _tick_est_pulse(self) -> None:
        if not self._estimating:
            return
        self._est_i += 1
        self._render_summary(estimating=True)
        self._update_fee_list(estimating=True)

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
                "",
                f"[b #fdba74]Fee:[/b #fdba74]       {'[reverse]estimating…[/reverse]' if ((self._est_i // 3) % 2) else '[b]estimating…[/b]'}",
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
            est = self._estimate or {}
            fee_opts = est.get("fee_options") or {}
            chosen = fee_opts.get(self._fee_choice) or {}
            chosen_total = chosen.get("total_fee_xtz")

            lines = [
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b #fdba74]Address:[/b #fdba74]   {self.address}",
                "",
                f"[b #8b5cf6]To:[/b #8b5cf6]        {self._baker_label}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
                "",
                f"[b #fdba74]Fee ({self._fee_choice}):[/b #fdba74] {format_xtz(chosen_total) if chosen_total else '0'} XTZ",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))

    def _init_fee_list(self) -> None:
        """Create the 3 fixed fee rows."""
        lv = self.query_one("#fee_list", ListView)
        lv.clear()
        self._fee_labels = []
        for _ in range(3):
            lbl = Label("")
            self._fee_labels.append(lbl)
            lv.append(ListItem(lbl))

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        """Update fee rows text + checkmark."""
        if not self._fee_labels:
            self._init_fee_list()

        if estimating:
            texts = [
                "  Economy — estimating…",
                "  Normal — estimating…",
                "  Priority — estimating…",
            ]
        elif err or not self._estimate:
            texts = [
                "  Economy — unavailable",
                "  Normal — unavailable",
                "  Priority — unavailable",
            ]
        else:
            fee_opts = self._estimate.get("fee_options") or {}
            eco = fee_opts.get("economy") or {}
            nor = fee_opts.get("normal") or {}
            pri = fee_opts.get("priority") or {}

            eco_fee = format_xtz(eco.get("total_fee_xtz")) if eco.get("total_fee_xtz") else "0"
            nor_fee = format_xtz(nor.get("total_fee_xtz")) if nor.get("total_fee_xtz") else "0"
            pri_fee = format_xtz(pri.get("total_fee_xtz")) if pri.get("total_fee_xtz") else "0"

            check_eco = "● " if self._fee_choice == "economy" else "○ "
            check_nor = "● " if self._fee_choice == "normal" else "○ "
            check_pri = "● " if self._fee_choice == "priority" else "○ "

            texts = [
                f"{check_eco}Economy — {eco_fee} XTZ",
                f"{check_nor}Normal — {nor_fee} XTZ",
                f"{check_pri}Priority — {pri_fee} XTZ",
            ]

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

        # Update index
        lv = self.query_one("#fee_list", ListView)
        if self._fee_choice == "economy":
            lv.index = 0
        elif self._fee_choice == "normal":
            lv.index = 1
        elif self._fee_choice == "priority":
            lv.index = 2

    @work(exclusive=True, thread=True)
    def _estimate_worker(self) -> None:
        """Estimate stake operation in background thread."""
        try:
            est_result = estimate_stake(self.rpc, self.key, self.amount)
            self.app._ui(self._on_estimate_success, est_result)
        except Exception as e:
            log_error("Stake estimation failed", exception=e)
            self.app._ui(self._on_estimate_error, str(e))

    def _on_estimate_success(self, est_result: dict) -> None:
        self._estimate = est_result
        self._stop_est_pulse()
        self._render_summary()
        self._update_fee_list()

    def _on_estimate_error(self, error_msg: str) -> None:
        self._stop_est_pulse()
        self._render_summary(err=error_msg)
        self._update_fee_list(err=error_msg)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx == 0:
            self._fee_choice = "economy"
        elif idx == 1:
            self._fee_choice = "normal"
        elif idx == 2:
            self._fee_choice = "priority"

        self._render_summary()
        self._update_fee_list()

    @on(Button.Pressed, "#stake")
    def stake_pressed(self) -> None:
        """User confirmed stake operation."""
        result = {"ok": True}

        # Get fee parameters based on choice
        if self._estimate:
            fee_opts = self._estimate.get("fee_options") or {}
            chosen = fee_opts.get(self._fee_choice) or {}
            result["fee_mutez"] = chosen.get("fee_mutez")
            result["gas_limit"] = chosen.get("gas_limit")
            result["storage_limit"] = chosen.get("storage_limit")
        else:
            result["fee_mutez"] = None
            result["gas_limit"] = None
            result["storage_limit"] = None

        self.dismiss(result)

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss({"__BACK__": True})

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "backspace" and self.show_back_button:
            self.dismiss({"__BACK__": True})
            event.stop()
            return
        if key == "escape":
            self.dismiss(None)
            event.stop()


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
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #8b5cf6;
        padding: 1 2;
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

        self.query_one("#unstake", Button).focus()
        self._estimate_worker()

    def on_unmount(self) -> None:
        self._stop_est_pulse()

    def _start_est_pulse(self) -> None:
        self._estimating = True
        self._est_i = 0
        if self._est_timer is None:
            self._est_timer = self.set_interval(Config.ESTIMATION_PULSE_INTERVAL, self._tick_est_pulse)

    def _stop_est_pulse(self) -> None:
        self._estimating = False
        if self._est_timer is not None:
            self._est_timer.stop()
            self._est_timer = None

    def _tick_est_pulse(self) -> None:
        if not self._estimating:
            return
        self._est_i += 1
        self._render_summary(estimating=True)
        self._update_fee_list(estimating=True)

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)

        if estimating:
            lines = [
                "[b]Confirm Unstake Operation[/b]",
                "",
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b cyan]Address:[/b cyan]   {self.address}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
                "",
                f"[b #fdba74]Fee:[/b #fdba74]       {'[reverse]estimating…[/reverse]' if ((self._est_i // 3) % 2) else '[b]estimating…[/b]'}",
            ]
        elif err:
            lines = [
                "[b]Confirm Unstake Operation[/b]",
                "",
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
            est = self._estimate or {}
            fee_opts = est.get("fee_options") or {}
            chosen = fee_opts.get(self._fee_choice) or {}
            chosen_total = chosen.get("total_fee_xtz")

            lines = [
                "[b]Confirm Unstake Operation[/b]",
                "",
                f"[b #fdba74]Network:[/b #fdba74]   {net}",
                "",
                f"[b cyan]Address:[/b cyan]   {self.address}",
                "",
                f"[b #fdba74]Amount:[/b #fdba74]    {format_xtz(self.amount)} XTZ",
                "",
                f"[b #fdba74]Fee ({self._fee_choice}):[/b #fdba74] {format_xtz(chosen_total) if chosen_total else '0'} XTZ",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))

    def _init_fee_list(self) -> None:
        lv = self.query_one("#fee_list", ListView)
        lv.clear()
        self._fee_labels = []
        for _ in range(3):
            lbl = Label("")
            self._fee_labels.append(lbl)
            lv.append(ListItem(lbl))

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        if not self._fee_labels:
            self._init_fee_list()

        if estimating:
            texts = [
                "  Economy — estimating…",
                "  Normal — estimating…",
                "  Priority — estimating…",
            ]
        elif err or not self._estimate:
            texts = [
                "  Economy — unavailable",
                "  Normal — unavailable",
                "  Priority — unavailable",
            ]
        else:
            fee_opts = self._estimate.get("fee_options") or {}
            eco = fee_opts.get("economy") or {}
            nor = fee_opts.get("normal") or {}
            pri = fee_opts.get("priority") or {}

            eco_fee = format_xtz(eco.get("total_fee_xtz")) if eco.get("total_fee_xtz") else "0"
            nor_fee = format_xtz(nor.get("total_fee_xtz")) if nor.get("total_fee_xtz") else "0"
            pri_fee = format_xtz(pri.get("total_fee_xtz")) if pri.get("total_fee_xtz") else "0"

            check_eco = "● " if self._fee_choice == "economy" else "○ "
            check_nor = "● " if self._fee_choice == "normal" else "○ "
            check_pri = "● " if self._fee_choice == "priority" else "○ "

            texts = [
                f"{check_eco}Economy — {eco_fee} XTZ",
                f"{check_nor}Normal — {nor_fee} XTZ",
                f"{check_pri}Priority — {pri_fee} XTZ",
            ]

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

        lv = self.query_one("#fee_list", ListView)
        if self._fee_choice == "economy":
            lv.index = 0
        elif self._fee_choice == "normal":
            lv.index = 1
        elif self._fee_choice == "priority":
            lv.index = 2

    @work(exclusive=True, thread=True)
    def _estimate_worker(self) -> None:
        try:
            est_result = estimate_unstake(self.rpc, self.key, self.amount)
            self.app._ui(self._on_estimate_success, est_result)
        except Exception as e:
            log_error("Unstake estimation failed", exception=e)
            self.app._ui(self._on_estimate_error, str(e))

    def _on_estimate_success(self, est_result: dict) -> None:
        self._estimate = est_result
        self._stop_est_pulse()
        self._render_summary()
        self._update_fee_list()

    def _on_estimate_error(self, error_msg: str) -> None:
        self._stop_est_pulse()
        self._render_summary(err=error_msg)
        self._update_fee_list(err=error_msg)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx == 0:
            self._fee_choice = "economy"
        elif idx == 1:
            self._fee_choice = "normal"
        elif idx == 2:
            self._fee_choice = "priority"

        self._render_summary()
        self._update_fee_list()

    @on(Button.Pressed, "#unstake")
    def unstake_pressed(self) -> None:
        result = {"ok": True}

        if self._estimate:
            fee_opts = self._estimate.get("fee_options") or {}
            chosen = fee_opts.get(self._fee_choice) or {}
            result["fee_mutez"] = chosen.get("fee_mutez")
            result["gas_limit"] = chosen.get("gas_limit")
            result["storage_limit"] = chosen.get("storage_limit")
        else:
            result["fee_mutez"] = None
            result["gas_limit"] = None
            result["storage_limit"] = None

        self.dismiss(result)

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss({"__BACK__": True})

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "backspace" and self.show_back_button:
            self.dismiss({"__BACK__": True})
            event.stop()
            return
        if key == "escape":
            self.dismiss(None)
            event.stop()


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
            ("ghostnet", "Ghostnet — https://ghostnet.tezos.marigold.dev"),
        ]

        for key, desc in options:
            if key == self.current:
                text = f"✓ [black on #3b82f6] CURRENT [/black on #3b82f6]  {desc}"
            else:
                text = f"  {desc}"
            lv.append(ListItem(Label(text, markup=True)))

        try:
            lv.index = 0 if self.current == "mainnet" else 1
        except Exception as e:
            log_error("Failed to set network selection index", exception=e)

        lv.focus()

    def _selected_key(self) -> str:
        lv = self.query_one("#networks", ListView)
        idx = lv.index or 0
        return "mainnet" if idx == 0 else "ghostnet"

    @on(ListView.Selected)
    def choose_with_enter(self, event: ListView.Selected) -> None:
        # Selection should not auto-apply; wait for explicit Select/Enter.
        return

    @on(Button.Pressed, "#select")
    def select_pressed(self) -> None:
        self.dismiss(self._selected_key())

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss("")

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss("")
            event.stop()
            return
        if getattr(event, "key", None) == "enter":
            if isinstance(self.app.focused, ListView):
                self.dismiss(self._selected_key())
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
        except Exception as e:
            log_error("Failed to set RPC selection index", exception=e)

        lv.focus()

    def _selected_rpc(self) -> str:
        lv = self.query_one("#rpcs", ListView)
        idx = lv.index or 0
        if idx < 0 or idx >= len(self.options):
            return self.current_rpc
        return self.options[idx]

    @on(ListView.Selected)
    def choose_with_enter(self, event: ListView.Selected) -> None:
        # Selection should not auto-apply; wait for explicit Select/Enter.
        return

    @on(Button.Pressed, "#select")
    def select_pressed(self) -> None:
        self.dismiss(self._selected_rpc())

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss("")

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss("")
            event.stop()
            return
        if getattr(event, "key", None) == "enter":
            if isinstance(self.app.focused, ListView):
                self.dismiss(self._selected_rpc())
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
            self.app._set_status(f"✅ Address copied: {self.address}")  # type: ignore[attr-defined]
        except Exception as e:
            log_warning("Clipboard copy failed", exception=e, address=self.address)
            self.app._set_status(f"❌ Copy failed. Address: {self.address}")  # type: ignore[attr-defined]

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "backspace":
            self.dismiss({"__BACK__": True})
            event.stop()
            return
        if key == "escape":
            self.dismiss(None)
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
        max-height: 40;
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
        margin-bottom: 0;
        color: $accent;
        padding-left: 1;
    }

    ImportWizardScreen #hint {
        margin-bottom: 0;
        color: #fbbf24;
        text-style: italic;
        min-height: 1;
        padding-left: 1;
    }

    ImportWizardScreen #mnemonic_hint,
    ImportWizardScreen #secret_hint {
        margin-top: 0;
        margin-bottom: 0;
        color: #94a3b8;
        padding-left: 1;
    }

    ImportWizardScreen #mnemonic_store_hint {
        margin-top: 0;
        margin-bottom: 0;
        color: #fbbf24;
        padding-left: 1;
    }

    ImportWizardScreen #mnemonic_options {
        margin-top: 1;
        max-height: 2;
    }

    ImportWizardScreen #mnemonic_options > ListItem {
        padding: 0 0 0 1;
    }

    ImportWizardScreen #error {
        margin-top: 1;
        color: #f87171;
        min-height: 1;
        padding-left: 1;
    }

    ImportWizardScreen #import_types {
        margin-bottom: 1;
        max-height: 12;
    }

    ImportWizardScreen #hint {
        margin-top: 0;
    }

    ImportWizardScreen Input {
        margin-top: 1;
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

    IMPORT_TYPES = [
        ("mnemonic12", "🧠 Import with 12 Words", "Default derivation"),
        ("mnemonic24", "🧠 Import with 24 Words", "Default derivation"),
        ("secret", "🔑 Import with Secret Key", "Full wallet - can send & receive"),
        ("watch", "👀 Watch-Only Address", "Monitor only - cannot send"),
        ("backup", "📦 From Backup File", "Restore from recipe book"),
    ]

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
            yield Input(placeholder="Secret key (edsk...)", id="inp_secret", password=True)
            yield Input(
                placeholder="12-word mnemonic (space separated)",
                id="inp_mnemonic",
            )
            yield Input(
                placeholder="Derivation path (m/44'/1729'/0'/0') — leave blank for default",
                id="inp_mnemonic_path",
            )
            yield Input(placeholder="BIP39 passphrase (optional)", id="inp_mnemonic_pass", password=True)
            yield Input(placeholder="Passphrase to encrypt", id="inp_passphrase", password=True)
            yield Static(
                "[yellow]Passphrase encrypts keys (AES-256-GCM + scrypt).[/yellow]",
                id="secret_hint",
                markup=True,
            )
            yield Static(
                "[yellow]Passphrase encrypts keys (AES-256-GCM + scrypt).[/yellow]",
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
            yield Input(placeholder="Backup passphrase", id="inp_backup_pass", password=True)
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
        for _type_id, title, desc in self.IMPORT_TYPES:
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

    def _apply_step(self) -> None:
        title = self.query_one("#title", Static)
        hint = self.query_one("#hint", Static)
        error = self.query_one("#error", Static)
        lv = self.query_one("#import_types", ListView)

        inp_name = self.query_one("#inp_name", Input)
        inp_secret = self.query_one("#inp_secret", Input)
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
            title.update("[b]🔐 Backup Passphrase[/b]")
            hint.update("Unlock the recipe book.")
            self._set_hidden(inp_backup_pass, False)
            self._set_hidden(back_btn, False)
            self._set_hidden(import_btn, False)
            self._set_hidden(cancel_btn, False)
            inp_backup_pass.focus()

    def _get_selected_type(self) -> Optional[str]:
        lv = self.query_one("#import_types", ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self.IMPORT_TYPES):
            return None
        return self.IMPORT_TYPES[idx][0]

    def _set_error(self, message: str) -> None:
        self.query_one("#error", Static).update(message)

    def _load_backup_file(self, path: Path) -> Optional[dict]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            self._set_error("❌ Backup file not found.")
            return None
        except json.JSONDecodeError:
            self._set_error("❌ Invalid backup file format.")
            return None
        except Exception as e:
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
        self._step = "backup"
        self._apply_step()

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
            passphrase = self.query_one("#inp_passphrase", Input).value.strip()
            if not name or not secret or not passphrase:
                self._set_error("⚠️ Fill all fields to continue.")
                return
            self.dismiss({"mode": "secret", "name": name, "secret": secret, "passphrase": passphrase})
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
                self._set_error("⚠️ Name and passphrase required.")
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
                self._set_error("⚠️ Passphrase required.")
                return
            try:
                from sassy_wallet.core.crypto import EncryptedBlob

                backup_type = (self._backup_encrypted or {}).get("backup_type")
                blob_dict = (self._backup_encrypted or {}).get("blob") or {}
                blob = EncryptedBlob(
                    salt_b64=blob_dict.get("salt_b64", ""),
                    nonce_b64=blob_dict.get("nonce_b64", ""),
                    ct_b64=blob_dict.get("ct_b64", ""),
                )
                payload_json = decrypt_secret(blob, passphrase)
                data = json.loads(payload_json)
                if backup_type and not data.get("backup_type"):
                    data["backup_type"] = backup_type
            except Exception:
                self._set_error("❌ Wrong passphrase or corrupted backup.")
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
            self.dismiss(None)
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
        if key == "enter" and self._step in ("backup", "backup_pass"):
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
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
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
        max-height: 12;
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

    IMPORT_TYPES = [
        ("mnemonic12", "🧠 Import with 12 Words", "Default derivation"),
        ("mnemonic24", "🧠 Import with 24 Words", "Default derivation"),
        ("secret", "🔑 Import with Secret Key", "Full wallet - can send & receive"),
        ("watch", "👀 Watch-Only Address", "Monitor only - cannot send"),
        ("backup", "📦 From Backup File", "Restore from recipe book"),
    ]

    def __init__(self):
        super().__init__()
        self.selected_type: Optional[str] = None

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

        for type_id, title, description in self.IMPORT_TYPES:
            label_text = f"[b]{title}[/b]\n[dim]{description}[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))

        lv.index = 0
        lv.focus()

    def _get_selected_type(self) -> Optional[str]:
        lv = self.query_one("#import_types", ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self.IMPORT_TYPES):
            return None
        return self.IMPORT_TYPES[idx][0]

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
            self.dismiss({"__BACK__": True})
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
    ImportSecretScreen #inp_passphrase {
        margin-top: 1;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    ImportSecretScreen #inp_name:focus,
    ImportSecretScreen #inp_secret:focus,
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
            yield Input(placeholder="Secret key (edsk...)", id="inp_secret", password=True)
            yield Input(placeholder="Passphrase to encrypt", id="inp_passphrase", password=True)
            yield Static(
                "[yellow]Passphrase encrypts keys (AES-256-GCM + scrypt).[/yellow]",
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
            passphrase = self.query_one("#inp_passphrase", Input).value
            self.dismiss({
                "name": name,
                "secret": secret,
                "passphrase": passphrase,
            })
        elif event.button.id == "back":
            self.dismiss({"__BACK__": True})
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if isinstance(self.app.focused, Input):
            if getattr(event, "key", None) == "escape":
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
                return
            return
        if getattr(event, "key", None) == "escape":
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
            self.dismiss({"__BACK__": True})
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if isinstance(self.app.focused, Input):
            if getattr(event, "key", None) == "escape":
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
                return
            return
        if getattr(event, "key", None) == "escape":
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
        if getattr(event, "key", None) == "escape":
            self.dismiss(None)
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
        border: heavy #eab308;
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
        background: #eab308;
        color: white;
    }

    BackupWalletSelectorScreen #select:hover {
        background: #ca8a04;
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
        margin-bottom: 1;
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

    BackupMultiSelectorScreen Horizontal {
        align: center middle;
    }

    BackupMultiSelectorScreen Horizontal > Button {
        margin: 0 1;
    }

    BackupMultiSelectorScreen .hidden {
        display: none;
    }

    BackupMultiSelectorScreen #backup_selected,
    BackupMultiSelectorScreen #backup_all,
    BackupMultiSelectorScreen #ok {
        background: #eab308;
        color: white;
    }

    BackupMultiSelectorScreen #backup_selected:hover,
    BackupMultiSelectorScreen #backup_all:hover,
    BackupMultiSelectorScreen #ok:hover {
        background: #ca8a04;
        color: white;
    }

    BackupMultiSelectorScreen #inp_pass,
    BackupMultiSelectorScreen #inp_confirm {
        margin-top: 1;
        background: transparent;
        border: solid #4b5563;
        padding: 0 1;
    }

    BackupMultiSelectorScreen #inp_pass:focus,
    BackupMultiSelectorScreen #inp_confirm:focus {
        border: solid #10b981;
    }

    BackupMultiSelectorScreen #inp_backup_dir {
        margin-top: 1;
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

    BackupMultiSelectorScreen #backup_dir_mode {
        margin-top: 1;
        max-height: 4;
    }

    BackupMultiSelectorScreen .dimmed {
        opacity: 0.6;
    }
    """

    def __init__(self, accounts: list["Account"]):
        super().__init__()
        self.accounts = accounts
        self._selected: set[int] = set()
        self._labels: list[Label] = []
        self._step: str = "select"
        self._mode: str | None = None
        self._pass_hint: str = ""
        self._backup_dir: Path = Path("data/backups")
        self._use_default_dir: bool = True
        self._dir_mode_labels: list[Label] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="title", markup=True)
            yield Static("", id="hint", markup=True)
            yield ListView(id="wallets")
            yield ListView(id="backup_dir_mode")
            yield Input(placeholder="Backup folder (default: data/backups)", id="inp_backup_dir")
            yield DirectoryTree(path=Path.home(), id="backup_dir_picker")
            yield Input(placeholder="Create passphrase", password=True, id="inp_pass")
            yield Input(placeholder="Confirm passphrase", password=True, id="inp_confirm")
            yield Static("", id="pass_hint", markup=True)
            with Horizontal():
                yield Button("← Back", id="back", variant="default")
                yield Button("Backup selected", id="backup_selected", variant="primary")
                yield Button("Bulk backup", id="backup_all", variant="warning")
                yield Button("🔒 Encrypt Backup", id="ok", variant="primary")
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
        self._init_dir_mode()
        self._apply_step()

    def _init_dir_mode(self) -> None:
        mode_lv = self.query_one("#backup_dir_mode", ListView)
        mode_lv.clear()
        self._dir_mode_labels.clear()
        for text in ("Default folder (data/backups)", "Choose folder manually"):
            lbl = Label(text)
            self._dir_mode_labels.append(lbl)
            mode_lv.append(ListItem(lbl))
        mode_lv.index = 0
        self._use_default_dir = True
        self._update_dir_mode_labels()

    def _apply_step(self) -> None:
        title = self.query_one("#title", Static)
        hint = self.query_one("#hint", Static)
        wallets = self.query_one("#wallets", ListView)
        mode_lv = self.query_one("#backup_dir_mode", ListView)
        inp_backup_dir = self.query_one("#inp_backup_dir", Input)
        backup_dir_picker = self.query_one("#backup_dir_picker", DirectoryTree)
        inp_pass = self.query_one("#inp_pass", Input)
        inp_confirm = self.query_one("#inp_confirm", Input)
        pass_hint = self.query_one("#pass_hint", Static)
        back_btn = self.query_one("#back", Button)
        backup_selected = self.query_one("#backup_selected", Button)
        backup_all = self.query_one("#backup_all", Button)
        ok_btn = self.query_one("#ok", Button)

        if self._step == "select":
            title.update("[b]Backup Wallets[/b]\nSelect one or many wallets")
            hint.update("Tip: Space/Enter to toggle. Choose Bulk Backup to grab everything.")
            self._pass_hint = ""
            pass_hint.update("")
            wallets.remove_class("hidden")
            mode_lv.add_class("hidden")
            inp_backup_dir.add_class("hidden")
            backup_dir_picker.add_class("hidden")
            inp_pass.add_class("hidden")
            inp_confirm.add_class("hidden")
            pass_hint.add_class("hidden")
            back_btn.add_class("hidden")
            ok_btn.add_class("hidden")
            backup_selected.remove_class("hidden")
            backup_all.remove_class("hidden")
            wallets.focus()
        else:
            title.update("[b]🔐 Backup Passphrase[/b]")
            hint.update("Pick a folder, then set a passphrase.\n[dim]Encryption: AES-256-GCM + scrypt.[/dim]")
            pass_hint.remove_class("hidden")
            pass_hint.update(self._pass_hint)
            wallets.add_class("hidden")
            mode_lv.remove_class("hidden")
            inp_backup_dir.remove_class("hidden")
            backup_dir_picker.remove_class("hidden")
            inp_pass.remove_class("hidden")
            inp_confirm.remove_class("hidden")
            back_btn.remove_class("hidden")
            ok_btn.remove_class("hidden")
            backup_selected.add_class("hidden")
            backup_all.add_class("hidden")
            inp_backup_dir.value = str(self._backup_dir)
            self._apply_dir_mode()
            mode_lv.focus()

    def _apply_dir_mode(self) -> None:
        inp_backup_dir = self.query_one("#inp_backup_dir", Input)
        backup_dir_picker = self.query_one("#backup_dir_picker", DirectoryTree)
        if self._use_default_dir:
            inp_backup_dir.value = str(self._backup_dir)
            inp_backup_dir.disabled = True
            backup_dir_picker.disabled = True
            inp_backup_dir.add_class("dimmed")
            backup_dir_picker.add_class("dimmed")
        else:
            inp_backup_dir.disabled = False
            backup_dir_picker.disabled = False
            inp_backup_dir.remove_class("dimmed")
            backup_dir_picker.remove_class("dimmed")
        self._update_dir_mode_labels()

    def _update_dir_mode_labels(self) -> None:
        for i, lbl in enumerate(self._dir_mode_labels):
            mark = "[#eab308]■[/#eab308]" if (self._use_default_dir and i == 0) or (not self._use_default_dir and i == 1) else "[dim]□[/dim]"
            text = "Default folder (data/backups)" if i == 0 else "Choose folder manually"
            lbl.update(f"{mark} {text}")

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
        btn.disabled = not self._selected

    @on(ListView.Selected, "#wallets")
    def list_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is None:
            return
        self._toggle_index(idx)

    @on(Button.Pressed, "#backup_selected")
    def backup_selected_pressed(self) -> None:
        if not self._selected:
            return
        self._mode = "selected"
        self._step = "passphrase"
        self._apply_step()

    @on(Button.Pressed, "#backup_all")
    def backup_all_pressed(self) -> None:
        self._mode = "all"
        self._step = "passphrase"
        self._apply_step()

    @on(Button.Pressed, "#ok")
    def ok_pressed(self) -> None:
        inp_backup_dir = self.query_one("#inp_backup_dir", Input)
        inp_pass = self.query_one("#inp_pass", Input)
        inp_confirm = self.query_one("#inp_confirm", Input)
        backup_dir = (inp_backup_dir.value or "").strip()
        passphrase = (inp_pass.value or "").strip()
        confirm_passphrase = (inp_confirm.value or "").strip()
        pass_hint = self.query_one("#pass_hint", Static)
        if not backup_dir:
            self._pass_hint = "⚠️ Choose a backup folder.\n[dim]Encryption: AES-256-GCM + scrypt.[/dim]"
            pass_hint.update(self._pass_hint)
            self.query_one("#backup_dir_mode", ListView).focus()
            return
        if not passphrase or not confirm_passphrase:
            self._pass_hint = "⚠️ Both fields are required.\n[dim]Encryption: AES-256-GCM + scrypt.[/dim]"
            pass_hint.update(self._pass_hint)
            inp_pass.focus()
            return
        if confirm_passphrase != passphrase:
            self._pass_hint = "⚠️ Hey, this is serious stuff. Pay attention — both passphrases must match. 😅\n[dim]Encryption: AES-256-GCM + scrypt.[/dim]"
            pass_hint.update(self._pass_hint)
            inp_pass.focus()
            return
        self._backup_dir = Path(backup_dir).expanduser()
        if self._mode == "selected":
            accounts = [self.accounts[i] for i in sorted(self._selected)]
            self.dismiss({
                "mode": "selected",
                "accounts": accounts,
                "passphrase": passphrase,
                "confirm": confirm_passphrase,
                "backup_dir": str(self._backup_dir),
            })
        elif self._mode == "all":
            self.dismiss({
                "mode": "all",
                "passphrase": passphrase,
                "confirm": confirm_passphrase,
                "backup_dir": str(self._backup_dir),
            })
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self._step = "select"
        self._apply_step()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(DirectoryTree.DirectorySelected, "#backup_dir_picker")
    def backup_dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if self._use_default_dir:
            return
        self._backup_dir = event.path
        self.query_one("#inp_backup_dir", Input).value = str(event.path)

    @on(DirectoryTree.FileSelected, "#backup_dir_picker")
    def backup_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        if self._use_default_dir:
            return
        parent = event.path.parent
        self._backup_dir = parent
        self.query_one("#inp_backup_dir", Input).value = str(parent)

    @on(Tree.NodeHighlighted, "#backup_dir_picker")
    def backup_dir_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if self._use_default_dir:
            return
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
        if self._use_default_dir:
            return
        node = event.node
        entry = getattr(node, "data", None)
        path = getattr(entry, "path", None)
        if not path:
            return
        use_path = path if path.is_dir() else path.parent
        self._backup_dir = use_path
        self.query_one("#inp_backup_dir", Input).value = str(use_path)

    @on(ListView.Selected, "#backup_dir_mode")
    def backup_dir_mode_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        self._use_default_dir = idx == 0
        if self._use_default_dir:
            self._backup_dir = Path("data/backups")
        self._apply_dir_mode()

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)
        if key == "escape":
            self.dismiss(None)
            event.stop()
            return
        if key in ("left", "right") and isinstance(self.app.focused, Button):
            parent = self.app.focused.parent
            if isinstance(parent, Horizontal):
                focusables = [c for c in parent.children if isinstance(c, Button)]
                if self.app.focused in focusables:
                    idx = focusables.index(self.app.focused)
                    if key == "left" and idx > 0:
                        focusables[idx - 1].focus()
                        event.stop()
                        return
                    if key == "right" and idx < len(focusables) - 1:
                        focusables[idx + 1].focus()
                        event.stop()
                        return
        if key in ("enter", "space"):
            if isinstance(self.app.focused, ListView):
                lv = self.query_one("#wallets", ListView)
                idx = lv.index
                if idx is not None:
                    self._toggle_index(idx)
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
        self._status_timer = None
        import random
        self._fun_message = random.choice(self.RECEIVE_MESSAGES)

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
        try:
            idx = next(i for i, acc in enumerate(self.accounts) if acc.address == self.address)
            lv.index = idx
        except StopIteration:
            lv.index = 0
        if self.accounts and lv.index is not None:
            self._set_address(self.accounts[lv.index].address)

    def _set_address(self, address: str) -> None:
        self.address = address
        try:
            self.query_one("#address_text", Static).update(
                f"[b]{self.address}[/b]\n[dim]👆 Share this address to receive XTZ[/dim]"
            )
        except Exception:
            pass

    @on(ListView.Selected, "#wallet_selector")
    def wallet_selected(self, event: ListView.Selected) -> None:
        if event.list_view.index is None:
            return
        idx = event.list_view.index
        if 0 <= idx < len(self.accounts):
            self._set_address(self.accounts[idx].address)

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss(None)
            event.stop()

    @on(Button.Pressed, "#copy")
    def copy_pressed(self) -> None:
        try:
            self.app.copy_to_clipboard(self.address)  # type: ignore[attr-defined]
            self.app._set_status(f"✅ Address copied: {self.address}")  # type: ignore[attr-defined]
        except Exception as e:
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
        max-height: 36;
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

    StakeScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        overflow-y: auto;
        background: $surface;
        border: heavy #10b981;
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

    StakeScreen #info_box {
        margin-bottom: 1;
        padding: 1 2;
        height: auto;
        background: $panel;
        border: solid #374151;
        display: none;
        text-align: left;
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

    def __init__(self, accounts: list["Account"], rpc: str, wallet_info_cache: Optional[dict[str, dict]] = None):
        super().__init__()
        # Filter only accounts with secret keys (not watch-only)
        self.accounts = [acc for acc in accounts if acc.enc is not None]
        self.rpc = rpc
        self.selected_account: Optional["Account"] = None
        self.balance_xtz: Decimal = Decimal(0)
        self.delegate_addr: Optional[str] = None
        self.staked_mutez: int = 0
        self.is_delegated: bool = False
        self._delegation_pending: bool = False
        self._polling_timer = None
        # Cache wallet info to avoid re-fetching when selecting
        self._wallet_info_cache: dict[str, dict] = wallet_info_cache if wallet_info_cache is not None else {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]⚡ Stake Manager[/b]", id="title", markup=True)

            # Wallet selector
            yield Static("[b]Choose Wallet:[/b]", id="wallet_selector_label", markup=True)
            yield ListView(id="wallet_selector")
            yield Static("💡 Who’s the lucky wallet becoming a staking CHAD today? Let’s lock in some XTZ! 💪", id="fun_note", markup=True)

            # Info box (hidden initially, shown after wallet selection)
            yield Static("", id="info_box", markup=True)

            # Input container (hidden initially)
            with Vertical(id="input_container"):
                yield Static("", id="input_label", markup=True)
                yield Input(placeholder="", id="input_field")
                yield Static("", id="input_hint", markup=True)
                yield Static("", id="amount_comment", markup=True)

            yield Static("", id="status_msg", markup=True)

            # Buttons
            with Horizontal(id="button_container"):
                yield Button("Select", id="select_wallet_btn", variant="primary")
                yield Button("◀ Back", id="back_btn", variant="default", classes="hidden")
                yield Button("Delegate", id="delegate_btn", variant="warning", classes="hidden")
                yield Button("Stake", id="stake_btn", variant="primary", classes="hidden")
                yield Button("Unstake", id="unstake_btn", variant="warning", classes="hidden")
                yield Button("Cancel", id="cancel")

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
                    staked_mutez = cached_info.get("staked_mutez", 0)
                    delegate_addr = cached_info.get("delegate_addr")
                    status_tags = []
                    if staked_mutez > 0:
                        staked_xtz = mutez_to_xtz(staked_mutez)
                        status_tags.append(f"[#8b5cf6]⚡ STAKING ({format_xtz(staked_xtz)} XTZ)[/#8b5cf6]")
                    elif delegate_addr:
                        status_tags.append("[yellow]🔗 DELEGATED[/yellow]")
                    else:
                        status_tags.append("[dim]⚪ Not delegated[/dim]")
                    status_line = " ".join(status_tags)
                    label_text = f"[b]{acc.name}[/b] {status_line}\n[dim]{addr_short}[/dim]"
                else:
                    fun_msg = get_wallet_loading_message()
                    label_text = f"[b]{acc.name}[/b] [dim]{fun_msg}[/dim]\n[dim]{addr_short}[/dim]"
                lv.append(ListItem(Label(label_text, markup=True)))

            lv.index = 0

            # Refresh data asynchronously without blocking UI
            self.run_worker(self._load_wallet_statuses(), exclusive=False)

    async def _load_wallet_statuses(self) -> None:
        """Load wallet statuses asynchronously without blocking UI."""
        lv = self.query_one("#wallet_selector", ListView)
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        for idx, acc in enumerate(self.accounts):
            try:
                addr_short = acc.address[:10] + "…" + acc.address[-8:]
                spin = spinner[idx % len(spinner)]
                try:
                    list_items = list(lv.children)
                    if idx < len(list_items):
                        item = list_items[idx]
                        label = item.query_one(Label)
                        label.update(f"{spin} [b]{acc.name}[/b] [dim]Loading...[/dim]\n[dim]{addr_short}[/dim]")
                except Exception:
                    pass

                # Fetch delegation and staking status (blocking calls, but in worker thread)
                delegate_addr = get_delegation_info(self.rpc, acc.address)
                staked_mutez = get_staking_balance(self.rpc, acc.address)
                balance_mutez = get_balance_mutez(self.rpc, acc.address)

                # Cache the info for instant access when selecting
                self._wallet_info_cache[acc.address] = {
                    "delegate_addr": delegate_addr,
                    "staked_mutez": staked_mutez,
                    "balance_mutez": balance_mutez,
                }

                # Build status tags
                status_tags = []
                if staked_mutez > 0:
                    staked_xtz = mutez_to_xtz(staked_mutez)
                    status_tags.append(f"[#8b5cf6]⚡ STAKING ({format_xtz(staked_xtz)} XTZ)[/#8b5cf6]")
                elif delegate_addr:
                    status_tags.append("[yellow]🔗 DELEGATED[/yellow]")
                else:
                    status_tags.append("[dim]⚪ Not delegated[/dim]")

                status_line = " ".join(status_tags)
                label_text = f"[b]{acc.name}[/b] {status_line}\n[dim]{addr_short}[/dim]"

            except Exception as e:
                log_error(f"Failed to fetch status for {acc.name}", exception=e)
                label_text = f"[b]{acc.name}[/b] [red]⚠️ Error loading status[/red]\n[dim]{addr_short}[/dim]"

            # Update the list item with loaded data
            try:
                list_items = list(lv.children)
                if idx < len(list_items):
                    item = list_items[idx]
                    # Update the label inside the ListItem
                label = item.query_one(Label)
                label.update(label_text)
            except Exception as e:
                log_error(f"Failed to update UI for {acc.name}", exception=e)
    def on_key(self, event) -> None:
        # CRITICAL: Don't capture keys in these scenarios
        from textual.widgets import Input
        from textual.screen import ModalScreen

        key = getattr(event, "key", None)

        # 🚫 If focus is on an Input widget, let it handle keys naturally
        # Only intercept Escape for cancel functionality
        if isinstance(self.app.focused, Input):
            if key == "escape":
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
            # For all other keys, let Input handle them naturally (NO event.stop())
            return

        # 🚫 If a modal is open (check if screen stack has another modal on top)
        # The active screen should be THIS screen if no modal is open
        if self.app.screen is not self:
            event.stop()
            return

        # Valid navigation from here

        if key == "escape":
            self.dismiss(None)
            return
        if key == "backspace" and self.selected_account:
            self._go_back_to_selector()
            event.stop()
            return

    @on(ListView.Selected, "#wallet_selector")
    def wallet_selected(self, event: ListView.Selected) -> None:
        """Handle wallet highlighting from ListView (no auto-advance)."""
        # Just highlight, don't advance automatically
        pass

    @on(Button.Pressed, "#select_wallet_btn")
    def select_wallet_pressed(self) -> None:
        """Handle Select button - confirm wallet selection."""
        try:
            lv = self.query_one("#wallet_selector", ListView)
            if lv.index is not None and lv.index >= 0:
                self._select_wallet(lv.index)
        except Exception as e:
            log_error("Failed to select wallet", exception=e)

    def _select_wallet(self, index: int) -> None:
        """Select wallet and update view with its info (uses cached data)."""
        if index < 0 or index >= len(self.accounts):
            return

        self.selected_account = self.accounts[index]

        # Use cached wallet info for instant transition
        try:
            cached_info = self._wallet_info_cache.get(self.selected_account.address)

            if cached_info:
                # Use cached data - instant, no lag!
                self.balance_xtz = mutez_to_xtz(cached_info["balance_mutez"])
                self.delegate_addr = cached_info["delegate_addr"]
                self.staked_mutez = cached_info["staked_mutez"]
                self.is_delegated = bool(self.delegate_addr)
            else:
                # Fallback: fetch if cache miss (shouldn't happen normally)
                balance_mutez = get_balance_mutez(self.rpc, self.selected_account.address)
                self.balance_xtz = mutez_to_xtz(balance_mutez)
                self.delegate_addr = get_delegation_info(self.rpc, self.selected_account.address)
                self.staked_mutez = get_staking_balance(self.rpc, self.selected_account.address)
                self.is_delegated = bool(self.delegate_addr)

            self._update_view()
        except Exception as e:
            log_error("Failed to fetch wallet info", exception=e)
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update(f"[red]❌ Failed to fetch wallet info: {str(e)}[/red]")

    def _go_back_to_selector(self) -> None:
        """Go back to wallet selector screen."""
        # Reset state
        self.selected_account = None
        self.balance_xtz = Decimal(0)
        self.delegate_addr = None
        self.staked_mutez = 0
        self.is_delegated = False
        self._delegation_pending = False

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
        except Exception as e:
            log_error("Failed to show wallet selector", exception=e)

        # Show Select button
        try:
            self.query_one("#select_wallet_btn", Button).display = True
        except Exception as e:
            log_error("Failed to show select button", exception=e)

        # Clear and hide info box
        try:
            info_widget = self.query_one("#info_box", Static)
            info_widget.update("")
            info_widget.display = False
        except Exception as e:
            log_error("Failed to clear info box", exception=e)

        # Hide and clear input container
        try:
            self.query_one("#input_container", Vertical).display = False
            self.query_one("#input_label", Static).update("")
            self.query_one("#input_field", Input).value = ""
            self.query_one("#input_field", Input).placeholder = ""
            self.query_one("#input_hint", Static).update("")
        except Exception as e:
            log_error("Failed to hide/clear input container", exception=e)

        # Clear status
        try:
            self.query_one("#status_msg", Static).update("")
        except Exception as e:
            log_error("Failed to clear status", exception=e)

        # Reset buttons - hide all action buttons
        def reset_buttons():
            try:
                # Show select wallet button
                select_btn = self.query_one("#select_wallet_btn", Button)
                select_btn.remove_class("hidden")

                # Hide all action buttons
                self.query_one("#back_btn", Button).add_class("hidden")
                self.query_one("#delegate_btn", Button).add_class("hidden")
                self.query_one("#stake_btn", Button).add_class("hidden")
                self.query_one("#unstake_btn", Button).add_class("hidden")
            except Exception as e:
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
            except Exception as e:
                log_error("Failed to hide wallet selector", exception=e)

            # Show input container and prepare input field
            try:
                input_container = self.query_one("#input_container", Vertical)
                input_container.display = True

                # Pre-configure input field
                input_field = self.query_one("#input_field", Input)
                input_field.disabled = False
            except Exception as e:
                log_error("Failed to show input container", exception=e)

            # Update info box - ALWAYS show wallet details
            staked_xtz = format_xtz(mutez_to_xtz(self.staked_mutez))
            info_widget = self.query_one("#info_box", Static)

            # Build detailed wallet info
            addr = self.selected_account.address
            addr_short = addr[:10] + "…" + addr[-6:] if len(addr) > 16 else addr

            available_xtz = format_xtz(self.balance_xtz)

            delegate_label = "[dim]Not delegated[/dim]"
            if self.is_delegated and self.delegate_addr:
                delegate_short = self.delegate_addr[:10] + "…" + self.delegate_addr[-6:] if len(self.delegate_addr) > 16 else self.delegate_addr
                info = get_baker_info(self.rpc, self.delegate_addr)
                alias = info.get("alias") if info else None
                if alias:
                    delegate_label = f"{alias} [dim]({delegate_short})[/dim]"
                else:
                    delegate_label = delegate_short

            info_lines = [
                f"[b]Wallet:[/b] {self.selected_account.name}",
                f"[dim]{addr_short}[/dim]",
                "",
                f"[cyan]Available[/cyan] {available_xtz} XTZ   [#8b5cf6]Staked[/#8b5cf6] {staked_xtz} XTZ",
                f"[yellow]Delegated to[/yellow] {delegate_label}",
            ]

            info_text = "\n".join(info_lines)
            info_widget.update(info_text)
            info_widget.display = True

            # Update input container
            input_label = self.query_one("#input_label", Static)
            input_field = self.query_one("#input_field", Input)
            input_hint = self.query_one("#input_hint", Static)

            # Always clear the input field when updating view
            input_field.value = ""

            if not self.is_delegated and not self._delegation_pending:
                # Not delegated - show baker input
                input_label.update("[b]Enter Baker Address:[/b]")
                input_field.placeholder = "tz1... or tz2... or tz3... or tz4..."
                input_field.disabled = False
                input_hint.update("[dim]Find bakers at baking-bad.org or tzkt.io[/dim]")
                self.query_one("#amount_comment", Static).update("")
            elif self._delegation_pending:
                # Delegation pending - show waiting message
                input_label.update("[b]⏳ Waiting for confirmation...[/b]")
                input_field.placeholder = "Please wait..."
                input_field.disabled = True
                input_hint.update("[dim]Processing delegation (30-60 seconds)...[/dim]")
                self.query_one("#amount_comment", Static).update("")
            else:
                # Delegated - show amount input
                input_label.update("[b]Enter Amount (XTZ):[/b]")
                input_field.placeholder = "Example: 10.5"
                input_field.disabled = False
                input_hint.update("")
                self.query_one("#amount_comment", Static).update("")

            # Update buttons - simplified show/hide approach
            def update_buttons():
                try:
                    # Hide select wallet button
                    select_btn = self.query_one("#select_wallet_btn", Button)
                    select_btn.add_class("hidden")

                    # Show back button
                    back_btn = self.query_one("#back_btn", Button)
                    back_btn.remove_class("hidden")

                    # Get buttons
                    delegate_btn = self.query_one("#delegate_btn", Button)
                    stake_btn = self.query_one("#stake_btn", Button)
                    unstake_btn = self.query_one("#unstake_btn", Button)

                    # Hide all action buttons first
                    delegate_btn.add_class("hidden")
                    stake_btn.add_class("hidden")
                    unstake_btn.add_class("hidden")

                    # Show/configure buttons based on state
                    if not self.is_delegated and not self._delegation_pending:
                        # Not delegated - show Delegate button
                        delegate_btn.remove_class("hidden")
                        delegate_btn.disabled = False
                        delegate_btn.label = "Delegate"
                    elif self._delegation_pending:
                        # Delegation pending
                        delegate_btn.remove_class("hidden")
                        delegate_btn.disabled = True
                        delegate_btn.label = "Delegating..."
                    elif self.staked_mutez > 0:
                        # Already staking - show Stake and Unstake
                        stake_btn.remove_class("hidden")
                        stake_btn.disabled = False
                        unstake_btn.remove_class("hidden")
                        unstake_btn.disabled = False
                    else:
                        # Delegated but not staking - show Stake button
                        stake_btn.remove_class("hidden")
                        stake_btn.disabled = False

                except Exception as e:
                    log_error("Failed to update buttons", exception=e)

            self.call_later(update_buttons)

            # Focus input field after everything is ready - simple and direct
            def focus_input():
                try:
                    input_field = self.query_one("#input_field", Input)
                    if not input_field.disabled:
                        input_field.focus()
                except Exception as e:
                    log_error("Failed to focus input field", exception=e)

            # Use set_timer to ensure DOM is fully rendered
            self.set_timer(0.1, focus_input)

        except Exception as e:
            log_error("Failed to update view", exception=e)
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update(f"[red]❌ Error updating view: {str(e)}[/red]")

    @on(Input.Changed, "#input_field")
    def on_input_changed(self, event: Input.Changed) -> None:
        """Validate input in real-time and provide visual feedback."""
        if not self.selected_account:
            return

        value = sanitize_input(event.value)
        input_hint = self.query_one("#input_hint", Static)

        # If input is empty, show default hint
        if not value:
            if not self.is_delegated and not self._delegation_pending:
                input_hint.update("[dim]Must delegate before staking. Find bakers at baking-bad.org or tzkt.io[/dim]")
            elif not self._delegation_pending:
                input_hint.update("")
                self.query_one("#amount_comment", Static).update("")
            return

        # Validate based on current state
        if not self.is_delegated and not self._delegation_pending:
            # Validating baker address
            is_valid, error_msg = validate_baker_address(value)
            if is_valid:
                input_hint.update("[#34d399]✓ Valid baker address[/#34d399]")
            else:
                # Only show error if the address looks complete (36 chars)
                if len(value) >= 36:
                    input_hint.update(f"[red]✗ {error_msg}[/red]")
                else:
                    input_hint.update("[dim]Enter complete baker address (36 characters)[/dim]")
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

    @work(exclusive=False, thread=True)
    @work(exclusive=True)
    @on(Button.Pressed, "#delegate_btn")
    async def delegate_pressed(self) -> None:
        """Handle delegation action."""
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

        # Check for pending transactions before attempting delegation
        from sassy_wallet.core.tezos import check_pending_operations
        pending_info = check_pending_operations(self.rpc, self.selected_account.address)

        if pending_info and pending_info.get('has_pending'):
            # Show warning about pending transactions
            pending_count = pending_info.get('pending_count', 0)
            operations = pending_info.get('operations', [])

            # Build warning message
            ops_details = []
            for op in operations[:3]:  # Show max 3 operations
                kind = op.get('kind', 'unknown')
                counter = op.get('counter', '?')
                hash_short = op.get('hash', 'unknown')[:16]
                ops_details.append(f"  • {kind} (counter: {counter}) - {hash_short}...")

            ops_text = "\n".join(ops_details)
            if len(operations) > 3:
                ops_text += f"\n  ... and {len(operations) - 3} more"

            warning_msg = (
                f"⚠️ [b]Pending Transactions Detected![/b]\n\n"
                f"Found {pending_count} pending operation(s) for this wallet:\n\n"
                f"{ops_text}\n\n"
                f"These transactions are waiting to be confirmed in the blockchain.\n"
                f"Attempting to delegate now may cause counter errors.\n\n"
                f"[b]Recommendations:[/b]\n"
                f"• Wait 1-2 minutes for pending operations to confirm\n"
                f"• Check your transaction history\n"
                f"• Try again after pending operations clear\n\n"
                f"Do you want to proceed anyway? (Not recommended)"
            )

            # Show confirmation dialog
            proceed = await self.app.push_screen_wait(ConfirmScreen(warning_msg))

            if not proceed:
                self._show_error("⏸️ Delegation cancelled - waiting for pending operations")
                return

        # Show fee selection modal
        fee_result = await self.app.push_screen_wait(
            ConfirmDelegateScreen(
                self.rpc,
                self.selected_account.address,
                value
            )
        )

        if not fee_result or not fee_result.get("ok"):
            self._show_error("⏸️ Delegation cancelled")
            return

        # Extract fee parameters from modal result
        fee_mutez = fee_result.get("fee_mutez")
        gas_limit = fee_result.get("gas_limit")
        storage_limit = fee_result.get("storage_limit")

        # Apply defaults if None
        if fee_mutez is None:
            fee_mutez = 8000
        if gas_limit is None:
            gas_limit = 30000
        if storage_limit is None:
            storage_limit = 0

        # Try to get baker name from known bakers (if available)
        baker_name = "Unknown Baker"
        try:
            from sassy_wallet.core.tezos import KNOWN_BAKERS
            for baker in KNOWN_BAKERS:
                if baker.get("address") == value:
                    baker_name = baker.get("name", "Unknown Baker")
                    break
        except:
            pass


        # Close StakeScreen and return data to app for passphrase handling
        self.dismiss({
            "action": "delegate",
            "baker_address": value,
            "baker_name": baker_name,
            "fee_mutez": fee_mutez,
            "gas_limit": gas_limit,
            "storage_limit": storage_limit,
            "account": self.selected_account
        })

    @work(exclusive=True)
    @on(Button.Pressed, "#stake_btn")
    async def stake_pressed(self) -> None:
        """Handle staking action."""

        input_field = self.query_one("#input_field", Input)
        value = sanitize_input(input_field.value)

        if not value:
            self._show_error("⚠️ Please enter amount")
            return

        # Validate amount with proper error messages
        is_valid, error_msg, amount = validate_amount(value, min_value=Decimal("0"), max_value=self.balance_xtz)

        if not is_valid:
            self._show_error(f"⚠️ {error_msg}")
            return

        try:

            # Check for pending transactions
            from sassy_wallet.core.tezos import check_pending_operations
            pending_info = check_pending_operations(self.rpc, self.selected_account.address)

            if pending_info and pending_info.get('has_pending'):
                pending_count = pending_info.get('pending_count', 0)
                warning_msg = (
                    f"⚠️ [b]Pending Transactions Detected![/b]\n\n"
                    f"Found {pending_count} pending operation(s) for this wallet.\n"
                    f"Proceeding may cause counter errors.\n\n"
                    f"Wait 1-2 minutes for operations to confirm, then try again.\n\n"
                    f"Proceed anyway? (Not recommended)"
                )
                proceed = await self.app.push_screen_wait(ConfirmScreen(warning_msg))
                if not proceed:
                    self._show_error("⏸️ Staking cancelled - waiting for pending operations")
                    return

            # Close StakeScreen and return basic data to app
            # Passphrase and gas estimation will be handled in _handle_stake_action

            self.dismiss({
                "action": "stake",
                "amount": amount,
                "account": self.selected_account
            })

        except (ValueError, decimal.InvalidOperation) as ve:
            self._show_error("⚠️ Invalid amount format")
        except Exception as ex:
            self._show_error(f"⚠️ Staking failed: {str(ex)}")
            raise  # Re-raise to see full traceback

    @work(exclusive=True)
    @on(Button.Pressed, "#unstake_btn")
    async def unstake_pressed(self) -> None:
        """Handle unstaking action."""
        input_field = self.query_one("#input_field", Input)
        value = sanitize_input(input_field.value)

        if not value:
            self._show_error("⚠️ Please enter amount to unstake")
            return

        # Validate amount against staked balance
        staked_xtz = mutez_to_xtz(self.staked_mutez)
        is_valid, error_msg, amount = validate_amount(value, min_value=Decimal("0"), max_value=staked_xtz)
        if not is_valid:
            # Custom error message for unstaking
            if "must not exceed" in error_msg:
                self._show_error(f"⚠️ Cannot unstake more than staked ({format_xtz(staked_xtz)} XTZ)")
            else:
                self._show_error(f"⚠️ {error_msg}")
            return

        try:

            # Check for pending transactions
            from sassy_wallet.core.tezos import check_pending_operations
            pending_info = check_pending_operations(self.rpc, self.selected_account.address)

            if pending_info and pending_info.get('has_pending'):
                pending_count = pending_info.get('pending_count', 0)
                warning_msg = (
                    f"⚠️ [b]Pending Transactions Detected![/b]\n\n"
                    f"Found {pending_count} pending operation(s) for this wallet.\n"
                    f"Proceeding may cause counter errors.\n\n"
                    f"Wait 1-2 minutes for operations to confirm, then try again.\n\n"
                    f"Proceed anyway? (Not recommended)"
                )
                proceed = await self.app.push_screen_wait(ConfirmScreen(warning_msg))
                if not proceed:
                    self._show_error("⏸️ Unstaking cancelled - waiting for pending operations")
                    return

            # Close StakeScreen and return basic data to app
            # Passphrase and gas estimation will be handled in _handle_unstake_action

            self.dismiss({
                "action": "unstake",
                "amount": amount,
                "account": self.selected_account
            })

        except (ValueError, decimal.InvalidOperation):
            self._show_error("⚠️ Invalid amount format")

    async def _perform_delegation(self, baker_address: str, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> None:
        """Delegate to baker."""
        if not self.selected_account:
            return

        status_widget = self.query_one("#status_msg", Static)
        status_widget.update("[yellow]⏳ Delegating... This may take a moment...[/yellow]")

        # Get passphrase - using SAME logic as SEND (which works)
        passphrase = await self.app.push_screen_wait(  # type: ignore[attr-defined]
            SendPassphraseScreen(
                "🔐 Enter Your Passphrase",
                password=True,
                placeholder="Your wallet passphrase",
                wallet_info=f"[b]{self.selected_account.name}[/b]",
                ok_label="✅ Delegate!",
                fun_note="Delegate like a boss! Your XTZ will thank you! 🎯"
            )
        )

        if not passphrase:
            status_widget.update("[yellow]⏸️ Delegation cancelled[/yellow]")
            return

        try:
            _, can_send, _ = self.app._ensure_working_rpc()  # type: ignore[attr-defined]
            self.rpc = self.app.rpc  # type: ignore[attr-defined]
            if not can_send:
                status_widget.update("[red]❌ No RPC available to inject operations[/red]")
                return

            # Decrypt key
            secret_key = decrypt_secret(self.selected_account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            # Perform delegation with fee parameters
            op_hash = delegate_to_baker(self.rpc, key, baker_address, fee_mutez=fee_mutez, gas_limit=gas_limit, storage_limit=storage_limit)

            status_widget.update(f"[#34d399]✅ Delegation sent![/#34d399]\n[dim]Op: {op_hash} Waiting for confirmation...[/dim]")

            # Start spinner with baker-themed messages in main app
            baker_msg = get_baker_message()
            self.app._ui(self.app._start_spinner, baker_msg)  # type: ignore[attr-defined]

            # Set delegation pending state
            self._delegation_pending = True
            self.delegate_addr = baker_address  # Store baker address
            self._update_view()

            # Start polling for delegation confirmation
            self._start_delegation_polling()

        except Exception as e:
            log_error("Delegation failed", exception=e)
            # Stop spinner on error
            self.app._ui(self.app._stop_spinner)  # type: ignore[attr-defined]
            status_widget.update(f"[red]❌ Delegation failed: {str(e)}[/red]")
            # Also show error in main app
            self.app._set_status(f"[red]❌ Delegation failed: {str(e)}[/red]")  # type: ignore[attr-defined]

    async def _perform_staking(self, amount: Decimal, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> None:
        """Stake XTZ."""
        import traceback


        try:
            if not self.selected_account:
                return

            source_address = self.selected_account.address

            status_widget = self.query_one("#status_msg", Static)
            status_widget.update("[yellow]⏳ Staking... This may take a moment...[/yellow]")

            # Get passphrase - using SAME logic as SEND (which works)

            passphrase = await self.app.push_screen_wait(  # type: ignore[attr-defined]
                SendPassphraseScreen(
                    "🔐 Enter Your Passphrase",
                    password=True,
                    placeholder="Your wallet passphrase",
                    wallet_info=f"[b]{self.selected_account.name}[/b]",
                    ok_label="💎 Stake!",
                    fun_note="Time to become a CHAD! Lock in that XTZ! 💪🔥"
                )
            )


            if not passphrase:
                status_widget.update("[yellow]⏸️ Staking cancelled - passphrase not provided[/yellow]")
                return

            # Decrypt key
            _, can_send, _ = self.app._ensure_working_rpc()  # type: ignore[attr-defined]
            self.rpc = self.app.rpc  # type: ignore[attr-defined]
            if not can_send:
                status_widget.update("[red]❌ No RPC available to inject operations[/red]")
                return

            secret_key = decrypt_secret(self.selected_account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            key_pkh = key.public_key_hash()

            if source_address != key_pkh:
                status_widget.update(f"[red]❌ KEY MISMATCH! Wallet address doesn't match decrypted key[/red]")
                return

            # Perform staking
            op_hash = stake_xtz(self.rpc, key, amount, fee_mutez=fee_mutez, gas_limit=gas_limit, storage_limit=storage_limit)


            # Show success message
            status_widget.update(
                f"[#34d399]✅ STAKE SUCCESSFUL! You're a true CHAD now! 🔥💪[/#34d399]\n"
                f"[dim]Operation: {op_hash}[/dim]"
            )

            # Also show in main app status bar
            self.app._set_status(  # type: ignore[attr-defined]
                f"[#34d399]✅ Staked {format_xtz(amount)} XTZ successfully![/#34d399]"
            )

            # Trigger refresh to update display
            self.app.call_later(self.app._refresh_account)  # type: ignore[attr-defined]

            # Close modal after success
            self.call_later(lambda: self.dismiss(None))

        except Exception as e:

            # Extract meaningful error message
            error_msg = str(e)
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."

            # Show error in modal (if status_widget exists)
            try:
                status_widget = self.query_one("#status_msg", Static)
                status_widget.update(
                    f"[red]❌ Staking failed[/red]\n"
                    f"[dim]{error_msg}[/dim]\n"
                    f"[yellow]Check logs/wallet.log for details[/yellow]"
                )
            except:
                pass

            # Also show error in main app
            try:
                self.app._set_status(f"[red]❌ Staking failed - check logs[/red]")  # type: ignore[attr-defined]
            except:
                pass

    async def _perform_unstaking(self, amount: Decimal, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> None:
        """Unstake XTZ."""
        if not self.selected_account:
            return

        status_widget = self.query_one("#status_msg", Static)
        status_widget.update("[yellow]⏳ Unstaking... This may take a moment...[/yellow]")

        # Get passphrase - using SAME logic as SEND (which works)
        passphrase = await self.app.push_screen_wait(  # type: ignore[attr-defined]
            SendPassphraseScreen(
                "🔐 Enter Your Passphrase",
                password=True,
                placeholder="Your wallet passphrase",
                wallet_info=f"[b]{self.selected_account.name}[/b]",
                ok_label="💸 Unstake!",
                fun_note="Time to unlock that XTZ! Freedom awaits! 🔓✨"
            )
        )

        if not passphrase:
            status_widget.update("[yellow]⏸️ Unstaking cancelled[/yellow]")
            return

        try:
            _, can_send, _ = self.app._ensure_working_rpc()  # type: ignore[attr-defined]
            self.rpc = self.app.rpc  # type: ignore[attr-defined]
            if not can_send:
                status_widget.update("[red]❌ No RPC available to inject operations[/red]")
                return

            # Decrypt key
            secret_key = decrypt_secret(self.selected_account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            # Perform unstaking with fee parameters
            op_hash = unstake_xtz(self.rpc, key, amount, fee_mutez=fee_mutez, gas_limit=gas_limit, storage_limit=storage_limit)

            # Show success message in modal
            status_widget.update(
                f"[#34d399]✅ UNSTAKE SUCCESSFUL! XTZ unlocked! 💰[/#34d399]\n"
                f"[dim]Operation: {op_hash}[/dim]"
            )

            # Also show in main app status bar
            self.app._set_status(  # type: ignore[attr-defined]
                f"[#34d399]✅ Unstaked {format_xtz(amount)} XTZ successfully![/#34d399]"
            )

            # Trigger refresh to update display
            self.app.call_later(self.app._refresh_account)  # type: ignore[attr-defined]

            # Close modal after success
            self.call_later(lambda: self.dismiss(None))

        except Exception as e:
            log_error(f"Unstaking failed - Full error details", exception=e)
            # Extract meaningful error message
            error_msg = str(e)
            # If the error is too long, truncate but keep the important part
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."

            # Show error in modal status_widget (keep modal open)
            status_widget.update(
                f"[red]❌ Unstaking failed[/red]\n"
                f"[dim]{error_msg}[/dim]\n"
                f"[yellow]Check logs/wallet.log for details[/yellow]"
            )
            # Also show error in main app
            self.app._set_status(f"[red]❌ Unstaking failed - check logs[/red]")  # type: ignore[attr-defined]

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

            except Exception as e:
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
            hash_short = h[:10] + "..." + h[-8:] if len(h) > 20 else h

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
        width: auto;
        min-width: 65;
        max-width: 80;
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

        self.query_one("#send", Button).focus()
        self._estimate_worker()

    def on_unmount(self) -> None:
        self._stop_est_pulse()


    # -------------------------
    # Estimation pulse (ConfirmSendScreen)
    # -------------------------
    def _start_est_pulse(self) -> None:
        self._estimating = True
        self._est_i = 0
        if self._est_timer is None:
            self._est_timer = self.set_interval(Config.ESTIMATION_PULSE_INTERVAL, self._tick_est_pulse)

    def _stop_est_pulse(self) -> None:
        self._estimating = False
        if self._est_timer is not None:
            self._est_timer.stop()
            self._est_timer = None

    def _tick_est_pulse(self) -> None:
        if not self._estimating:
            return
        self._est_i += 1
        self._render_summary(estimating=True)
        self._update_fee_list(estimating=True)

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)

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
                "",
                f"[b cyan]Fee:[/b cyan]       {'[reverse]estimating…[/reverse]' if ((self._est_i // 3) % 2) else '[b]estimating…[/b]'}",
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
            est = self._estimate or {}
            reveal_needed = bool(est.get("reveal_needed"))
            fee_opts = est.get("fee_options") or {}
            chosen = fee_opts.get(self._fee_choice) or {}

            chosen_total = chosen.get("total_fee_xtz")
            tx = est.get("tx") or {}
            gas = int(tx.get("gas_limit") or 0)
            storage = int(tx.get("storage_limit") or 0)

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
                "",
                f"[b cyan]Fee ({self._fee_choice}):[/b cyan] {format_xtz(chosen_total) if chosen_total else '0'} XTZ",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))


    def _init_fee_list(self) -> None:
        """Create the 3 fixed fee rows once, keeping Label refs for fast updates."""
        lv = self.query_one("#fee_list", ListView)
        lv.clear()
        self._fee_labels = []
        for _ in range(3):
            lbl = Label("")
            self._fee_labels.append(lbl)
            lv.append(ListItem(lbl))

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        """Update fee rows text + checkmark without rebuilding ListView."""
        # Ensure list initialized
        if not self._fee_labels:
            self._init_fee_list()

        if estimating:
            texts = [
                "  Economy — estimating…",
                "  Normal — estimating…",
                "  Priority — estimating…",
            ]
        elif err or not self._estimate:
            texts = [
                "  Economy — unavailable",
                "  Normal — unavailable",
                "  Priority — unavailable",
            ]
        else:
            fee_opts = (self._estimate.get("fee_options") or {})
            order = [("economy", "Economy"), ("normal", "Normal"), ("priority", "Priority")]
            texts = []
            for key, title in order:
                d = fee_opts.get(key) or {}
                total_xtz = d.get("total_fee_xtz")
                mark = "✓ " if key == self._fee_choice else "  "
                texts.append(f"{mark}{title} — total fee: {format_xtz(total_xtz) if total_xtz else '0'} XTZ")

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        # Selection should commit only on Enter / click.
        idx = event.list_view.index
        if idx is None:
            return
        self._fee_choice = {0: "economy", 1: "normal", 2: "priority"}.get(idx, "normal")
        # Update checkmarks + summary (do NOT move highlight).
        self._update_fee_list(estimating=False)
        if self._estimate:
            self._render_summary(estimating=False)

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

                self.query_one("#fee_xtz", Input).value = str(mutez_to_xtz(fee_mutez))
                self.query_one("#gas_limit", Input).value = str(gas) if gas else ""
                self.query_one("#storage_limit", Input).value = str(storage) if storage else ""

            # ModalScreen doesn't provide call_from_thread in some Textual versions.
            # Use the App bridge instead.
            self.app.call_from_thread(_ui_apply)

        except Exception as e:
            log_error("Failed to estimate transaction fees", exception=e)
            # Report error safely on UI thread
            self.app.call_from_thread(self._stop_est_pulse)
            self.app.call_from_thread(self._update_fee_list, False, str(e))
            self.app.call_from_thread(self._render_summary, False, str(e))

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
            # Return to fee list for arrow keys
            try:
                self.query_one("#fee_list", ListView).focus()
            except Exception as e:
                log_error("Failed to focus fee list", exception=e)
                # Focus appropriate button based on context
                try:
                    self.query_one("#send", Button).focus()
                except:
                    try:
                        self.query_one("#delegate", Button).focus()
                    except:
                        pass

    def _parse_overrides(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
        fee_xtz_s = sanitize_input(self.query_one("#fee_xtz", Input).value or "")
        gas_s = sanitize_input(self.query_one("#gas_limit", Input).value or "")
        storage_s = sanitize_input(self.query_one("#storage_limit", Input).value or "")

        fee_mutez = None
        gas = None
        storage = None

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

    def _fee_choice_to_tx_fee_mutez(self) -> Optional[int]:
        if not self._estimate:
            return None
        fee_opts = (self._estimate.get("fee_options") or {})
        chosen = fee_opts.get(self._fee_choice) or {}
        tx_fee = chosen.get("tx_fee_mutez")
        try:
            return int(tx_fee) if tx_fee is not None else None
        except Exception as e:
            log_error("Failed to parse tx fee from choice", exception=e, tx_fee=tx_fee)
            return None

    @on(Button.Pressed, "#toggle")
    def toggle_pressed(self) -> None:
        self._toggle_advanced()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss({"ok": False, "fee_mutez": None, "gas_limit": None, "storage_limit": None})

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss({"__BACK__": True, "ok": False, "fee_mutez": None, "gas_limit": None, "storage_limit": None})

    @on(Button.Pressed, "#send")
    def send_pressed(self) -> None:
        # Modo Advanced => overrides manuales
        if self._advanced:
            try:
                fee_mutez, gas, storage = self._parse_overrides()
            except Exception as e:
                log_error("Failed to parse override values", exception=e)
                self._render_summary(err=str(e))
                return
            self.dismiss({"ok": True, "fee_mutez": fee_mutez, "gas_limit": gas, "storage_limit": storage})
            return

        # Modo normal => fee por selector, gas/storage = None (autofill)
        fee_mutez = self._fee_choice_to_tx_fee_mutez()
        self.dismiss({"ok": True, "fee_mutez": fee_mutez, "gas_limit": None, "storage_limit": None})

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)

        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return

        # Let Input/ListView handle keys naturally, but allow escape to blur first
        if isinstance(self.app.focused, (Input, ListView)):
            if key == "escape" and isinstance(self.app.focused, Input):
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
            return

        if key == "backspace" and self.show_back_button:
            self.back_pressed()
            event.stop()
            return

        # enter: si focus toggle => toggle; si focus cancel => cancel; si focus fee list => seleccionar; else send
        if key == "enter":
            try:
                if self.query_one("#toggle", Button).has_focus:
                    self._toggle_advanced()
                    return
                if self.query_one("#cancel", Button).has_focus:
                    self.cancel_pressed()
                    return
            except Exception as e:
                log_error("Failed to check button focus", exception=e)
            self.send_pressed()


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
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #eab308;
        padding: 1 2;
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
                yield Button("👑 DELEGATE", id="delegate", variant="primary")
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

        self.query_one("#delegate", Button).focus()
        self._estimate_worker()

    def on_unmount(self) -> None:
        self._stop_est_pulse()


    # -------------------------
    # Estimation pulse (ConfirmDelegateScreen)
    # -------------------------
    def _start_est_pulse(self) -> None:
        self._estimating = True
        self._est_i = 0
        if self._est_timer is None:
            self._est_timer = self.set_interval(Config.ESTIMATION_PULSE_INTERVAL, self._tick_est_pulse)

    def _stop_est_pulse(self) -> None:
        self._estimating = False
        if self._est_timer is not None:
            self._est_timer.stop()
            self._est_timer = None

    def _tick_est_pulse(self) -> None:
        if not self._estimating:
            return
        self._est_i += 1
        self._render_summary(estimating=True)
        self._update_fee_list(estimating=True)

    def _render_summary(self, estimating: bool = False, err: str = "") -> None:
        net = network_from_rpc(self.rpc)

        if estimating:
            lines = [
                "[b]Confirm delegation[/b]",
                "",
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]To:[/b yellow]        {self._baker_label}",
                "",
                f"[b yellow]Fee:[/b yellow]       {'[reverse]estimating…[/reverse]' if ((self._est_i // 3) % 2) else '[b]estimating…[/b]'}",
            ]
        elif err:
            lines = [
                "[b]Confirm delegation[/b]",
                "",
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
            est = self._estimate or {}
            reveal_needed = bool(est.get("reveal_needed"))
            fee_opts = est.get("fee_options") or {}
            chosen = fee_opts.get(self._fee_choice) or {}

            chosen_total = chosen.get("total_fee_xtz")
            tx = est.get("tx") or {}
            gas = int(tx.get("gas_limit") or 0)
            storage = int(tx.get("storage_limit") or 0)

            # Simple summary (suggested limits moved to separate widget)
            lines = [
                "[b]Confirm delegation[/b]",
                "",
                f"[b yellow]Network:[/b yellow]   {net}",
                "",
                f"[b yellow]From:[/b yellow]      {self.from_addr}",
                "",
                f"[b yellow]To:[/b yellow]        {self._baker_label}",
                "",
                f"[b yellow]Fee ({self._fee_choice}):[/b yellow] {format_xtz(chosen_total) if chosen_total else '0'} XTZ",
            ]

        self.query_one("#summary", Static).update("\n".join(lines))


    def _init_fee_list(self) -> None:
        """Create the 3 fixed fee rows once, keeping Label refs for fast updates."""
        lv = self.query_one("#fee_list", ListView)
        lv.clear()
        self._fee_labels = []
        for _ in range(3):
            lbl = Label("")
            self._fee_labels.append(lbl)
            lv.append(ListItem(lbl))

    def _update_fee_list(self, estimating: bool = False, err: str = "") -> None:
        """Update fee rows text + checkmark without rebuilding ListView."""
        # Ensure list initialized
        if not self._fee_labels:
            self._init_fee_list()

        if estimating:
            texts = [
                "  Economy — estimating…",
                "  Normal — estimating…",
                "  Priority — estimating…",
            ]
        elif err or not self._estimate:
            texts = [
                "  Economy — unavailable",
                "  Normal — unavailable",
                "  Priority — unavailable",
            ]
        else:
            fee_opts = (self._estimate.get("fee_options") or {})
            order = [("economy", "Economy"), ("normal", "Normal"), ("priority", "Priority")]
            texts = []
            for key, title in order:
                d = fee_opts.get(key) or {}
                total_xtz = d.get("total_fee_xtz")
                mark = "✓ " if key == self._fee_choice else "  "
                texts.append(f"{mark}{title} — total fee: {format_xtz(total_xtz) if total_xtz else '0'} XTZ")

        for lbl, txt in zip(self._fee_labels, texts):
            lbl.update(txt)

    @on(ListView.Selected, "#fee_list")
    def fee_selected(self, event: ListView.Selected) -> None:
        # Selection should commit only on Enter / click.
        idx = event.list_view.index
        if idx is None:
            return
        self._fee_choice = {0: "economy", 1: "normal", 2: "priority"}.get(idx, "normal")
        # Update checkmarks + summary (do NOT move highlight).
        self._update_fee_list(estimating=False)
        if self._estimate:
            self._render_summary(estimating=False)

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

                self.query_one("#fee_xtz", Input).value = str(mutez_to_xtz(fee_mutez))
                self.query_one("#gas_limit", Input).value = str(gas) if gas else ""
                self.query_one("#storage_limit", Input).value = str(storage) if storage else ""

            # ModalScreen doesn't provide call_from_thread in some Textual versions.
            # Use the App bridge instead.
            self.app.call_from_thread(_ui_apply)

        except Exception as e:
            log_error("Failed to estimate delegation fees", exception=e)
            # Report error safely on UI thread
            self.app.call_from_thread(self._stop_est_pulse)
            self.app.call_from_thread(self._update_fee_list, False, str(e))
            self.app.call_from_thread(self._render_summary, False, str(e))

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
            # Return to fee list for arrow keys
            try:
                self.query_one("#fee_list", ListView).focus()
            except Exception as e:
                log_error("Failed to focus fee list", exception=e)
                # Focus appropriate button based on context
                try:
                    self.query_one("#send", Button).focus()
                except:
                    try:
                        self.query_one("#delegate", Button).focus()
                    except:
                        pass

    def _parse_overrides(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
        fee_xtz_s = sanitize_input(self.query_one("#fee_xtz", Input).value or "")
        gas_s = sanitize_input(self.query_one("#gas_limit", Input).value or "")
        storage_s = sanitize_input(self.query_one("#storage_limit", Input).value or "")

        fee_mutez = None
        gas = None
        storage = None

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

    def _fee_choice_to_tx_fee_mutez(self) -> Optional[int]:
        if not self._estimate:
            return None
        fee_opts = (self._estimate.get("fee_options") or {})
        chosen = fee_opts.get(self._fee_choice) or {}
        tx_fee = chosen.get("tx_fee_mutez")
        try:
            return int(tx_fee) if tx_fee is not None else None
        except Exception as e:
            log_error("Failed to parse tx fee from choice", exception=e, tx_fee=tx_fee)
            return None

    @on(Button.Pressed, "#toggle")
    def toggle_pressed(self) -> None:
        self._toggle_advanced()

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss({"ok": False, "fee_mutez": None, "gas_limit": None, "storage_limit": None})

    @on(Button.Pressed, "#back")
    def back_pressed(self) -> None:
        self.dismiss({"__BACK__": True, "ok": False, "fee_mutez": None, "gas_limit": None, "storage_limit": None})

    @on(Button.Pressed, "#delegate")
    def delegate_pressed(self) -> None:
        # Advanced mode => manual overrides
        if self._advanced:
            try:
                fee_mutez, gas, storage = self._parse_overrides()
            except Exception as e:
                log_error("Failed to parse override values", exception=e)
                self._render_summary(err=str(e))
                return
            self.dismiss({"ok": True, "fee_mutez": fee_mutez, "gas_limit": gas, "storage_limit": storage})
            return

        # Normal mode => fee by selector, gas/storage = None (autofill)
        fee_mutez = self._fee_choice_to_tx_fee_mutez()
        self.dismiss({"ok": True, "fee_mutez": fee_mutez, "gas_limit": None, "storage_limit": None})

    def on_key(self, event) -> None:
        key = getattr(event, "key", None)

        if key == "escape":
            self.cancel_pressed()
            event.stop()
            return

        # Let Input/ListView handle keys naturally, but allow escape to blur first
        if isinstance(self.app.focused, (Input, ListView)):
            if key == "escape" and isinstance(self.app.focused, Input):
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
            return

        if key == "backspace" and self.show_back_button:
            self.back_pressed()
            event.stop()
            return

        # enter: if focus toggle => toggle; if focus cancel => cancel; else delegate
        if key == "enter":
            try:
                if self.query_one("#toggle", Button).has_focus:
                    self._toggle_advanced()
                    return
                if self.query_one("#cancel", Button).has_focus:
                    self.cancel_pressed()
                    return
            except Exception as e:
                log_error("Failed to check button focus", exception=e)
            self.delegate_pressed()


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

    SendScreen > Vertical {
        width: auto;
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        overflow-y: auto;
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
        min-height: 6;
        max-height: 8;
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
        max-height: 5;
    }

    SendScreen #quick_destinations > ListItem {
        padding: 0 0 0 2;
    }

    SendScreen #amount_label {
        margin-bottom: 0;
    }

    SendScreen #amount_comment {
        margin-top: 1;
        margin-bottom: 0;
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
        self._quick_destination_addrs: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical():
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

            # Load balances asynchronously
            self.run_worker(self._load_wallet_balances(), exclusive=False)

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
            hint = self.query_one("#hint_text", Static)
            hint.update("[dim]💡 Click below to quick-fill address[/dim]")

    async def _load_wallet_balances(self) -> None:
        """Load wallet balances asynchronously."""
        lv = self.query_one("#wallet_selector", ListView)
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        indices = list(range(len(self.accounts)))
        if self.selected_account:
            try:
                sel_idx = next(
                    i for i, acc in enumerate(self.accounts) if acc.address == self.selected_account.address
                )
                indices = [sel_idx] + [i for i in indices if i != sel_idx]
            except StopIteration:
                pass

        for idx in indices:
            acc = self.accounts[idx]
            try:
                addr_short = acc.address[:10] + "…" + acc.address[-8:]
                spin = spinner[idx % len(spinner)]
                try:
                    item = lv.children[idx]
                    label = item.children[0]
                    if isinstance(label, Label):
                        label.update(f"{spin} [b]{acc.name}[/b] [dim]Loading...[/dim]\n[dim]{addr_short}[/dim]")
                except Exception:
                    pass

                if acc.address in self._balance_cache:
                    balance_xtz = self._balance_cache[acc.address]
                else:
                    balance_mutez = get_balance_mutez(self.rpc, acc.address)
                    balance_xtz = mutez_to_xtz(balance_mutez)
                    self._balance_cache[acc.address] = balance_xtz
                balance_str = format_xtz(balance_xtz)
                label_text = f"[b]{acc.name}[/b] [#34d399]{balance_str} XTZ[/#34d399]\n[dim]{addr_short}[/dim]"

                # Update list item
                if idx < len(lv.children):
                    item = lv.children[idx]
                    if isinstance(item, ListItem) and item.children:
                        label = item.children[0]
                        if isinstance(label, Label):
                            label.update(label_text)

                # Update selected account balance if this is the one
                if self.selected_account and self.selected_account.address == acc.address:
                    self.balance_xtz = balance_xtz
                    self._balance_loading = False

            except Exception as e:
                log_error(f"Failed to load balance for {acc.name}", exception=e)
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
        cached = self._balance_cache.get(self.selected_account.address)
        if cached is not None:
            self.balance_xtz = cached
            self._balance_loading = False
        else:
            self.balance_xtz = Decimal(0)
            self._balance_loading = True

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
        except Exception as e:
            log_error("Failed to get wallet balance", exception=e)

    def _apply_selected_balance(self, address: str, balance_xtz: Decimal) -> None:
        if not self.selected_account or self.selected_account.address != address:
            return
        self.balance_xtz = balance_xtz
        self._balance_loading = False

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
        comment_widget = self.query_one("#amount_comment", Static)

        try:
            value = sanitize_input(event.value)
            if not value:
                comment_widget.update("")
                return

            amount = Decimal(value)
            if amount <= 0:
                comment_widget.update("")
                return

            # Show sassy comment based on amount
            from sassy_wallet.messages.send_commentary import get_amount_comment
            comment = get_amount_comment(amount)
            comment_widget.update(f"[dim italic]{comment}[/dim italic]")
        except (ValueError, decimal.InvalidOperation):
            comment_widget.update("")

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
            comment = self.query_one("#amount_comment", Static)
            comment.update("[red]✗ Please select a wallet first[/red]")
            return
        if self._balance_loading:
            comment = self.query_one("#amount_comment", Static)
            comment.update("[dim]⏳ Balance still loading...[/dim]")
            return

        # Get To address
        to_input = self.query_one("#to_input", Input)
        to_addr = sanitize_input(to_input.value)

        if not to_addr:
            hint = self.query_one("#hint_text", Static)
            hint.update("[red]✗ Please enter a destination address[/red]")
            to_input.focus()
            return

        # Validate address
        is_valid, error_msg = validate_tezos_address(to_addr, allow_kt1=True)
        if not is_valid:
            hint = self.query_one("#hint_text", Static)
            hint.update(f"[red]✗ {error_msg}[/red]")
            to_input.focus()
            return
        if self.selected_account and to_addr == self.selected_account.address:
            hint = self.query_one("#hint_text", Static)
            hint.update("[red]✗ Cannot send to the same wallet[/red]")
            to_input.focus()
            return

        # Get amount
        amount_input = self.query_one("#amount_input", Input)
        amount_str = sanitize_input(amount_input.value)

        if not amount_str:
            comment = self.query_one("#amount_comment", Static)
            comment.update("[red]✗ Please enter an amount[/red]")
            amount_input.focus()
            return

        # Validate amount
        is_valid, error_msg, amount = validate_amount(amount_str, min_value=Decimal("0"))
        if not is_valid:
            comment = self.query_one("#amount_comment", Static)
            comment.update(f"[red]✗ {error_msg}[/red]")
            amount_input.focus()
            return

        # Check sufficient balance
        estimated_max_fee = Decimal("0.01")
        total_needed = amount + estimated_max_fee

        if self.balance_xtz < total_needed:
            comment = self.query_one("#amount_comment", Static)
            comment.update(
                f"[red]✗ Insufficient balance. Have: {format_xtz(self.balance_xtz)} XTZ, "
                f"Need: ~{format_xtz(total_needed)} XTZ (including fees)[/red]"
            )
            amount_input.focus()
            return

        # All good, return data
        self.dismiss({
            "from_account": self.selected_account,
            "to_addr": to_addr,
            "amount": amount
        })

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        from textual.widgets import Input

        key = getattr(event, "key", None)

        # Let Input handle keys naturally, but allow escape to blur first
        if isinstance(self.app.focused, Input):
            if key == "escape":
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
                return
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

    @on(Input.Changed, "#dest_inp")
    def on_dest_input_changed(self, event: Input.Changed) -> None:
        """Validate destination address in real-time."""
        value = sanitize_input(event.value)
        hint_widget = self.query_one("#dest_validation_hint", Static)
        sassy_widget = self.query_one("#sassy_comment", Static)

        if not value:
            hint_widget.update("")
            sassy_widget.update("")
            return

        # Check if sending to self
        if value == self.from_address:
            hint_widget.update("[red]✗ Cannot send to yourself[/red]")
            sassy_widget.update("")
            return

        # Validate address
        is_valid, error_msg = validate_tezos_address(value, allow_kt1=True)
        if is_valid:
            hint_widget.update("[#34d399]✓ Valid Tezos address[/#34d399]")
            # Show a sassy comment when address is valid
            sassy_widget.update(f"[dim italic]{get_recipient_comment()}[/dim italic]")
        else:
            sassy_widget.update("")
            # Only show error if the address looks complete (36 characters)
            if len(value) >= 36:
                hint_widget.update(f"[red]✗ {error_msg}[/red]")
            elif len(value) > 3:
                hint_widget.update("[yellow]⏳ Enter complete address (36 characters)...[/yellow]")
            else:
                hint_widget.update("")

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

        if isinstance(self.app.focused, Input):
            if key == "escape":
                try:
                    self.query_one("#cancel", Button).focus()
                except Exception:
                    pass
                event.stop()
                return

        if key == "escape":
            self.dismiss("")
            event.stop()
            return

        if key == "down":
            try:
                inp = self.query_one("#dest_inp", Input)
                lv = self.query_one("#recent_list", ListView)
                if inp.has_focus:
                    lv.focus()
                    return
            except Exception as e:
                log_error("Failed to handle down key in destination picker", exception=e)

        if key == "enter":
            try:
                lv = self.query_one("#recent_list", ListView)
                if lv.has_focus and self.recents:
                    idx = lv.index or 0
                    if 0 <= idx < len(self.recents):
                        self.dismiss(self.recents[idx])
                        return
            except Exception as e:
                log_error("Failed to handle enter key in destination picker", exception=e)


class WalletApp(App):
    CSS = """
    Screen {
        padding: 1 24;
        align: center top;
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
        background: #111827;
        color: #e5e7eb;
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
        background: rgba(59, 130, 246, 0.5);
    }

    ListView:focus > ListItem.--highlight,
    ListView:focus > ListItem.--selected {
        background: rgba(59, 130, 246, 0.5);
    }

    #banner {
        height: auto;
        margin-bottom: 1;
        padding: 1 1;
    }

    #accounts_header {
        height: auto;
        margin-bottom: 1;
        align: left middle;
    }

    #tagline {
        content-align: center middle;
        margin-left: 2;
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

    #accounts_columns_header {
        height: 1;
        margin-bottom: 0;
        padding-left: 2;
        color: $accent;
    }

    #accounts {
        height: auto;
        max-height: 3;
        margin-bottom: 1;
    }

    #accounts > ListItem {
        margin-bottom: 0;
        padding: 0 0 0 2;
        height: 1;
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
        margin-bottom: 1;
    }

    #action_buttons {
        height: auto;
        margin-top: 1;
        margin-bottom: 0;
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
        margin-top: 1;
        margin-bottom: 1;
        color: $accent;
        padding-left: 2;
    }

    #history_headers {
        height: 1;
        margin-bottom: 0;
        color: $accent;
    }

    #history_header {
        width: 50%;
        padding-left: 2;
        color: $accent;
        background: $surface;
    }

    #tx_detail_header {
        width: 50%;
        padding-left: 1;
        color: $accent;
        background: $surface;
        border-left: solid $primary;
    }

    #history_split {
        height: 1fr;
    }

    #history {
        width: 50%;
        height: 100%;
    }

    #history > ListItem {
        padding: 0 0 0 2;
    }

    #tx_detail_pane {
        width: 50%;
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
        margin-top: 1;
        margin-bottom: 1;
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

    #rpc_indicator {
        width: auto;
        padding: 0 1;
        text-align: right;
        color: #16a34a;
        text-style: bold;
        background: $boost;
    }

    #rpc_indicator:hover {
        background: $boost;
        color: #16a34a;
        text-style: bold;
    }

    /* Status bar states with glow effects */
    #bottom_bar.status-success {
        border: heavy #22c55e;
        background: #052e16;
    }

    #bottom_bar.status-warning {
        border: heavy #eab308;
        background: #422006;
    }

    #bottom_bar.status-error {
        border: heavy #ef4444;
        background: #450a0a;
    }

    #bottom_bar.status-info {
        border: heavy #3b82f6;
        background: #172554;
    }

    #bottom_bar.status-stake {
        border: heavy #8b5cf6;
        background: #1f1336;
    }

    #bottom_bar.status-unstake {
        border: heavy #111827;
        background: #0b0b0b;
    }

    #bottom_bar.status-unstake-dim {
        border: heavy #1f2937;
        background: #1f1f1f;
    }

    #status_line.status-success {
        color: #22c55e;
        background: #052e16;
    }

    #status_line.status-warning {
        color: #eab308;
        background: #422006;
    }

    #status_line.status-error {
        color: #ef4444;
        background: #450a0a;
    }

    #status_line.status-info {
        color: #3b82f6;
        background: #172554;
    }

    #status_line.status-stake {
        color: #c4b5fd;
        background: #1f1336;
    }

    #status_line.status-unstake {
        color: #e5e7eb;
        background: #0b0b0b;
    }

    #status_line.status-unstake-dim {
        color: #d1d5db;
        background: #1f1f1f;
    }

    /* Processing state with orange glow (breathing effect handled by timer) */
    #bottom_bar.status-processing {
        border: heavy #f97316;
        background: #431407;
    }

    #status_line.status-processing {
        color: #f97316;
        background: #431407;
    }

    #bottom_bar.status-processing-dim {
        border: heavy #c2410c;
        background: #292524;
    }

    #status_line.status-processing-dim {
        color: #c2410c;
        background: #292524;
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
        self.rpc = self.store.get("rpc") or Config.RPC_DEFAULT_GHOSTNET
        logging.info(f"RPC: {self.rpc}")
        self.accounts = list_accounts(self.store)
        logging.info(f"Loaded {len(self.accounts)} account(s)")
        self.selected: Account | None = None

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

        self._last_status: str = ""
        self._status_lock_until_refresh: bool = False

        self._send_in_progress: bool = False

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
        yield Static(logo, id="banner")

        with Vertical():
            # Accounts section with action buttons
            with Horizontal(id="accounts_header"):
                yield Button("Import (i)", id="add")
                yield Button("Backup (b)", id="backup")
                yield Button("Delete (Del)", id="delete")
                yield Static("💅 A wallet with an attitude", id="tagline")
            # Column headers for wallet list (aligned with content format: name:<30 + " │ " + address)
            # "Wallet" (6 chars) + 25 spaces to move │ right, aligning with content format
            yield Static("[b]Wallet                         │ Address[/b]", id="accounts_columns_header", markup=True)
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
            yield Static(f"[b]Recent Transactions[/b] (last {self.history_limit})", id="hist_title", markup=True)
            # Column headers for both panels with fixed widths matching content
            with Horizontal(id="history_headers"):
                # Fixed widths: #=3, Time=14, Type=5, Amount=15, Destination=20, Status=7
                header_line = f"{'#':<3} {'Time':<14}  {'Type':<5}  {'Amount':<15}  {'Destination':<20}  {'Status':<7}"
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
                yield Static("● RPC", id="rpc_indicator", markup=True)

        yield Footer()

    def on_mount(self) -> None:
        # Store the main thread ID for thread safety checks
        self._thread_id = threading.get_ident()

        self._update_rpc_indicator()
        self._render_accounts()
        # Auto-pick an RPC that supports BOTH simulation and injection.
        # Many public RPCs are read-only or restrict sensitive endpoints.
        self._autodetect_rpc()

        # Start auto-refresh if enabled
        if self._auto_refresh_enabled:
            self._start_auto_refresh()

    def on_unmount(self) -> None:
        """Cleanup timers on app close."""
        if self._spin_timer:
            self._spin_timer.stop()
            self._spin_timer = None

        if self._auto_refresh_timer:
            self._auto_refresh_timer.stop()
            self._auto_refresh_timer = None

        log_info("WalletApp unmounted, timers cleaned up")

    def on_key(self, event) -> None:
        """Handle key events at App level.

        CRITICAL: Block app-level keybindings when a modal is open.
        This prevents actions from firing behind the modal.
        """
        from textual.screen import ModalScreen

        if isinstance(self.screen, ModalScreen):
            key = getattr(event, "key", None)
            if key in ("left", "right") and isinstance(self.focused, Button):
                parent = self.focused.parent
                if isinstance(parent, Horizontal):
                    focusables = [
                        c
                        for c in parent.children
                        if isinstance(c, Button) and not c.has_class("hidden") and getattr(c, "visible", True)
                    ]
                    if self.focused in focusables:
                        idx = focusables.index(self.focused)
                        if key == "left" and idx > 0:
                            focusables[idx - 1].focus()
                            event.stop()
                            return
                        if key == "right" and idx < len(focusables) - 1:
                            focusables[idx + 1].focus()
                            event.stop()
                            return
            event.stop()
            return
        # If no modal, let normal key handling proceed (bindings, etc.)

        key = getattr(event, "key", None)
        if key == "down" and self.focused is None:
            try:
                self.query_one("#add", Button).focus()
            except Exception:
                pass
            event.stop()
            return
        if key == "up" and self.focused is None:
            try:
                self.query_one("#send", Button).focus()
            except Exception:
                pass
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
                except Exception:
                    pass
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
        except Exception as e:
            log_error("Failed to check thread ID in _ui", exception=e)
        return self.call_from_thread(fn, *args, **kwargs)

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
        except Exception as e:
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
        self._last_status = text
        # Status messages shown in status_line
        try:
            self.query_one("#status_line", Static).update(text)
        except Exception as e:
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

        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            # Update text
            status_widget.update(text)

            # Remove all status classes first
            for cls in [
                "status-success",
                "status-warning",
                "status-error",
                "status-info",
                "status-stake",
                "status-unstake",
                "status-unstake-dim",
                "status-processing",
                "status-processing-dim",
            ]:
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

        except Exception as e:
            log_error("Failed to set styled status", exception=e)

    def _revert_status_style(self) -> None:
        """Revert status bar to default styling."""
        if self._status_lock_until_refresh:
            return
        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            for cls in [
                "status-success",
                "status-warning",
                "status-error",
                "status-info",
                "status-stake",
                "status-unstake",
                "status-unstake-dim",
                "status-processing",
                "status-processing-dim",
            ]:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

        except Exception as e:
            log_error("Failed to revert status style", exception=e)

    def _set_status_styled_locked(self, text: str, style: str) -> None:
        """Set a styled status that stays until refresh."""
        self._status_lock_until_refresh = True
        self._set_status_styled(text, style=style, duration=0.0, force=True)

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
            for cls in [
                "status-success",
                "status-warning",
                "status-error",
                "status-info",
                "status-stake",
                "status-unstake",
                "status-unstake-dim",
                "status-processing",
                "status-processing-dim",
            ]:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

            # Start with bright state
            status_widget.add_class(bright_class)
            bottom_bar.add_class(bright_class)

            # Schedule breathing toggle
            self._breathing_timer = self.set_timer(0.8, self._toggle_breathing)

        except Exception as e:
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
            self._breathing_timer = self.set_timer(0.8, self._toggle_breathing)

        except Exception as e:
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
            for cls in ["status-processing", "status-processing-dim", "status-unstake", "status-unstake-dim"]:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

        except Exception as e:
            log_error("Failed to stop breathing effect", exception=e)

    def _set_busy(self, busy: bool) -> None:
        for bid in ("#add", "#backup", "#export", "#delete", "#refresh", "#send", "#recv", "#stake"):
            # Use query() to check if button exists before accessing
            btns = self.query(bid)
            if btns:
                try:
                    btns.first(Button).disabled = busy
                except Exception as e:
                    log_error("Failed to set button busy state", exception=e, button_id=bid)

    def _update_rpc_indicator(self) -> None:
        """Update the RPC indicator in bottom-right corner with RPC URL."""
        try:
            # Shorten RPC URL for display
            rpc_short = self.rpc.replace("https://", "").replace("http://", "")
            if len(rpc_short) > 35:
                rpc_short = rpc_short[:32] + "..."

            # Show connection status with green dot
            status_indicator = "[#34d399]●[/#34d399]"

            # Display: ● rpc.tzkt.io/mainnet
            self.query_one("#rpc_indicator", Static).update(f"{status_indicator} {rpc_short}")
        except Exception as e:
            log_error("Failed to update RPC indicator", exception=e)
            try:
                self.query_one("#rpc_indicator", Static).update("[red]●[/red] Offline")
            except Exception as e2:
                log_error("Failed to set RPC indicator to offline", exception=e2)

    def _show_tx_link(self, oph_short: str, tzkt_url: str) -> None:
        """Show transaction hash with link to TzKT explorer.

        Args:
            oph_short: Shortened operation hash for display
            tzkt_url: Full TzKT explorer URL
        """
        try:
            log_error(f"[TX_LINK DEBUG] Input - oph_short: {oph_short}, tzkt_url: {tzkt_url}")

            # Validate URL starts with http/https
            if not tzkt_url.startswith(('http://', 'https://')):
                tzkt_url = f"https://{tzkt_url}"

            log_error(f"[TX_LINK DEBUG] After validation - tzkt_url: {tzkt_url}")

            # Create clickable link with copy hint - escape any ] in the hash
            oph_display = oph_short.replace(']', '&#93;')
            link_text = f"📋 [link=\"{tzkt_url}\"]{oph_display}[/link] | [dim]Check TzKT →[/dim]"

            log_error(f"[TX_LINK DEBUG] Final link_text: {link_text}")

            self.query_one("#tx_link_area", Static).update(link_text)
        except Exception as e:
            log_error("Failed to show transaction link", exception=e)

    def _clear_tx_link(self) -> None:
        """Clear the transaction link area."""
        try:
            self.query_one("#tx_link_area", Static).update("")
        except Exception as e:
            log_error("Failed to clear transaction link", exception=e)

    def _update_history_title(self, suffix: str = "") -> None:
        self.query_one("#hist_title", Static).update(
            f"[b]Recent Transactions[/b] (last {self.history_limit}){suffix}"
        )

    def _update_tx_details(self) -> None:
        """Update the transaction details pane with the selected transaction."""
        try:
            detail_pane = self.query_one("#tx_detail_content", Static)
        except Exception as e:
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
            except Exception:
                pass
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
                except Exception:
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
                except Exception:
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
        except Exception:
            pass

    def _focus_action_buttons(self) -> None:
        try:
            self.query_one("#send", Button).focus()
        except Exception:
            pass

    def _focus_accounts_header(self) -> None:
        try:
            self.query_one("#add", Button).focus()
        except Exception:
            pass

    def _focus_accounts_list(self) -> None:
        try:
            lv = self.query_one("#accounts", ListView)
            if lv.index is None:
                lv.index = 0
            lv.focus()
        except Exception:
            pass

    def _focus_history_list(self) -> None:
        try:
            lv = self.query_one("#history", ListView)
            if lv.index is None:
                lv.index = 0
            lv.focus()
        except Exception:
            pass

    def _focus_tx_details(self) -> None:
        try:
            self.query_one("#tx_detail_content", Static).focus()
        except Exception:
            pass

    # -------------------------
    # Accounts
    # -------------------------
    def _render_accounts(self) -> None:
        lv = self.query_one("#accounts", ListView)
        lv.clear()

        self.accounts = list_accounts(self.store)

        if not self.accounts:
            self.selected = None
            self._update_status_balance()  # This will clear wallet details
            self._render_history([])
            # Show a fun motivational message from the library
            lv.append(ListItem(Label(f"[yellow]{self._empty_wallet_message}[/yellow]", markup=True)))
            return

        for a in self.accounts:
            tag = " (watch)" if a.enc is None else ""
            # Shorten address for display
            addr_short = a.address[:10] + "…" + a.address[-8:]
            # Align addresses by using fixed-width name column
            name_with_tag = f"{a.name}{tag}"
            marker = self._marker_for_address(a.address)
            label_text = f"{name_with_tag:<30} │ {addr_short}{marker}"
            lv.append(ListItem(Label(label_text)))

        if self.accounts:
            self.selected = self.accounts[0]
            self._last_selected_addr = self.selected.address
            self._update_status_balance()
            # Defer history load so name/balance render first
            self.set_timer(0.2, lambda: self._load_history_for_selected(force=True, quiet=True))
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

    def _apply_account_selection(self, idx: int) -> None:
        addr = self.accounts[idx].address
        if self._history_loaded_addr != addr:
            self._show_account_loading(idx)
        if self._last_selected_addr != addr:
            prev_addr = self._last_selected_addr
            self.selected = self.accounts[idx]
            self._last_selected_addr = addr
            self._update_status_balance()
            if prev_addr:
                self._refresh_account_row(prev_addr)
        self._load_history_for_selected(force=True, quiet=True)
        self._update_tx_details()

    def _marker_for_address(self, address: str) -> str:
        if address and self._last_selected_addr == address:
            return " 🥐"
        return ""

    def _render_account_row(self, idx: int, *, loading: bool = False) -> None:
        try:
            lv = self.query_one("#accounts", ListView)
            item = list(lv.children)[idx]
            label = item.query_one(Label)
            acc = self.accounts[idx]
            tag = " (watch)" if acc.enc is None else ""
            addr_short = acc.address[:10] + "…" + acc.address[-8:]
            name_with_tag = f"{acc.name}{tag}"
            suffix = "  [dim]Loading…[/dim]" if loading else ""
            marker = self._marker_for_address(acc.address)
            label.update(f"{name_with_tag:<30} │ {addr_short}{suffix}{marker}")
        except Exception:
            pass

    def _show_account_loading(self, idx: int) -> None:
        self._render_account_row(idx, loading=True)

    def _clear_account_loading(self, address: str) -> None:
        try:
            idx = next(i for i, acc in enumerate(self.accounts) if acc.address == address)
        except StopIteration:
            return
        self._render_account_row(idx, loading=False)

    def _refresh_account_row(self, address: str) -> None:
        try:
            idx = next(i for i, acc in enumerate(self.accounts) if acc.address == address)
        except StopIteration:
            return
        self._render_account_row(idx, loading=False)

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
        except Exception as e:
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

        if not items:
            if not self.accounts:
                hv.append(ListItem(Label("Import a wallet to see transactions here.")))
            else:
                hv.append(ListItem(Label("No transactions yet. Press 's' to send or 'x' to receive.")))
            try:
                self.query_one("#tx_detail_content", Static).update("No transactions available")
            except Exception as e:
                log_error("Failed to update tx detail content", exception=e)
            return

        for idx, it in enumerate(items, start=1):
            # Use relative time instead of full timestamp
            ts_raw = it.get("ts") or ""
            ts = format_relative_time(ts_raw)

            direction = it.get("direction") or "?"
            amt: Decimal = it.get("amount_xtz") or Decimal(0)
            cp = it.get("counterparty") or "?"

            # Format amount with fixed width for alignment
            amt_formatted = format_xtz(amt)

            # Fixed width columns for perfect alignment
            # Column widths: Time=14, Type=5, Amount=15, Destination=20, Status=7
            if direction == "IN":
                # Fixed 15-char field for amount (includes sign and XTZ)
                amt_str = f"[#34d399]{f'+{amt_formatted} XTZ':<15}[/#34d399]"
            elif direction == "OUT":
                # Fixed 15-char field for amount
                amt_str = f"[red]{f'-{amt_formatted} XTZ':<15}[/red]"
            elif direction == "STK":
                amt_str = f"[#8b5cf6]{f'-{amt_formatted} XTZ':<15}[/#8b5cf6]"
            elif direction == "UST":
                amt_str = f"[#8b5cf6]{f'+{amt_formatted} XTZ':<15}[/#8b5cf6]"
            elif direction == "DEL":
                amt_str = f"[yellow]{f'---':<15}[/yellow]"
            elif direction == "UND":
                amt_str = f"[yellow]{f'---':<15}[/yellow]"
            else:
                amt_str = f"{f'{amt_formatted} XTZ':<15}"

            kind = (it.get("kind") or "").lower()
            entrypoint = (it.get("entrypoint") or "").lower()
            if kind == "delegation":
                type_raw = "DLG"
            elif entrypoint == "stake":
                type_raw = "STK"
            elif entrypoint == "unstake":
                type_raw = "UST"
            else:
                type_raw = "TX"

            if type_raw == "DLG":
                type_text = f"[yellow]{type_raw:<5}[/yellow]"
            elif type_raw in ("STK", "UST"):
                type_text = f"[#8b5cf6]{type_raw:<5}[/#8b5cf6]"
            else:
                type_text = f"{type_raw:<5}"

            # Truncate and pad counterparty address to fixed width
            if len(cp) > 20:
                cp_display = (cp[:10] + "…" + cp[-9:])  # Will be exactly 20 chars
            else:
                cp_display = f"{cp:<20}"  # Pad to 20 chars

            # Single line format with fixed widths for perfect alignment
            # Format: [3 #] [14 time] [5 type] [15 amount] [20 destination] [7 status]
            ts_padded = f"{ts:<14}"
            status = (it.get("status") or "CONFIRMED").upper()
            if status == "PENDING":
                status_label = "PENDING"
            elif status == "UNKNOWN":
                status_label = "UNKNOWN"
            elif status == "FAILED":
                status_label = "FAIL"
            else:
                status_label = "OK"

            if status == "FAILED":
                status_color = "red"
            elif direction in ("STK", "UST"):
                status_color = "#8b5cf6"
            elif direction in ("DEL", "UND"):
                status_color = "yellow"
            else:
                status_color = "green"

            status_text = f"[{status_color}]{status_label:<7}[/{status_color}]"

            idx_text = f"{idx:<3}"
            line = f"{idx_text} {ts_padded}  {type_text}  {amt_str}  {cp_display}  {status_text}"

            hv.append(ListItem(Label(line, markup=True)))

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
                except Exception as e:
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
            except Exception as e:
                log_error("Failed to select first transaction", exception=e)

    def _history_cache_key(self, address: str) -> tuple[str, int]:
        return (address, self.history_limit)

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
                if quiet:
                    return
                # Refresh in background to reconcile cache with indexer
                self._load_history(addr, self.history_limit, quiet=True)
                return

        self._load_history(addr, self.history_limit, quiet=quiet)

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
            self._ui(self._render_history, items)
            self._ui(self._set_history_loaded_addr, address)
            if not quiet:
                if self._history_requested_more:
                    self._ui(
                        self._set_status_styled_locked,
                        "🥖 10 more baguettes ready to eat!",
                        "success",
                    )
                else:
                    self._ui(self._set_status, get_message("refresh_success"))
            self._ui(self._clear_account_loading, address)
        except Exception as e:
            log_error("Failed to load history", exception=e, address=address, limit=limit)
            self._ui(self._render_history, [])
            if not quiet:
                self._ui(self._set_status, f"❌ Display shelf check failed: {e}")
            self._ui(self._clear_account_loading, address)
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
                seen_hashes.add(h)
            merged.append(item)

        with self._pending_ops_lock:
            for oph, pending in list(self._pending_ops.items()):
                if pending.get("address") != address:
                    continue
                if oph in seen_hashes:
                    self._pending_ops.pop(oph, None)
                    pending_changed = True
                    continue
                age = now - float(pending.get("ts_epoch") or 0.0)
                if pending.get("status") == "PENDING" and age > Config.PENDING_TX_TIMEOUT_SECONDS:
                    pending["status"] = "UNKNOWN"
                    pending_changed = True
                if resolve_pending and pending.get("status") == "UNKNOWN":
                    try:
                        resolved = resolve_tx_by_hash(self.rpc, address, oph)
                        if resolved:
                            self._pending_ops.pop(oph, None)
                            pending_changed = True
                            resolved_items.append(resolved)
                            continue
                    except Exception:
                        pass
                merged.append(dict(pending))

        merged.extend(resolved_items)
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
            except Exception:
                pass
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

    def _format_baker_label(self, baker_addr: Optional[str]) -> str:
        if not baker_addr:
            return "?"
        info = get_baker_info(self.rpc, baker_addr)
        alias = info.get("alias") if info else None
        return alias or baker_addr

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
    ) -> None:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        item = {
            "ts": ts,
            "direction": direction,
            "amount_xtz": amount_xtz,
            "counterparty": counterparty,
            "hash": oph,
            "kind": kind,
            "entrypoint": entrypoint,
            "status": "PENDING",
            "address": address,
            "ts_epoch": time.time(),
        }

        with self._pending_ops_lock:
            self._pending_ops[oph] = item
        self._persist_pending_ops()

        if self.selected and self.selected.address == address:
            self._invalidate_history_cache(address)
            self._load_history_for_selected(force=True)

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
            try:
                idx = next(i for i, acc in enumerate(self.accounts) if acc.address == self.selected.address)
                self._show_account_loading(idx)
            except StopIteration:
                pass
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
        self._load_history_for_selected(force=True)

    def action_toggle_auto_refresh(self) -> None:
        """Toggle automatic refresh on/off."""
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

        import random

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
        self._set_status_styled_locked(random.choice(net_msgs), style="info")
        if self.selected:
            self._update_status_balance()
            self._load_history_for_selected(force=True, quiet=True)

    @work(exclusive=True)
    async def action_rpc(self) -> None:
        old_rpc = self.rpc
        choice = await self.push_screen_wait(RpcPickerScreen(current_rpc=self.rpc))
        if not choice or choice == old_rpc:
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
        import random

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
        self._set_status_styled_locked(random.choice(oven_msgs), style="info")
        if self.selected:
            self._update_status_balance()
            self._load_history_for_selected(force=True, quiet=True)

    def action_receive(self) -> None:
        if not self.accounts:
            self._set_status("🥐 Receive what, exactly? Fancy some croissant? Import a wallet first. ¬_¬")
            return
        if not self.selected:
            self._set_status("ℹ️ No account selected")
            return
        self.push_screen(ReceiveScreen(self.selected.address, self.accounts))

    @work(exclusive=True)
    async def action_quit(self) -> None:
        import random

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
        line = random.choice(exit_lines)
        message = f"[b #f59e0b]{line}[/b #f59e0b]\n\nAre you sure you want to exit?"
        confirmed = await self.push_screen_wait(
            ConfirmScreen(
                message,
                title="Exit",
                yes_label="Exit",
                no_label="Stay",
            )
        )
        if confirmed:
            self.exit()

    @work(exclusive=True)
    async def action_stake(self) -> None:
        """Open stake/delegation modal and handle the returned action."""
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
                wallet_info_cache=self._stake_wallet_info_cache
            )
        )

        # If user cancelled or closed modal, stake_data will be None
        if not stake_data:
            return

        # Handle the action based on what was returned
        action = stake_data.get("action")

        if action == "stake":
            await self._handle_stake_action(stake_data)
        elif action == "unstake":
            await self._handle_unstake_action(stake_data)
        elif action == "delegate":
            await self._handle_delegate_action(stake_data)

    async def _handle_stake_action(self, stake_data: dict) -> None:
        """
        Handle staking operation with new flow:
        1. Request passphrase (decrypt key)
        2. Estimate gas and show confirmation screen
        3. Execute stake operation
        """
        import traceback
        from sassy_wallet.core.tezos import stake_xtz, key_from_encoded_secret
        from sassy_wallet.core.crypto import decrypt_secret

        account = stake_data.get("account")
        amount = stake_data.get("amount")

        if not account or amount is None:
            log_error("Invalid stake data received", stake_data=stake_data)
            self._set_status("❌ Invalid stake data")
            return


        # Step 1: Request passphrase and decrypt key
        passphrase = await self.push_screen_wait(
            StakePassphraseScreen(
                "🔐 Enter Your Passphrase",
                password=True,
                placeholder="Your wallet passphrase",
                wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                ok_label="Next →",
                fun_note="Keep your keys safe. Never share this passphrase. 🔐🥖",
                show_back_button=True
            )
        )

        if passphrase == "__BACK__":
            self.call_later(self.action_stake)
            return

        if not passphrase:
            self._set_status("👀 Chad mode has to wait — staking canceled.")
            return

        try:
            _, can_send, _, can_stake = self._ensure_working_rpc_for_stake(account.address)
            if not can_send:
                self._set_status("[red]❌ No RPC available to inject operations[/red]")
                return
            if not can_stake:
                self._set_status("[red]❌ RPC/protocol does not support stake operations[/red]")
                return

            # Decrypt key
            secret_key = decrypt_secret(account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            key_pkh = key.public_key_hash()

            if account.address != key_pkh:
                self._set_status("❌ KEY MISMATCH! Wallet address doesn't match decrypted key")
                return

            # Step 2: Show confirmation screen with gas estimation
            confirm_result = await self.push_screen_wait(
                ConfirmStakeScreen(
                    rpc=self.rpc,
                    key=key,
                    address=account.address,
                    amount=amount,
                    show_back_button=True
                )
            )

            if not confirm_result or not confirm_result.get("ok"):
                if confirm_result and confirm_result.get("__BACK__"):
                    passphrase_retry = await self.push_screen_wait(
                        StakePassphraseScreen(
                            "🔐 Enter Your Passphrase",
                            password=True,
                            placeholder="Your wallet passphrase",
                            wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                            ok_label="Next →",
                            fun_note="Keep your keys safe. Never share this passphrase. 🔐🥖",
                            show_back_button=True
                        )
                    )
                    if passphrase_retry == "__BACK__":
                        self.call_later(self.action_stake)
                        return
                    if not passphrase_retry:
                        self._set_status("👀 Chad mode has to wait — staking canceled.")
                        return
                    passphrase = passphrase_retry
                    secret_key = decrypt_secret(account.enc, passphrase)
                    key = key_from_encoded_secret(secret_key)
                else:
                    self._set_status("👀 Chad mode has to wait — staking canceled.")
                    return

            # Step 3: Execute staking operation with confirmed parameters
            fee_mutez = confirm_result.get("fee_mutez")
            gas_limit = confirm_result.get("gas_limit")
            storage_limit = confirm_result.get("storage_limit")

            self._start_breathing_effect("⏳ Staking... This may take a moment...")

            op_hash = stake_xtz(
                self.rpc,
                key,
                amount,
                fee_mutez=fee_mutez,
                gas_limit=gas_limit,
                storage_limit=storage_limit,
            )

            baker_addr = get_delegation_info(self.rpc, account.address)
            baker_label = self._format_baker_label(baker_addr)
            self._add_pending_tx(
                address=account.address,
                oph=op_hash,
                direction="STK",
                amount_xtz=amount,
                counterparty=baker_label,
                kind="transaction",
                entrypoint="stake",
            )

            # Show success
            self._stop_breathing_effect()
            self._status_lock_until_refresh = True
            self._set_status_styled(
                f"✅ Staked {format_xtz(amount)} XTZ successfully! 💪🔥",
                style="stake",
                duration=0.0,
                force=True,
            )

            # Trigger refresh
            self.call_later(self._refresh_account)

        except Exception as e:

            error_msg = str(e)
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."

            self._stop_breathing_effect()
            self._set_status_styled(f"❌ Staking failed: {error_msg}", style="error", duration=6.0)

    async def _handle_unstake_action(self, stake_data: dict) -> None:
        """
        Handle unstaking operation with new flow:
        1. Request passphrase (decrypt key)
        2. Estimate gas and show confirmation screen
        3. Execute unstake operation
        """
        import traceback
        from sassy_wallet.core.tezos import unstake_xtz, key_from_encoded_secret
        from sassy_wallet.core.crypto import decrypt_secret

        account = stake_data.get("account")
        amount = stake_data.get("amount")

        if not account or amount is None:
            log_error("Invalid unstake data received", stake_data=stake_data)
            self._set_status("❌ Invalid unstake data")
            return


        # Step 1: Request passphrase and decrypt key
        passphrase = await self.push_screen_wait(
            StakePassphraseScreen(
                "🔐 Enter Your Passphrase",
                password=True,
                placeholder="Your wallet passphrase",
                wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                ok_label="Next →",
                fun_note="Keep your keys safe. Never share this passphrase. 🔐🥖",
                show_back_button=True
            )
        )

        if passphrase == "__BACK__":
            self.call_later(self.action_stake)
            return

        if not passphrase:
            self._set_status("⏸️ Unstaking cancelled")
            return

        try:
            _, can_send, _, can_stake = self._ensure_working_rpc_for_stake(account.address)
            if not can_send:
                self._set_status("[red]❌ No RPC available to inject operations[/red]")
                return
            if not can_stake:
                self._set_status("[red]❌ RPC/protocol does not support unstake operations[/red]")
                return

            # Decrypt key
            secret_key = decrypt_secret(account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            key_pkh = key.public_key_hash()

            if account.address != key_pkh:
                self._set_status("❌ KEY MISMATCH!")
                return

            # Step 2: Show confirmation screen with gas estimation
            confirm_result = await self.push_screen_wait(
                ConfirmUnstakeScreen(
                    rpc=self.rpc,
                    key=key,
                    address=account.address,
                    amount=amount,
                    show_back_button=True
                )
            )

            if not confirm_result or not confirm_result.get("ok"):
                if confirm_result and confirm_result.get("__BACK__"):
                    passphrase_retry = await self.push_screen_wait(
                        StakePassphraseScreen(
                            "🔐 Enter Your Passphrase",
                            password=True,
                            placeholder="Your wallet passphrase",
                            wallet_info=f"[b cyan]Wallet:[/b cyan] {account.name}",
                            ok_label="Next →",
                            fun_note="Keep your keys safe. Never share this passphrase. 🔐🥖",
                            show_back_button=True
                        )
                    )
                    if passphrase_retry == "__BACK__":
                        self.call_later(self.action_stake)
                        return
                    if not passphrase_retry:
                        self._set_status("⏸️ Unstaking cancelled")
                        return
                    passphrase = passphrase_retry
                    secret_key = decrypt_secret(account.enc, passphrase)
                    key = key_from_encoded_secret(secret_key)
                else:
                    self._set_status("↩️ Unstaking cancelled")
                    return

            # Extra confirmation to discourage impulsive unstaking
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

            # Step 3: Execute unstaking operation with confirmed parameters
            fee_mutez = confirm_result.get("fee_mutez")
            gas_limit = confirm_result.get("gas_limit")
            storage_limit = confirm_result.get("storage_limit")

            self._start_breathing_effect("⏳ Unstaking... This may take a moment...")

            op_hash = unstake_xtz(
                self.rpc,
                key,
                amount,
                fee_mutez=fee_mutez,
                gas_limit=gas_limit,
                storage_limit=storage_limit,
            )

            baker_addr = get_delegation_info(self.rpc, account.address)
            baker_label = self._format_baker_label(baker_addr)
            self._add_pending_tx(
                address=account.address,
                oph=op_hash,
                direction="UST",
                amount_xtz=amount,
                counterparty=baker_label,
                kind="transaction",
                entrypoint="unstake",
            )

            self._stop_breathing_effect()
            self._status_lock_until_refresh = True
            self._start_breathing_effect(
                f"⚰️ Unstaked {format_xtz(amount)} XTZ. The network feels a little less safe. 😔",
                bright_class="status-unstake",
                dim_class="status-unstake-dim",
            )
            self.call_later(self._refresh_account)

        except Exception as e:

            error_msg = str(e)
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."

            self._stop_breathing_effect()
            self._set_status_styled(f"❌ Unstaking failed: {error_msg}", style="error", duration=6.0)

    async def _handle_delegate_action(self, stake_data: dict) -> None:
        """Handle delegation operation with passphrase from app level."""
        import traceback
        from sassy_wallet.core.tezos import delegate_to_baker, key_from_encoded_secret
        from sassy_wallet.core.crypto import decrypt_secret

        account = stake_data.get("account")
        baker_address = stake_data.get("baker_address")
        baker_name = stake_data.get("baker_name", "Unknown Baker")
        fee_mutez = stake_data.get("fee_mutez")
        gas_limit = stake_data.get("gas_limit")
        storage_limit = stake_data.get("storage_limit")

        if not account or not baker_address:
            log_error("Invalid delegation data received", stake_data=stake_data)
            self._set_status("❌ Invalid delegation data")
            return


        # Request passphrase
        baker_display = baker_name if baker_name != "Unknown Baker" else f"{baker_address[:10]}...{baker_address[-8:]}"
        passphrase = await self.push_screen_wait(
            SendPassphraseScreen(
                "🔐 Enter Your Passphrase",
                password=True,
                placeholder="Your wallet passphrase",
                wallet_info=f"[b]{account.name}[/b]",
                ok_label="✅ Delegate!",
                fun_note="Delegate like a boss! Your XTZ will thank you! 🎯"
            )
        )

        if not passphrase:
            self._set_status("⏸️ Delegation cancelled")
            return

        try:
            _, can_send, _ = self._ensure_working_rpc()
            if not can_send:
                self._set_status("[red]❌ No RPC available to inject operations[/red]")
                return

            self._set_status_styled(
                "⏳ Delegating... This may take a moment...",
                style="warning",
                duration=0,
            )

            secret_key = decrypt_secret(account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            key_pkh = key.public_key_hash()
            if account.address != key_pkh:
                self._set_status("❌ KEY MISMATCH!")
                return

            op_hash = delegate_to_baker(
                self.rpc,
                key,
                baker_address,
                fee_mutez=fee_mutez,
                gas_limit=gas_limit,
                storage_limit=storage_limit,
            )

            self._add_pending_tx(
                address=account.address,
                oph=op_hash,
                direction="DEL",
                amount_xtz=Decimal(0),
                counterparty=baker_display,
                kind="delegation",
                entrypoint="delegation",
            )

            self._set_status_styled_locked(
                f"✅ Delegation sent to {baker_display}! 🎯",
                style="warning",
            )
            self.call_later(self._refresh_account)

        except Exception as e:

            error_msg = str(e)
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."

            self._set_status_styled(f"❌ Delegation failed: {error_msg}", style="error", duration=6.0)

    def action_show_address(self) -> None:
        """Show full address details in a modal."""
        if not self.selected:
            self._set_status("ℹ️ No account selected")
            return
        self.push_screen(AddressDetailScreen(self.selected.name, self.selected.address))

    @work(exclusive=True)
    async def action_backup(self) -> None:
        """Create a timestamped encrypted backup (single wallet or all)."""
        if not self.accounts:
            self._ui(self._set_status, "🥐 Back up the void? Import a wallet first. ¬_¬")
            return

        try:
            from datetime import datetime
            import json
            from sassy_wallet.core.crypto import encrypt_secret
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
                self._ui(self._set_status, "❌ Backup cancelled - Passphrase mismatch")
                return

            # Create backup directory
            backup_dir = Path(selection.get("backup_dir") or "data/backups").expanduser()
            if backup_dir.is_file():
                backup_dir = backup_dir.parent
            backup_dir.mkdir(parents=True, exist_ok=True)

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

            # Write backup file
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_content, f, indent=2, ensure_ascii=False)

            # Get file size for confirmation
            size_kb = backup_path.stat().st_size / 1024
            # Get absolute path for display
            abs_backup_path = backup_path.resolve()

            if selected_account:
                logging.info(f"Created backup for {selected_account.name}: {backup_path}")
                backup_msg = get_message("backup_success", name=selected_account.name)
            elif selected_accounts:
                logging.info(f"Created backup for {len(selected_accounts)} wallet(s): {backup_path}")
                backup_msg = f"✅ Backed up {len(selected_accounts)} wallet(s)"
            else:
                logging.info(f"Created backup for {len(self.accounts)} wallet(s): {backup_path}")
                backup_msg = f"✅ Backed up {len(self.accounts)} wallet(s)"
            self._ui(
                self._set_status_styled,
                f"{backup_msg} ({size_kb:.1f} KB) → {abs_backup_path}",
                "warning",
                5.0,
            )
            return

        except Exception as e:
            log_error("Backup failed", exception=e)
            self._ui(self._set_status_styled, f"❌ Backup failed: {e}", "error", 5.0)

    @work(exclusive=True)
    async def action_delete_wallet(self) -> None:
        """Delete a wallet after selection and confirmation."""
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

        except Exception as e:
            log_error("Failed to delete wallet", exception=e)
            self._set_status_styled(f"❌ Failed to delete wallet: {e}", style="error", duration=5.0)

    @work(exclusive=True)
    async def action_import_wallet(self) -> None:
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
            backup_dir.mkdir(parents=True, exist_ok=True)
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
            if backup_path_str == "__BACK__":
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

            # Read and parse backup file
            self._set_status("🔍 Reading the recipe from the pantry...")
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
            except json.JSONDecodeError as e:
                log_error("Invalid JSON in backup file", exception=e)
                self._set_status(f"❌ Invalid backup file format! Recipe got soggy! 💧")
                return False
            except Exception as e:
                log_error("Failed to read backup file", exception=e)
                self._set_status(f"❌ Failed to read backup: {e}")
                return False

            # Validate backup structure
            if not isinstance(backup_data, dict):
                self._set_status("❌ Invalid backup: Not a valid recipe book! 📖")
                return False

            if backup_data.get("encrypted"):
                from sassy_wallet.core.crypto import decrypt_secret, EncryptedBlob

                backup_type = backup_data.get("backup_type")
                passphrase = await self.push_screen_wait(
                    PromptScreen(
                        "🔐 Backup Passphrase",
                        placeholder="Enter backup passphrase",
                        password=True,
                        ok_label="Unlock →",
                        fun_note="Unlock the recipe book.",
                        show_back_button=True,
                    )
                )
                if passphrase == "__BACK__":
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
                    backup_data = json.loads(payload_json)
                    if backup_type and not backup_data.get("backup_type"):
                        backup_data["backup_type"] = backup_type
                except Exception as e:
                    log_error("Failed to decrypt backup file", exception=e)
                    self._set_status("❌ Failed to decrypt backup. Wrong passphrase?")
                    return False
            return await self._import_from_backup_payload(backup_data)

        except Exception as e:
            log_error("Backup import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    async def _import_with_secret_key(self) -> bool:
        """Import wallet with secret key (auto-derives address)."""
        try:
            resp = await self.push_screen_wait(ImportSecretScreen())
            if resp and resp.get("__BACK__"):
                return True
            if not resp:
                self._set_status(get_message("import_cancel"))
                return False
            await self._import_with_secret_key_data(
                resp.get("name", ""),
                resp.get("secret", ""),
                resp.get("passphrase", ""),
            )
            return False

        except Exception as e:
            log_error("Secret key import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    async def _import_watch_only(self) -> bool:
        """Import watch-only wallet (no secret key)."""
        try:
            resp = await self.push_screen_wait(ImportWatchScreen())
            if resp and resp.get("__BACK__"):
                return True
            if not resp:
                self._set_status(get_message("import_cancel"))
                return False
            await self._import_watch_only_data(resp.get("name", ""), resp.get("address", ""))
            return False

        except Exception as e:
            log_error("Watch-only import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    async def _import_with_secret_key_data(self, name: str, secret: str, pw: str) -> None:
        name = (name or "").strip()
        secret = (secret or "").strip()
        pw = pw or ""

        if not name:
            self._set_status("↩️ Import cancelled - Name required! 🏷️")
            return
        if not secret:
            self._set_status("↩️ Import cancelled - No secret key provided! 🌾")
            return
        if not pw:
            self._set_status("↩️ Import cancelled - Passphrase required! 🔐")
            return

        self._set_status("🔮 Deriving your address from the secret key...")
        try:
            key = key_from_encoded_secret(secret)
            addr = key.public_key_hash()
            self._set_status(f"✨ Address derived: {addr}")
        except Exception as e:
            log_error("Failed to derive address from secret key", exception=e)
            self._set_status(f"❌ Invalid secret key! Can't bake bread with bad flour! 😅 Error: {e}")
            return

        enc = encrypt_secret(secret, pw)
        upsert_account(self.store, Account(name=name, address=addr, enc=enc))
        save_store(self.store)
        self._render_accounts()

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
        name = (name or "").strip()
        mnemonic = (mnemonic or "").strip()
        bip39_pass = bip39_pass or ""
        pw = pw or ""
        derivation_path = (derivation_path or "").strip()

        if not name:
            self._set_status("↩️ Import cancelled - Name required! 🏷️")
            return
        if not mnemonic:
            self._set_status("↩️ Import cancelled - Mnemonic required! 🧠")
            return
        if not pw:
            self._set_status("↩️ Import cancelled - Passphrase required! 🔐")
            return

        try:
            from mnemonic import Mnemonic
        except Exception:
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
        except Exception as e:
            log_error("Failed to derive key from mnemonic", exception=e)
            self._set_status(f"❌ Failed to derive key from mnemonic: {e}")
            return

        enc = encrypt_secret(secret, pw)
        upsert_account(self.store, Account(name=name, address=addr, enc=enc))
        save_store(self.store)
        self._render_accounts()

        self._set_status_styled_locked(
            "✓ Mnemonic imported — oven preheated and ready! 🔥",
            style="info",
        )

    async def _import_watch_only_data(self, name: str, addr: str) -> None:
        name = (name or "").strip()
        addr = (addr or "").strip()

        if not name:
            self._set_status("↩️ Import cancelled - Name required! 🏷️")
            return
        if not addr:
            self._set_status("↩️ Import cancelled - Address required! 🥐")
            return

        if not is_tz_address(addr):
            self._set_status("❌ Invalid account address. Must be tz1/tz2/tz3/tz4")
            return

        upsert_account(self.store, Account(name=name, address=addr, enc=None))
        save_store(self.store)
        self._render_accounts()

        success_msg = get_message("import_watch", name=name)
        self._set_status_styled_locked(
            f"✓ {success_msg} Watch-only mode activated! 🥖",
            style="info",
        )

    async def _import_from_backup_payload(self, backup_data: dict) -> bool:
        """Import from already parsed (and decrypted) backup data."""
        try:
            if not isinstance(backup_data, dict) or not backup_data:
                self._set_status("❌ Invalid backup: Not a valid recipe book! 📖")
                return False
            from sassy_wallet.core.crypto import EncryptedBlob

            if backup_data.get("backup_type") in ("all_wallets_encrypted", "multi_wallets_encrypted"):
                accounts_data = backup_data.get("accounts", [])
                if not isinstance(accounts_data, list) or not accounts_data:
                    self._set_status("❌ Invalid backup: No accounts found.")
                    return False

                imported = 0
                skipped = 0
                for acc_data in accounts_data:
                    addr = acc_data.get("address")
                    if not addr or not is_tz_address(addr):
                        skipped += 1
                        continue
                    name = acc_data.get("name", "Imported Wallet")
                    enc = acc_data.get("enc")
                    if isinstance(enc, dict):
                        enc = EncryptedBlob(**enc)
                    upsert_account(self.store, Account(name=name, address=addr, enc=enc))
                    imported += 1

                recent_map = backup_data.get("recent_to_by_wallet", {})
                if isinstance(recent_map, dict):
                    self.recent_to_by_wallet.update(recent_map)

                save_store(self.store)
                self._render_accounts()

                self._set_status_styled_locked(
                    f"✅ Restored {imported} wallet(s). Skipped {skipped}.",
                    style="info",
                )
                logging.info(f"Imported {imported} wallet(s) from backup")
                return False

            if backup_data.get("backup_type") == "single_wallet_encrypted":
                wallet_data = backup_data.get("wallet")
                if not wallet_data:
                    self._set_status("❌ Invalid backup: No wallet data found in recipe! 🤷")
                    return False

                name = wallet_data.get("name", "Imported Wallet")
                addr = wallet_data.get("address")
                enc = wallet_data.get("enc")
                if isinstance(enc, dict):
                    enc = EncryptedBlob(**enc)

                if not addr:
                    self._set_status("❌ Invalid backup: Missing address in wallet data!")
                    return False

                if not is_tz_address(addr):
                    self._set_status(f"❌ Invalid address in backup: {addr}")
                    return False

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

                upsert_account(self.store, Account(name=name, address=addr, enc=enc))

                recent_dests = backup_data.get("recent_destinations", [])
                if recent_dests:
                    self.recent_to_by_wallet[addr] = recent_dests

                save_store(self.store)
                self._render_accounts()

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
                return False

            wallet_data = backup_data.get("wallet")
            if not wallet_data:
                self._set_status("❌ Invalid backup: No wallet data found in recipe! 🤷")
                return False

            name = wallet_data.get("name", "Imported Wallet")
            addr = wallet_data.get("address")
            enc = wallet_data.get("enc")
            if isinstance(enc, dict):
                enc = EncryptedBlob(**enc)

            if not addr:
                self._set_status("❌ Invalid backup: Missing address in wallet data!")
                return False

            if not is_tz_address(addr):
                self._set_status(f"❌ Invalid address in backup: {addr}")
                return False

            upsert_account(self.store, Account(name=name, address=addr, enc=enc))

            recent_dests = backup_data.get("recent_destinations", [])
            if recent_dests:
                self.recent_to_by_wallet[addr] = recent_dests

            save_store(self.store)
            self._render_accounts()

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
            return False
        except Exception as e:
            log_error("Backup import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)
            return False

    @work(exclusive=True)
    async def action_send(self) -> None:
        """Simplified send flow using unified SendScreen with back navigation."""
        if self._send_in_progress:
            self._set_status("⏳ Send operation already in progress…")
            return
        if not self.accounts:
            self._set_status("🥐 You can't send what you don't have—yet, son. Import a wallet first. ¬_¬")
            return
        if not self.selected:
            self._set_status("ℹ️ Select a wallet first.")
            return

        from_account = None
        to_addr = ""
        amount = None
        step = 1  # 1: SendScreen, 2: Passphrase, 3: Confirm

        while True:
            # Step 1: Get From/To/Amount in one screen
            if step == 1:
                wallet_recents = self._get_recent_to_for_wallet(self.selected.address) if self.selected else []
                send_data = await self.push_screen_wait(
                    SendScreen(self.accounts, self.rpc, wallet_recents)
                )

                if not send_data:
                    self._set_status("🚫 Send canceled — keeping my baguettes. 🥖")
                    return

                from_account = send_data["from_account"]
                to_addr = send_data["to_addr"]
                amount = send_data["amount"]
                step = 2  # Go to passphrase

            # Step 2: Get passphrase
            elif step == 2:
                pw = await self.push_screen_wait(
                    SendPassphraseScreen(
                        "🔐 Enter Your Passphrase",
                        password=True,
                        placeholder="Your wallet passphrase",
                        wallet_info=f"[b]{from_account.name}[/b]",
                        ok_label="Next →",
                        fun_note="The moment of truth! Like opening a safe, but cooler. 🔓✨",
                        show_back_button=True
                    )
                )

                if pw == "__BACK__":
                    step = 1  # Go back to SendScreen
                    continue

                if not pw:
                    self._set_status("🚫 Send canceled — keeping my baguettes. 🥖")
                    return

                try:
                    secret = decrypt_secret(from_account.enc, pw)
                    key = key_from_encoded_secret(secret)
                except Exception as e:
                    log_error("Failed to decrypt secret key", exception=e)
                    self._set_status(f"❌ Decrypt key failed: {e}")
                    continue  # Stay on step 2 to retry

                step = 3  # Go to confirmation

            # Step 3: Confirm and send (with gas estimation)
            elif step == 3:
                self._send_in_progress = True
                self._set_busy(True)

                resp = await self.push_screen_wait(
                    ConfirmSendScreen(self.rpc, key, from_account.address, to_addr, amount, show_back_button=True)
                )

                if resp and resp.get("__BACK__"):
                    step = 2  # Go back to passphrase
                    self._set_busy(False)
                    self._send_in_progress = False
                    continue

                if not resp or not resp.get("ok"):
                    self._set_status("🚫 Send canceled — keeping my baguettes. 🥖")
                    self._set_busy(False)
                    self._send_in_progress = False
                    return

                from_addr = from_account.address
                self._send_and_refresh(
                    from_addr,
                    key,
                    to_addr,
                    amount,
                    fee_mutez=resp.get("fee_mutez"),
                    gas_limit=resp.get("gas_limit"),
                    storage_limit=resp.get("storage_limit"),
                )
                return  # Done!

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
        self._ui(self._set_busy, True)
        self._ui(self._clear_tx_link)  # Clear any previous transaction link

        # Phase 1: Preparing
        self._ui(self._start_spinner, "🌾 Preparing the dough…")
        time.sleep(0.3)  # Brief pause for UX

        # Phase 2: Kneading
        self._ui(self._set_status, "👐 Kneading the dough… almost ready!")
        time.sleep(0.3)

        try:
            self._ensure_working_rpc()
            # Phase 3: Baker is processing - START BREATHING EFFECT
            self._ui(self._start_breathing_effect, "👨‍🍳 Baker is processing your pastries, sit tight… 🥖")

            oph = send_xtz(
                self.rpc,
                key,
                to_addr,
                amount,
                fee_mutez=fee_mutez,
                gas_limit=gas_limit,
                storage_limit=storage_limit,
            )
            logging.info(f"Transaction injected: {oph}")

            self._push_recent_to(from_addr, to_addr)

            tzkt = tzkt_ui_base_from_rpc(self.rpc)
            oph_short = f"{oph[:10]}...{oph[-8:]}" if len(oph) > 20 else oph
            tzkt_link = f"{tzkt}/{oph}"

            # Phase 4: Baker is still working - CONTINUE BREATHING EFFECT
            self._ui(self._start_breathing_effect, f"🔥 Baker working hard on your order! Almost there… 👨‍🍳")
            self._ui(self._show_tx_link, oph_short, tzkt_link)

            # Invalidate caches after successful send
            self._invalidate_history_cache(from_addr)
            self._invalidate_balance_cache(from_addr)

            # Poll history until the injected op shows up (indexers can lag).
            # Keep the spinner running until we either see the op hash in history
            # or we hit a short timeout.
            items: list[dict] = []
            found = False
            for _ in range(Config.HISTORY_POLL_MAX_ATTEMPTS):
                try:
                    items = get_xtz_history(self.rpc, from_addr, limit=self.history_limit)
                except Exception as e:
                    log_error("Failed to poll history for new transaction", exception=e)
                    items = []
                if any((it.get("hash") or "") == oph for it in (items or [])):
                    found = True
                    break
                time.sleep(Config.HISTORY_POLL_INTERVAL)

            if items:
                self.history_cache[(from_addr, self.history_limit)] = items
                self._ui(self._render_history, items)
                self._ui(self._update_status_balance)

            if found:
                # Phase 5: Almost ready (caramelizing)
                self._ui(self._set_status, f"🍯 Almost done… getting that perfect golden crust! ✨")
                time.sleep(0.4)

                baker = find_baker_for_operation(self.rpc, oph, max_depth=Config.BAKER_SEARCH_MAX_DEPTH)

                if items and baker:
                    # Attach baker to the matching history row
                    for it in items:
                        if (it.get('hash') or '') == oph:
                            it['baker'] = baker
                    self.history_cache[(from_addr, self.history_limit)] = items
                    self._ui(self._render_history, items)

                # Phase 6: Done! Show baker info prominently - STOP BREATHING AND GO GREEN
                self._ui(self._stop_breathing_effect)
                oph_short = f"{oph[:10]}...{oph[-8:]}" if len(oph) > 20 else oph
                baker_short = f"{baker[:10]}...{baker[-8:]}" if baker and len(baker) > 20 else baker

                if baker:
                    self._ui(self._set_status_styled_locked, f"✓ 🥐 Baked to perfection! | 👨‍🍳 Baker: {baker_short}", "success")
                else:
                    self._ui(self._set_status_styled_locked, f"✓ 🥐 Baked to perfection! ✨ | Hash: {oph_short}", "success")

                # Show transaction link
                tzkt_link = f"{tzkt}/{oph}"
                self._ui(self._show_tx_link, oph_short, tzkt_link)
            else:
                # Still injected, but not yet indexed; user can refresh later.
                self._ui(self._stop_breathing_effect)
                oph_short = f"{oph[:10]}...{oph[-8:]}" if len(oph) > 20 else oph
                self._ui(self._set_status, f"🕐 Baker still processing… check back soon! | Hash: {oph_short}")
                tzkt_link = f"{tzkt}/{oph}"
                self._ui(self._show_tx_link, oph_short, tzkt_link)

            def _focus_hist():
                try:
                    self.query_one("#history", ListView).focus()
                except Exception as e:
                    log_error("Failed to focus history after send", exception=e)

            self._ui(_focus_hist)

        except Exception as e:
            log_error("Transaction failed", exception=e)
            self._ui(self._stop_breathing_effect)  # Stop breathing on error
            self._ui(self._set_status, f"❌ Baking failed: {e}")
            self._ui(self._clear_tx_link)  # Clear link on error
        finally:
            self._ui(self._stop_spinner)
            self._ui(self._stop_breathing_effect)  # Always stop breathing effect
            self._ui(self._set_busy, False)
            self._ui(setattr, self, '_send_in_progress', False)

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


if __name__ == "__main__":
    setup_logging()
    try:
        WalletApp().run()
    except Exception as e:
        log_error("Application crashed", exception=e)
        logging.critical(f"Application crashed: {e}", exc_info=True)
        raise
