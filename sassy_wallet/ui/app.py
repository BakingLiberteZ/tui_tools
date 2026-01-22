from __future__ import annotations
from decimal import Decimal
import decimal
import re
import threading
from threading import RLock
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
from textual.widgets import Header, Footer, ListView, ListItem, Label, Button, Input, Static

from sassy_wallet.core.store import load_store, save_store, list_accounts, upsert_account, Account
from sassy_wallet.core.crypto import encrypt_secret, decrypt_secret
from sassy_wallet.core.tezos import (
    get_balance_mutez,
    mutez_to_xtz,
    key_from_encoded_secret,
    send_xtz,
    get_xtz_history,
    estimate_send_xtz,
    get_delegation_info,
    get_staking_balance,
    delegate_to_baker,
    stake_xtz,
    unstake_xtz,
)
from sassy_wallet.core.logger import log_exception, safe_log_exception, log_error, log_info, log_warning
from sassy_wallet.messages.bakery import get_message, SPINNER_MESSAGES, BAKER_MESSAGES, get_baker_message
from sassy_wallet.messages.staking import get_staking_message
from sassy_wallet.messages.empty_wallet import get_empty_wallet_message
from sassy_wallet.messages.balance import get_balance_message
from sassy_wallet.messages.modal import get_modal_message


# --- Configuration constants ---
class Config:
    """Application configuration constants."""
    # RPC URLs
    RPC_DEFAULT_MAINNET = "https://rpc.tzkt.io/mainnet"
    RPC_DEFAULT_GHOSTNET = "https://ghostnet.tezos.marigold.dev"

    RPC_MAINNET_CANDIDATES = [
        "https://mainnet.tezos.ecadinfra.com",
        "https://mainnet.smartpy.io",
        "https://mainnet.api.tez.ie",
        # Fallbacks (may be read-only / throttled / flaky depending on policy/region):
        "https://rpc.tzkt.io/mainnet",
        "https://rpc.tzbeta.net",
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
    HISTORY_DEFAULT_LIMIT = 20
    HISTORY_INCREMENT = 20
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

    # File handler with rotation
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(Config.LOG_LEVEL)

    # Console handler (only errors)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

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

_OK_CODES = {200, 405, 415}

# Candidates ordered by preference. We will probe them at runtime and pick the first
# one that supports BOTH simulation (run_operation) and injection.
# Use Config constants instead of module-level variables
_MAINNET_RPC_CANDIDATES = Config.RPC_MAINNET_CANDIDATES
_GHOSTNET_RPC_CANDIDATES = Config.RPC_GHOSTNET_CANDIDATES


def _http_code(url: str, timeout_s: float = Config.RPC_TIMEOUT) -> int:
    """Return HTTP status code for a simple GET, or 0 on network error."""
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
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
    return _http_code(f"{rpc.rstrip('/')}/injection/operation") in _OK_CODES


def rpc_supports_simulation(rpc: str) -> bool:
    return (
        _http_code(
            f"{rpc.rstrip('/')}/chains/main/blocks/head/helpers/scripts/run_operation"
        )
        in _OK_CODES
    )


def choose_working_rpc(current_rpc: str) -> tuple[str, bool, bool]:
    """Pick the first RPC that supports injection and (ideally) simulation.

    Returns (rpc, supports_send, supports_simulation).
    """
    net = network_from_rpc(current_rpc)
    candidates = _MAINNET_RPC_CANDIDATES if net == "mainnet" else _GHOSTNET_RPC_CANDIDATES

    # Prefer the current RPC first, then fall back.
    ordered = [current_rpc] + [c for c in candidates if c != current_rpc]

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
        min-width: 65;
        max-width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: heavy #ef4444;
        padding: 1 2;
    }

    ConfirmScreen Static {
        margin-bottom: 0;
    }

    ConfirmScreen Horizontal {
        align: center middle;
    }

    ConfirmScreen Horizontal > Button {
        margin: 0 1;
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
        self.query_one("#no", Button).focus()

    @on(Button.Pressed, "#yes")
    def yes_pressed(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def no_pressed(self) -> None:
        self.dismiss(False)

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss(False)


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

    PromptScreen #wallet_info {
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
        padding: 1;
        background: $panel;
        border: solid #374151;
    }

    PromptScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-bottom: 0;
        padding: 0 1;
        background: $panel;
    }

    PromptScreen #inp {
        margin-bottom: 0;
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
        fun_note: str = ""
    ):
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._password = password
        self._wallet_info = wallet_info
        self._ok_label = ok_label
        self._fun_note = fun_note

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]{self._title}[/b]", markup=True)
            if self._wallet_info:
                yield Static(f"[dim]{self._wallet_info}[/dim]", id="wallet_info", markup=True)
            if self._fun_note:
                yield Static(f"💡 {self._fun_note}", id="fun_note", markup=True)
            yield Input(placeholder=self._placeholder, password=self._password, id="inp")
            with Horizontal():
                yield Button(self._ok_label, id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#inp", Input).focus()

    @on(Input.Submitted)
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            value = self.query_one("#inp", Input).value
            self.dismiss(value)
        else:
            self.dismiss("")


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

    SendAmountScreen Horizontal {
        align: center middle;
    }
    """


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
        if event.list_view.id != "networks":
            return
        self.dismiss(self._selected_key())

    @on(Button.Pressed, "#select")
    def select_pressed(self) -> None:
        self.dismiss(self._selected_key())

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.dismiss("")

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss("")


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
            self.app._set_status(f"✅ Address copied: {self.address[:10]}...")  # type: ignore[attr-defined]
            self.dismiss(None)
        except Exception as e:
            log_warning("Clipboard copy failed", exception=e, address=self.address[:10])
            self.app._set_status(f"❌ Copy failed. Address: {self.address}")  # type: ignore[attr-defined]

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss(None)


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
        if getattr(event, "key", None) == "escape":
            self.dismiss(None)


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
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    ReceiveScreen #address_box {
        margin-bottom: 1;
        padding: 1;
        background: $boost;
        border: solid #10b981;
        text-align: center;
    }

    ReceiveScreen #status_msg {
        margin-bottom: 1;
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

    def __init__(self, address: str):
        super().__init__()
        self.address = address
        self._status_timer = None
        import random
        self._fun_message = random.choice(self.RECEIVE_MESSAGES)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[b]💸 Receive XTZ[/b]\nCopy this address to receive funds", id="title", markup=True)
            yield Static(
                f"[b]{self.address}[/b]\n[dim]👆 Share this address to receive XTZ[/dim]",
                id="address_box",
                markup=True
            )
            yield Static("", id="status_msg", markup=True)
            yield Static(self._fun_message, id="fun_note", markup=True)
            with Horizontal():
                yield Button("Copy", id="copy", variant="primary")
                yield Button("Done", id="close")

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss(None)
        if getattr(event, "key", None) == "enter":
            self._copy_to_clipboard()

    def _copy_to_clipboard(self) -> None:
        """Copy address to clipboard and show visual feedback."""
        try:
            self.app.copy_to_clipboard(self.address)  # type: ignore[attr-defined]
            # Show success message in the modal
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update("[green]✅ Address copied to clipboard![/green]")

            # Also update main status
            self.app._set_status("✅ Address copied to clipboard.")  # type: ignore[attr-defined]

            # Auto-close after showing success message
            if self._status_timer is not None:
                self._status_timer.stop()
            self._status_timer = self.set_timer(1.5, self._delayed_close)

        except Exception as e:
            log_warning("Clipboard copy failed in ReceiveScreen", exception=e)
            # Show error in modal with fallback instructions
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update(
                f"[yellow]⚠️ Clipboard unavailable[/yellow]\n"
                f"[dim]Copy manually from below:[/dim]"
            )

            # Update the main text to show the full address prominently
            recv_text = self.query_one("#recv_text", Static)
            recv_text.update(
                "[b]Receive Funds[/b]\n\n"
                "[yellow]⚠️ Clipboard unavailable - Copy address manually:[/yellow]\n"
                f"[b reverse]{self.address}[/b reverse]\n\n"
                "[dim]Select and copy the address above[/dim]"
            )

            # Update main status
            self.app._set_status(f"⚠️ Clipboard unavailable. Address shown in modal.")  # type: ignore[attr-defined]

            # Don't auto-close when clipboard fails - let user copy manually
            if self._status_timer is not None:
                self._status_timer.stop()
                self._status_timer = None

    def _delayed_close(self) -> None:
        """Close modal after delay."""
        self.dismiss(None)

    @on(Button.Pressed, "#copy")
    def copy_pressed(self) -> None:
        self._copy_to_clipboard()

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def on_unmount(self) -> None:
        """Cleanup timer on screen close."""
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer = None


class StakeScreen(ModalScreen[None]):
    """Modal for Delegation and Staking operations."""

    CSS = """
    StakeScreen {
        align: center middle;
    }

    StakeScreen > Vertical {
        width: auto;
        min-width: 70;
        max-width: 90;
        height: auto;
        max-height: 40;
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

    StakeScreen #info_box {
        margin-bottom: 1;
        padding: 1;
        background: $panel;
        border: solid #374151;
        display: none;
    }

    StakeScreen #fun_note {
        color: #fbbf24;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 1;
        padding: 0 1;
        background: $panel;
    }

    StakeScreen #input_container {
        margin-bottom: 1;
        display: none;
    }

    StakeScreen #input_label {
        margin-bottom: 1;
        color: $accent;
    }

    StakeScreen Input {
        margin-bottom: 1;
        border: heavy $primary;
        background: $boost;
        height: 3;
        padding: 1 2;
    }

    StakeScreen Input:focus {
        border: heavy #10b981;
        background: $surface;
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

    def __init__(self, accounts: list["Account"], rpc: str):
        super().__init__()
        # Filter only accounts with secret keys (not watch-only)
        self.accounts = [acc for acc in accounts if acc.enc is not None]
        self.rpc = rpc
        self.selected_account: Optional["Account"] = None
        self.balance_xtz: Decimal = Decimal(0)
        self.delegate_addr: Optional[str] = None
        self.staked_mutez: int = 0
        self.is_delegated: bool = False
        self._fun_message: str = get_modal_message("wallet_selector_stake")
        self._delegation_pending: bool = False
        self._polling_timer = None
        # Cache wallet info to avoid re-fetching when selecting
        self._wallet_info_cache: dict[str, dict] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]⚡💎 Stake/Unstake Manager[/b]\nSelect wallet and manage your stake", id="title", markup=True)

            # Wallet selector
            yield Static("[b]Choose Wallet:[/b]", id="wallet_selector_label", markup=True)
            yield ListView(id="wallet_selector")

            # Info box (hidden initially, shown after wallet selection)
            yield Static("", id="info_box", markup=True)

            # Input container (hidden initially)
            with Vertical(id="input_container"):
                yield Static("", id="input_label", markup=True)
                yield Input(placeholder="", id="input_field")
                yield Static("", id="input_hint", markup=True)

            yield Static("", id="status_msg", markup=True)
            yield Static(self._fun_message, id="fun_note", markup=True)

            # Buttons
            with Horizontal(id="button_container"):
                yield Button("Select", id="select_wallet_btn", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        """Populate wallet selector with delegation/staking status."""
        lv = self.query_one("#wallet_selector", ListView)
        lv.clear()

        if not self.accounts:
            label_text = "[dim]No wallets with secret keys available[/dim]"
            lv.append(ListItem(Label(label_text, markup=True)))
        else:
            for acc in self.accounts:
                addr_short = acc.address[:10] + "…" + acc.address[-8:]

                # Fetch delegation and staking status
                try:
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

                lv.append(ListItem(Label(label_text, markup=True)))

            lv.index = 0

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss(None)
        # Remove auto-advance on Enter - user must click Select button

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

            # Update fun message based on state
            if self.staked_mutez > 0:
                self._fun_message = get_modal_message("already_staking")
            elif self.is_delegated:
                self._fun_message = get_modal_message("stake")
            else:
                self._fun_message = get_modal_message("delegate")

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
        self._fun_message = get_modal_message("wallet_selector_stake")

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

        # Update fun note
        try:
            self.query_one("#fun_note", Static).update(self._fun_message)
        except Exception as e:
            log_error("Failed to update fun note", exception=e)

        # Reset buttons to just Cancel
        def reset_buttons():
            try:
                button_container = self.query_one("#button_container", Horizontal)
                # Remove all action buttons (keep only Cancel)
                for bid in ["delegate_btn", "stake_btn", "unstake_btn", "back_btn"]:
                    try:
                        btn = self.query_one(f"#{bid}", Button)
                        btn.remove()
                    except Exception:
                        pass
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
                self.query_one("#select_wallet_btn", Button).display = False
            except Exception as e:
                log_error("Failed to hide wallet selector", exception=e)

            # Show input container
            try:
                self.query_one("#input_container", Vertical).display = True
            except Exception as e:
                log_error("Failed to show input container", exception=e)

            # Update info box
            staked_xtz = format_xtz(mutez_to_xtz(self.staked_mutez))
            info_widget = self.query_one("#info_box", Static)

            if self.is_delegated:
                delegate_short = self.delegate_addr[:10] + "..." if self.delegate_addr else "None"
                info_text = (
                    f"[b]Wallet:[/b]          {self.selected_account.name}\n"
                    f"[b]Balance:[/b]         [cyan]{format_xtz(self.balance_xtz)} XTZ[/cyan]\n"
                    f"[b]Delegated to:[/b]    [yellow]{delegate_short}[/yellow]\n"
                    f"[b]Staked:[/b]          [#8b5cf6]{staked_xtz} XTZ[/#8b5cf6]"
                )
            else:
                info_text = (
                    f"[b]Wallet:[/b]          {self.selected_account.name}\n"
                    f"[b]Balance:[/b]         [cyan]{format_xtz(self.balance_xtz)} XTZ[/cyan]\n"
                    f"[b]Status:[/b]          [yellow]⚠️ Not delegated[/yellow]"
                )

            info_widget.update(info_text)
            info_widget.display = True

            # Update input container
            input_label = self.query_one("#input_label", Static)
            input_field = self.query_one("#input_field", Input)
            input_hint = self.query_one("#input_hint", Static)

            # Always clear the input field when updating view
            input_field.value = ""

            if not self.is_delegated and not self._delegation_pending:
                # Not delegated - show baker input and educational message
                input_label.update("[b][yellow]👇 Enter Baker Address Below:[/yellow][/b]\n[dim](Must start with tz1, tz2, tz3, or tz4)[/dim]")
                input_field.placeholder = "tz1... or tz2... or tz3... or tz4..."
                # Explicitly enable and make visible
                input_field.disabled = False
                input_field.display = True
                input_hint.update(
                    "[yellow]📚 To stake, you must delegate first! (You're on the right path!)[/yellow]\n"
                    "[dim]💡 Find bakers at baking-bad.org or tzkt.io[/dim]"
                )
                # Update fun message to delegate_required
                self._fun_message = get_modal_message("delegate_required")
                log_error(f"Input configured for delegation. Disabled={input_field.disabled}")
            elif self._delegation_pending:
                # Delegation pending - show waiting message
                input_label.update("[b]⏳ Waiting for delegation confirmation...[/b]")
                input_field.placeholder = "Please wait..."
                input_field.disabled = True
                input_hint.update("[yellow]The blockchain is processing your delegation. This may take 30-60 seconds.[/yellow]")
                # Update fun message to delegation_confirming
                self._fun_message = get_modal_message("delegation_confirming")
            else:
                # Delegated - show amount input
                input_label.update("[b][#8b5cf6]👇 Enter Amount to Stake/Unstake:[/#8b5cf6][/b]\n[dim](in XTZ)[/dim]")
                input_field.placeholder = "0.00 (Example: 10.5 or 25.75)"
                # Explicitly enable and make visible
                input_field.disabled = False
                input_field.display = True
                input_hint.update(f"[dim]💡 Available: {format_xtz(self.balance_xtz)} XTZ | Staked: {staked_xtz} XTZ[/dim]")
                log_error(f"Input configured for staking. Disabled={input_field.disabled}")

            # Update fun note
            fun_note = self.query_one("#fun_note", Static)
            fun_note.update(self._fun_message)

            # Update buttons - use call_later to avoid timing issues
            def update_buttons():
                try:
                    button_container = self.query_one("#button_container", Horizontal)

                    # Remove action buttons (including Back button)
                    for bid in ["delegate_btn", "stake_btn", "unstake_btn", "back_btn"]:
                        try:
                            btn = self.query_one(f"#{bid}", Button)
                            btn.remove()
                        except Exception:
                            pass  # Button doesn't exist, that's fine

                    # Get the Cancel button index
                    cancel_btn = None
                    cancel_index = 0
                    for i, child in enumerate(button_container.children):
                        if child.id == "cancel":
                            cancel_btn = child
                            cancel_index = i
                            break

                    # Always add Back button first (before action buttons)
                    button_container.mount(Button("◀ Change Wallet", id="back_btn", variant="default"), before=cancel_index)

                    # Add new action buttons before Cancel based on state
                    if not self.is_delegated and not self._delegation_pending:
                        # Not delegated - show Delegate button and disabled Stake button
                        button_container.mount(Button("Delegate", id="delegate_btn", variant="primary"), before=cancel_index + 1)
                        stake_btn = Button("Stake (Delegate first)", id="stake_btn", variant="default")
                        stake_btn.disabled = True
                        button_container.mount(stake_btn, before=cancel_index + 2)
                    elif self._delegation_pending:
                        # Delegation pending - disable Delegate button, keep Stake disabled
                        delegate_btn = Button("Delegating...", id="delegate_btn", variant="default")
                        delegate_btn.disabled = True
                        button_container.mount(delegate_btn, before=cancel_index + 1)
                        stake_btn = Button("Stake (waiting...)", id="stake_btn", variant="default")
                        stake_btn.disabled = True
                        button_container.mount(stake_btn, before=cancel_index + 2)
                    elif self.staked_mutez > 0:
                        # Already staking - show Stake and Unstake
                        button_container.mount(Button("Stake", id="stake_btn", variant="primary"), before=cancel_index + 1)
                        button_container.mount(Button("Unstake", id="unstake_btn", variant="warning"), before=cancel_index + 2)
                    else:
                        # Delegated but not staking - show enabled Stake button
                        button_container.mount(Button("Stake", id="stake_btn", variant="primary"), before=cancel_index + 1)
                except Exception as e:
                    log_error("Failed to update buttons", exception=e)

            self.call_later(update_buttons)

            # Focus on input field - use a slightly longer delay to ensure everything is ready
            def focus_input():
                try:
                    input_field = self.query_one("#input_field", Input)
                    # Make absolutely sure it's enabled and visible
                    input_field.disabled = False
                    input_field.display = True
                    input_field.focus()
                    log_error(f"Input field focused. Disabled={input_field.disabled}, Value='{input_field.value}'")
                except Exception as e:
                    log_error("Failed to focus input", exception=e)

            # Use set_timer instead of call_later for a small delay
            self.set_timer(0.1, focus_input)

        except Exception as e:
            log_error("Failed to update view", exception=e)
            status_widget = self.query_one("#status_msg", Static)
            status_widget.update(f"[red]❌ Error updating view: {str(e)}[/red]")

    @work(exclusive=True)
    @on(Button.Pressed, "#delegate_btn")
    async def delegate_pressed(self) -> None:
        """Handle delegation action."""
        input_field = self.query_one("#input_field", Input)
        value = input_field.value.strip()

        if not value:
            self._show_error("⚠️ Please enter baker address")
            return

        if not value.startswith(("tz1", "tz2", "tz3", "tz4")):
            self._show_error("⚠️ Invalid baker address format")
            return

        # Check for pending transactions before attempting delegation
        from wallet.tezos import check_pending_operations
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

        await self._perform_delegation(value)

    @work(exclusive=True)
    @on(Button.Pressed, "#stake_btn")
    async def stake_pressed(self) -> None:
        """Handle staking action."""
        input_field = self.query_one("#input_field", Input)
        value = input_field.value.strip()

        if not value:
            self._show_error("⚠️ Please enter amount")
            return

        try:
            amount = Decimal(value)
            if amount <= 0:
                self._show_error("⚠️ Amount must be positive")
                return
            if amount > self.balance_xtz:
                self._show_error("⚠️ Insufficient balance")
                return

            # Check for pending transactions
            from wallet.tezos import check_pending_operations
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

            await self._perform_staking(amount)
        except (ValueError, decimal.InvalidOperation):
            self._show_error("⚠️ Invalid amount format")

    @work(exclusive=True)
    @on(Button.Pressed, "#unstake_btn")
    async def unstake_pressed(self) -> None:
        """Handle unstaking action."""
        input_field = self.query_one("#input_field", Input)
        value = input_field.value.strip()

        if not value:
            self._show_error("⚠️ Please enter amount to unstake")
            return

        try:
            amount = Decimal(value)
            if amount <= 0:
                self._show_error("⚠️ Amount must be positive")
                return

            staked_xtz = mutez_to_xtz(self.staked_mutez)
            if amount > staked_xtz:
                self._show_error(f"⚠️ Cannot unstake more than staked ({format_xtz(staked_xtz)} XTZ)")
                return

            # Check for pending transactions
            from wallet.tezos import check_pending_operations
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

            await self._perform_unstaking(amount)
        except (ValueError, decimal.InvalidOperation):
            self._show_error("⚠️ Invalid amount format")

    async def _perform_delegation(self, baker_address: str) -> None:
        """Delegate to baker."""
        if not self.selected_account:
            return

        status_widget = self.query_one("#status_msg", Static)
        status_widget.update("[yellow]⏳ Delegating... This may take a moment...[/yellow]")

        # Get passphrase
        wallet_display = f"🔑 Wallet: {self.selected_account.name}"
        addr_short = self.selected_account.address[:10] + "..." + self.selected_account.address[-8:]
        passphrase = await self.app.push_screen_wait(  # type: ignore[attr-defined]
            PromptScreen(
                "Enter Passphrase",
                placeholder="Enter your passphrase",
                password=True,
                wallet_info=f"{wallet_display}\n[dim]Address: {addr_short}[/dim]\n[yellow]⚠️ Confirm delegation operation[/yellow]",
                fun_note=get_modal_message("send_passphrase"),
            )
        )

        if not passphrase:
            status_widget.update("[yellow]❌ Delegation cancelled[/yellow]")
            return

        try:
            # Decrypt key
            secret_key = decrypt_secret(self.selected_account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            # Perform delegation
            op_hash = delegate_to_baker(self.rpc, key, baker_address)

            status_widget.update(f"[green]✅ Delegation sent![/green]\n[dim]Op: {op_hash[:16]}... Waiting for confirmation...[/dim]")

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

    async def _perform_staking(self, amount: Decimal) -> None:
        """Stake XTZ."""
        if not self.selected_account:
            return

        status_widget = self.query_one("#status_msg", Static)
        status_widget.update("[yellow]⏳ Staking... This may take a moment...[/yellow]")

        # Get passphrase
        wallet_display = f"🔑 Wallet: {self.selected_account.name}"
        addr_short = self.selected_account.address[:10] + "..." + self.selected_account.address[-8:]
        passphrase = await self.app.push_screen_wait(  # type: ignore[attr-defined]
            PromptScreen(
                "Enter Passphrase",
                placeholder="Enter your passphrase",
                password=True,
                wallet_info=f"{wallet_display}\n[dim]Address: {addr_short}[/dim]\n[green]💎 Confirm staking {format_xtz(amount)} XTZ[/green]",
                fun_note=get_modal_message("send_passphrase"),
            )
        )

        if not passphrase:
            status_widget.update("[yellow]❌ Staking cancelled[/yellow]")
            return

        try:
            # Decrypt key
            secret_key = decrypt_secret(self.selected_account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            # Close modal immediately - show processing in main app
            self.dismiss(None)

            # Show processing status in main app
            self.app._set_status(f"⏳ Staking {format_xtz(amount)} XTZ... Processing transaction...")  # type: ignore[attr-defined]

            # Perform staking
            op_hash = stake_xtz(self.rpc, key, amount)

            # Show CHAD success message
            self.app._set_status(  # type: ignore[attr-defined]
                f"[green]✅ STAKE SUCCESSFUL! You're a true CHAD now! 🔥💪[/green]\n"
                f"[dim]Operation: {op_hash[:16]}...[/dim]"
            )

            # Trigger refresh to update display
            self.app.call_later(self.app._refresh_account)  # type: ignore[attr-defined]

        except Exception as e:
            log_error("Staking failed", exception=e)
            # Show error in main app since modal is closed
            self.app._set_status(f"[red]❌ Staking failed: {str(e)}[/red]")  # type: ignore[attr-defined]

    async def _perform_unstaking(self, amount: Decimal) -> None:
        """Unstake XTZ."""
        if not self.selected_account:
            return

        status_widget = self.query_one("#status_msg", Static)
        status_widget.update("[yellow]⏳ Unstaking... This may take a moment...[/yellow]")

        # Get passphrase
        wallet_display = f"🔑 Wallet: {self.selected_account.name}"
        addr_short = self.selected_account.address[:10] + "..." + self.selected_account.address[-8:]
        passphrase = await self.app.push_screen_wait(  # type: ignore[attr-defined]
            PromptScreen(
                "Enter Passphrase",
                placeholder="Enter your passphrase",
                password=True,
                wallet_info=f"{wallet_display}\n[dim]Address: {addr_short}[/dim]\n[cyan]💰 Confirm unstaking {format_xtz(amount)} XTZ[/cyan]",
                fun_note=get_modal_message("send_passphrase"),
            )
        )

        if not passphrase:
            status_widget.update("[yellow]❌ Unstaking cancelled[/yellow]")
            return

        try:
            # Decrypt key
            secret_key = decrypt_secret(self.selected_account.enc, passphrase)
            key = key_from_encoded_secret(secret_key)

            # Close modal immediately - show processing in main app
            self.dismiss(None)

            # Show processing status in main app
            self.app._set_status(f"⏳ Unstaking {format_xtz(amount)} XTZ... Processing transaction...")  # type: ignore[attr-defined]

            # Perform unstaking
            op_hash = unstake_xtz(self.rpc, key, amount)

            # Show success message
            self.app._set_status(  # type: ignore[attr-defined]
                f"[green]✅ UNSTAKE SUCCESSFUL! XTZ unlocked! 💰[/green]\n"
                f"[dim]Operation: {op_hash[:16]}...[/dim]"
            )

            # Trigger refresh to update display
            self.app.call_later(self.app._refresh_account)  # type: ignore[attr-defined]

        except Exception as e:
            log_error("Unstaking failed", exception=e)
            # Show error in main app since modal is closed
            self.app._set_status(f"[red]❌ Unstaking failed: {str(e)}[/red]")  # type: ignore[attr-defined]

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
                        f"[green]🎉 DELEGATION CONFIRMED! Staking unlocked! 💪[/green]\n"
                        f"[dim]You can now stake your XTZ![/dim]"
                    )

                    # Show success in main app
                    self.app._set_status("[green]✅ Delegation confirmed! You can now stake your XTZ! 💪[/green]")  # type: ignore[attr-defined]

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
        background: $surface;
        border: heavy $primary;
        padding: 2;
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
                amt_label = f"[green]+{format_xtz(amt)} XTZ[/green]"
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
        min-width: 75;
        max-width: 90;
        height: auto;
        background: $surface;
        border: heavy #10b981;
        padding: 2;
    }

    ConfirmSendScreen #summary {
        margin-bottom: 1;
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

    ConfirmSendScreen #advanced {
        margin-top: 0;
        margin-bottom: 1;
    }

    ConfirmSendScreen Horizontal {
        align: center middle;
    }

    ConfirmSendScreen Horizontal > Button {
        margin: 0 1;
    }
    """

    def __init__(self, rpc: str, key, from_addr: str, to_addr: str, amount: Decimal):
        super().__init__()
        self.rpc = rpc
        self.key = key
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount

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

            # Advanced container (oculto por defecto)
            with Vertical(id="advanced"):
                yield Static("[b]Advanced (TX overrides)[/b]\nLeave blank to use suggested/autofill.", markup=True)
                with Horizontal():
                    yield Static("Fee (XTZ):", id="lbl_fee")
                    yield Input(placeholder="e.g. 0.0012", id="fee_xtz")
                with Horizontal():
                    yield Static("Gas limit:", id="lbl_gas")
                    yield Input(placeholder="e.g. 2000", id="gas_limit")
                with Horizontal():
                    yield Static("Storage limit:", id="lbl_storage")
                    yield Input(placeholder="e.g. 0", id="storage_limit")

            with Horizontal():
                yield Button("SEND", id="send", variant="primary")
                yield Button("Advanced", id="toggle")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        adv = self.query_one("#advanced", Vertical)
        adv.styles.display = "none"

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

            # Minimal summary by default; advanced details shown only when Advanced is open.
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

            if self._advanced:
                lines += [
                    f"[b cyan]Reveal:[/b cyan]    {'yes (first send)' if reveal_needed else 'no'}",
                    "",
                    f"[dim]Suggested limits:[/dim] gas={gas}, storage={storage}",
                    "[dim]Tip:[/dim] use Economy/Normal/Priority, Advanced only if you know what you're doing.",
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
        adv.styles.display = "block" if self._advanced else "none"
        self.query_one("#toggle", Button).label = "Basic" if self._advanced else "Advanced"
        if self._advanced:
            self.query_one("#fee_xtz", Input).focus()
        else:
            # volver al fee list para flechas
            try:
                self.query_one("#fee_list", ListView).focus()
            except Exception as e:
                log_error("Failed to focus fee list", exception=e)
                self.query_one("#send", Button).focus()

    def _parse_overrides(self) -> tuple[Optional[int], Optional[int], Optional[int]]:
        fee_xtz_s = (self.query_one("#fee_xtz", Input).value or "").strip()
        gas_s = (self.query_one("#gas_limit", Input).value or "").strip()
        storage_s = (self.query_one("#storage_limit", Input).value or "").strip()

        fee_mutez = None
        gas = None
        storage = None

        if fee_xtz_s:
            fee_xtz = Decimal(fee_xtz_s)
            if fee_xtz < 0:
                raise ValueError("fee must be >= 0")
            fee_mutez = _xtz_to_mutez(fee_xtz)

        if gas_s:
            gas = int(gas_s)
            if gas < 0:
                raise ValueError("gas must be >= 0")

        if storage_s:
            storage = int(storage_s)
            if storage < 0:
                raise ValueError("storage must be >= 0")

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
            return

        # Si estás en inputs o listas, no interferimos (flechas/enter los maneja el widget)
        if isinstance(self.app.focused, (Input, ListView)):
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


class DestinationPickerScreen(ModalScreen[str]):
    """Input + lista de últimos destinos + wallets cargadas (click/enter). Flechas funcionan si lista tiene foco."""

    CSS = """
    DestinationPickerScreen {
        align: center middle;
    }

    DestinationPickerScreen > Vertical {
        width: auto;
        min-width: 75;
        max-width: 90;
        height: auto;
        background: $surface;
        border: heavy #10b981;
        padding: 2;
    }

    DestinationPickerScreen Static {
        margin-bottom: 0;
    }

    #dest_inp {
        margin-bottom: 1;
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

            # Your wallets section
            if self.accounts:
                yield Static("Your wallets:", id="wallets_title", markup=True)
                yield ListView(id="wallets_list")

            # Recent destinations section
            yield Static("Recent destinations:", id="recent_title", markup=True)
            yield ListView(id="recent_list")

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

        if key == "escape":
            self.dismiss("")
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

    Button {
        background: #3b82f6;
        color: white;
        height: 3;
        min-height: 3;
        padding: 0 2;
    }

    Button:hover {
        background: #2563eb;
        color: white;
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
        padding-left: 4;
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
        Binding("i", "import_wallet", "Import", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("s", "send", "Send", show=True),
        Binding("x", "receive", "Receive", show=True),
        Binding("k", "stake", "Stake", show=True),
        Binding("n", "network", "Network", show=True),
        Binding("b", "backup", "Backup", show=True),
        Binding("delete", "delete_wallet", "Delete", show=True),
        Binding("q", "quit", "Quit", show=True),
        # Hidden bindings (still work, just not shown in footer)
        Binding("d", "tx_details", "Tx details", show=False),
        Binding("enter", "tx_details", "Tx details", show=False),
        Binding("m", "more_history", "More history", show=False),
        Binding("up", "nav_up", "Up", show=False),
        Binding("down", "nav_down", "Down", show=False),
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
                yield Button("Stake (k)", id="stake")
                yield Button("Refresh (r)", id="refresh")

            # Recent Transactions section with split view
            yield Static(f"[b]Recent Transactions[/b] (last {self.history_limit}, press m for more)", id="hist_title", markup=True)
            # Column headers for both panels with fixed widths matching content
            with Horizontal(id="history_headers"):
                # Fixed widths: Time=14, DIR=3, Amount=15, Destination=20
                # Arrow symbol ↕ centered in 3-char field to match "IN "/"OUT"
                header_line = f"{'Time':<14}  {'↕':^3}  {'Amount':<15}  ↔  {'Destination':<20}"
                yield Static(header_line, id="history_header", markup=True)
                yield Static("[b]Extra Details[/b]", id="tx_detail_header", markup=True)
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
    def _set_status(self, text: str) -> None:
        """Update status message (for general messages).

        Args:
            text: Status message to display (stays visible until next action)
        """
        self._last_status = text
        # Status messages shown in status_line
        try:
            self.query_one("#status_line", Static).update(text)
        except Exception as e:
            log_error("Failed to update status line", exception=e)

    def _set_status_styled(self, text: str, style: str = "default", duration: float = 4.0) -> None:
        """Update status message with visual styling (success/warning/error/info).

        Args:
            text: Status message to display
            style: One of "success", "warning", "error", "info", or "default"
            duration: How long to show the styled state (seconds) before reverting to default
        """
        self._last_status = text

        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            # Update text
            status_widget.update(text)

            # Remove all status classes first
            for cls in ["status-success", "status-warning", "status-error", "status-info", "status-processing", "status-processing-dim"]:
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
        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            for cls in ["status-success", "status-warning", "status-error", "status-info", "status-processing", "status-processing-dim"]:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

        except Exception as e:
            log_error("Failed to revert status style", exception=e)

    def _start_breathing_effect(self, text: str) -> None:
        """Start breathing glow effect for processing state.

        Args:
            text: Status message to display with breathing effect
        """
        self._breathing_active = True
        self._breathing_bright = True
        self._last_status = text

        try:
            status_widget = self.query_one("#status_line", Static)
            bottom_bar = self.query_one("#bottom_bar", Horizontal)

            # Update text
            status_widget.update(text)

            # Remove all status classes
            for cls in ["status-success", "status-warning", "status-error", "status-info", "status-processing", "status-processing-dim"]:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

            # Start with bright state
            status_widget.add_class("status-processing")
            bottom_bar.add_class("status-processing")

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
            status_widget.remove_class("status-processing")
            status_widget.remove_class("status-processing-dim")
            bottom_bar.remove_class("status-processing")
            bottom_bar.remove_class("status-processing-dim")

            # Add new classes based on state
            if self._breathing_bright:
                status_widget.add_class("status-processing")
                bottom_bar.add_class("status-processing")
            else:
                status_widget.add_class("status-processing-dim")
                bottom_bar.add_class("status-processing-dim")

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
            for cls in ["status-processing", "status-processing-dim"]:
                status_widget.remove_class(cls)
                bottom_bar.remove_class(cls)

        except Exception as e:
            log_error("Failed to stop breathing effect", exception=e)

    def _set_busy(self, busy: bool) -> None:
        for bid in ("#add", "#backup", "#export", "#delete", "#refresh", "#send", "#recv", "#stake"):
            try:
                self.query_one(bid, Button).disabled = busy
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
            status_indicator = "[green]●[/green]"

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
            # Create clickable link with copy hint
            link_text = f"📋 [link={tzkt_url}]{oph_short}[/link] | [dim]Check TzKT →[/dim]"
            self.query_one("#tx_link_area", Static).update(link_text)
        except Exception as e:
            log_error("Failed to show transaction link", exception=e)

    def _clear_tx_link(self) -> None:
        """Clear the transaction link area."""
        try:
            self.query_one("#tx_link_area", Static).update("")
        except Exception as e:
            log_error("Failed to clear transaction link", exception=e)

    def _update_history_title(self) -> None:
        self.query_one("#hist_title", Static).update(
            f"[b]Recent Transactions[/b] (last {self.history_limit}, press m for more)"
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

        # Build TzKT link
        tzkt_base = tzkt_ui_base_from_rpc(self.rpc)
        tzkt_link = f"{tzkt_base}/{h}" if h else ""

        # Get wallet address
        wallet_addr = self.selected.address if self.selected else ""

        # Determine From and To based on direction
        if direction == "IN":
            from_addr = cp
            to_addr = wallet_addr or "Your Wallet"
            amt_label = f"[green]+{format_xtz(amt)} XTZ[/green]"
        elif direction == "OUT":
            from_addr = wallet_addr or "Your Wallet"
            to_addr = cp
            amt_label = f"[red]-{format_xtz(amt)} XTZ[/red]"
        else:
            from_addr = "?"
            to_addr = "?"
            amt_label = f"{format_xtz(amt)} XTZ"

        # Build details text - single line per field (except Hash and TzKT link)
        lines = [
            f"[b]Date:[/b] {ts}",
            "",
            f"[b]From:[/b] {from_addr}",
            "",
            f"[b]To:[/b] {to_addr}",
            "",
            f"[b]Amount:[/b] {amt_label}",
            "",
            f"[b]Hash:[/b]",
            f"  {h}",
        ]

        if baker:
            lines.extend([
                "",
                f"[b]Baker:[/b] {baker}",
            ])

        if tzkt_link:
            lines.extend([
                "",
                "[b]TzKT Explorer:[/b]",
                f"  {tzkt_link}",
            ])

        detail_pane.update("\n".join(lines))

    # -------------------------
    # Global arrows nav
    # -------------------------
    def action_nav_up(self) -> None:
        w = self.focused
        if isinstance(w, ListView):
            idx = w.index or 0
            w.index = max(0, idx - 1)
            return
        # General focus navigation with up arrow
        self.screen.focus_previous()

    def action_nav_down(self) -> None:
        w = self.focused
        if isinstance(w, ListView):
            n = len(w.children)
            if n <= 0:
                return
            idx = w.index or 0
            w.index = min(n - 1, idx + 1)
            return
        # General focus navigation with down arrow
        self.screen.focus_next()

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
            label_text = f"{name_with_tag:<30} │ {addr_short}"
            lv.append(ListItem(Label(label_text)))

        if self.accounts:
            self.selected = self.accounts[0]
            self._update_status_balance()
            self._load_history_for_selected(force=True)
            lv.focus()

    @on(ListView.Selected)
    def selected_account(self, event: ListView.Selected) -> None:
        if event.list_view.id != "accounts":
            return
        idx = event.list_view.index
        if idx is None:
            return
        if 0 <= idx < len(self.accounts):
            self.selected = self.accounts[idx]
            self._update_status_balance()
            self._load_history_for_selected(force=True)

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
            # Show fun messages when no wallet is selected
            self.query_one("#wallet_status", Static).update("[b]Wallet:[/b] [red]🚨 NONE! Import one![/red]")
            self.query_one("#wallet_balance", Static).update(f"[yellow]{self._empty_wallet_message}[/yellow]")
            self.query_one("#wallet_delegation", Static).update("[dim]🏜️ This bakery is empty...[/dim]")
            self.query_one("#wallet_staking", Static).update("[red]😭 Press 'i' to import a wallet NOW![/red]")
            self.query_one("#wallet_network", Static).update("")
            return

        try:
            # Check cache first
            cached_balance = self._get_cached_balance(self.selected.address)
            if cached_balance is not None:
                logging.debug(f"Using cached balance for {self.selected.address}")
                bal = cached_balance
            else:
                logging.debug(f"Fetching balance for {self.selected.address}")
                bal = get_balance_mutez(self.rpc, self.selected.address)
                self._cache_balance(self.selected.address, bal)

            # Wallet Name
            wallet_tag = " [dim](watch-only)[/dim]" if self.selected.enc is None else ""
            self.query_one("#wallet_status", Static).update(f"[b]Wallet:[/b] [b]{self.selected.name}[/b]{wallet_tag}")

            # Delegation info (needed for balance message)
            delegate = get_delegation_info(self.rpc, self.selected.address)

            # Staking balance (needed for balance message)
            staking_bal = get_staking_balance(self.rpc, self.selected.address)

            # Balance tier message (select once per refresh and cache)
            balance_xtz = mutez_to_xtz(bal)
            is_staking = staking_bal > 0
            is_delegating = delegate is not None
            self._balance_message = get_balance_message(balance_xtz, is_staking, is_delegating)

            # Balance with tier message
            self.query_one("#wallet_balance", Static).update(
                f"[b]Balance:[/b] [b]{format_xtz(balance_xtz)} XTZ[/b] [cyan]{self._balance_message}[/cyan]"
            )

            # Delegation display
            if delegate:
                delegate_short = delegate[:10] + "…" + delegate[-8:]
                self.query_one("#wallet_delegation", Static).update(f"[b]Delegated to:[/b] [dim]{delegate_short}[/dim]")
            else:
                self.query_one("#wallet_delegation", Static).update("[b]Delegated to:[/b] [dim]not delegated[/dim]")

            # Select message once per refresh and cache it
            if staking_bal > 0:
                # CHAD: Has staking balance - GREEN (positive reinforcement)
                self._staking_message = get_staking_message("chad")
                self.query_one("#wallet_staking", Static).update(
                    f"[b]Staked Balance:[/b] [b]{format_xtz(mutez_to_xtz(staking_bal))} XTZ[/b] [green]{self._staking_message}[/green]"
                )
            elif delegate:
                # BORING: Delegating but not staking - YELLOW (invitation to stake)
                self._staking_message = get_staking_message("boring")
                self.query_one("#wallet_staking", Static).update(
                    f"[b]Staked Balance:[/b] [dim]-[/dim] [yellow]{self._staking_message}[/yellow]"
                )
            else:
                # LAZY: Not delegating and not staking - RED (urgent call to action)
                self._staking_message = get_staking_message("lazy")
                self.query_one("#wallet_staking", Static).update(
                    f"[b]Staked Balance:[/b] [dim]-[/dim] [red]{self._staking_message}[/red]"
                )

            # Network with green dot format
            net = network_from_rpc(self.rpc)
            net_label = "Mainnet" if net == "mainnet" else "Ghostnet"
            self.query_one("#wallet_network", Static).update(f"[b]Network:[/b] [green]●[/green] {net_label}")

        except Exception as e:
            # Wallet Name even on error
            log_error("Failed to fetch balance", exception=e, address=self.selected.address)
            wallet_tag = " [dim](watch-only)[/dim]" if self.selected.enc is None else ""
            self.query_one("#wallet_status", Static).update(f"[b]Wallet:[/b] [b]{self.selected.name}[/b]{wallet_tag}")
            self.query_one("#wallet_balance", Static).update(f"[b]Balance:[/b] error: {e}")

    # -------------------------
    # History
    # -------------------------
    def _render_history(self, items: list[dict]) -> None:
        hv = self.query_one("#history", ListView)
        hv.clear()

        self.history_items = items
        self.history_selected_index = None

        if not items:
            hv.append(ListItem(Label("No transactions yet. Press 's' to send or 'x' to receive.")))
            try:
                self.query_one("#tx_detail_content", Static).update("No transactions available")
            except Exception as e:
                log_error("Failed to update tx detail content", exception=e)
            return

        for it in items:
            # Use relative time instead of full timestamp
            ts_raw = it.get("ts") or ""
            ts = format_relative_time(ts_raw)

            direction = it.get("direction") or "?"
            amt: Decimal = it.get("amount_xtz") or Decimal(0)
            cp = it.get("counterparty") or "?"

            # Format amount with fixed width for alignment
            amt_formatted = format_xtz(amt)

            # Fixed width columns for perfect alignment
            # Column widths: Time=14, DIR=3, Amount=15, Destination=20
            if direction == "IN":
                dir_text = "IN "  # 3 chars with space
                # Fixed 15-char field for amount (includes sign and XTZ)
                amt_str = f"[green]{f'+{amt_formatted} XTZ':<15}[/green]"
            elif direction == "OUT":
                dir_text = "OUT"  # 3 chars
                # Fixed 15-char field for amount
                amt_str = f"[red]{f'-{amt_formatted} XTZ':<15}[/red]"
            else:
                dir_text = "?  "  # 3 chars with spaces
                amt_str = f"{f'{amt_formatted} XTZ':<15}"

            # Truncate and pad counterparty address to fixed width
            if len(cp) > 20:
                cp_display = (cp[:10] + "…" + cp[-9:])  # Will be exactly 20 chars
            else:
                cp_display = f"{cp:<20}"  # Pad to 20 chars

            # Single line format with fixed widths for perfect alignment
            # Format: [14 time]  [3 dir]  [15 amount]  ↔  [20 destination]
            ts_padded = f"{ts:<14}"
            line = f"{ts_padded}  {dir_text}  {amt_str}  ↔  {cp_display}"

            hv.append(ListItem(Label(line, markup=True)))

        # Auto-select first transaction if available
        if items:
            try:
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
            else:
                self.history_cache.clear()

    def _load_history_for_selected(self, force: bool = False) -> None:
        selected = self._get_selected()
        if not selected:
            return
        addr = selected.address
        key = self._history_cache_key(addr)

        self._update_history_title()

        with self._history_cache_lock:
            if not force and key in self.history_cache:
                self._render_history(self.history_cache[key])
                return

        self._load_history(addr, self.history_limit)

    @work(exclusive=True, thread=True)
    def _load_history(self, address: str, limit: int) -> None:
        logging.info(f"Loading history for {address} (limit: {limit})")
        self._ui(self._start_spinner, get_message("refresh_checking"))
        try:
            items = get_xtz_history(self.rpc, address, limit=limit)
            logging.info(f"Loaded {len(items)} transaction(s) for {address}")
            with self._history_cache_lock:
                self.history_cache[(address, limit)] = items
            self._ui(self._render_history, items)
            self._ui(self._set_status, get_message("refresh_success"))
        except Exception as e:
            log_error("Failed to load history", exception=e, address=address, limit=limit)
            self._ui(self._render_history, [])
            self._ui(self._set_status, f"❌ Display shelf check failed: {e}")
        finally:
            self._ui(self._stop_spinner)
            self._ui(self._update_status_balance)

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
        if self.selected:
            self._invalidate_balance_cache(self.selected.address)
        self._update_status_balance()
        if self.selected:
            self._invalidate_history_cache(self.selected.address)
            self._load_history_for_selected(force=True)
        else:
            self._set_status(get_message("refresh_success"))

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
        self.history_limit += Config.HISTORY_INCREMENT
        self._invalidate_history_cache(self.selected.address)
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
        if not choice:
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

        if can_send and can_sim:
            msg = f"Network set to {choice}. RPC OK. Refreshing…"
        elif can_send and not can_sim:
            msg = f"Network set to {choice}. RPC can send but no simulation. Refreshing…"
        else:
            msg = f"Network set to {choice}. RPC restricted. Refreshing…"

        self.query_one("#wallet_balance", Static).update(msg)
        if self.selected:
            self._update_status_balance()
            self._load_history_for_selected(force=True)

    def action_receive(self) -> None:
        if not self.selected:
            self._set_status("ℹ️ No account selected")
            return
        self.push_screen(ReceiveScreen(self.selected.address))

    def action_stake(self) -> None:
        """Open stake/delegation modal."""
        if not self.accounts:
            self._set_status("ℹ️ No wallets available")
            return

        # Filter watch-only wallets
        stakeable_accounts = [acc for acc in self.accounts if acc.enc is not None]

        if not stakeable_accounts:
            self._set_status("⚠️ No wallets with secret keys available. Cannot delegate or stake")
            return

        self.push_screen(
            StakeScreen(
                accounts=self.accounts,
                rpc=self.rpc
            )
        )

    def action_show_address(self) -> None:
        """Show full address details in a modal."""
        if not self.selected:
            self._set_status("ℹ️ No account selected")
            return
        self.push_screen(AddressDetailScreen(self.selected.name, self.selected.address))

    @work(exclusive=True)
    async def action_backup(self) -> None:
        """Create a timestamped backup of selected wallet."""
        if not self.accounts:
            self._ui(self._set_status, "ℹ️ No wallets available")
            return

        # Show wallet selection modal
        selected_account = await self.push_screen_wait(
            BackupWalletSelectorScreen(
                self.accounts,
                title="Backup Wallet",
                message="Select wallet to backup:",
                button_label="Backup"
            )
        )

        if not selected_account:
            self._ui(self._set_status, "📦 Backup cancelled - Recipe stays in the kitchen! 🍳")
            return

        try:
            from datetime import datetime
            import json

            # Create backup directory
            backup_dir = Path("data/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            wallet_name = selected_account.name.replace(" ", "_")
            backup_filename = f"wallet_{wallet_name}_{timestamp}.json"
            backup_path = backup_dir / backup_filename

            # Find the wallet data in the store
            wallet_data = None
            accounts_data = self.store.get("accounts", [])
            for acc_data in accounts_data:
                if acc_data.get("address") == selected_account.address:
                    wallet_data = acc_data
                    break

            if not wallet_data:
                self._ui(self._set_status, f"❌ Wallet data not found for {selected_account.name}")
                return

            # Create backup structure
            backup_content = {
                "backup_timestamp": timestamp,
                "backup_type": "single_wallet",
                "wallet": wallet_data,
                "recent_destinations": self.recent_to_by_wallet.get(selected_account.address, [])
            }

            # Write backup file
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_content, f, indent=2, ensure_ascii=False)

            # Get file size for confirmation
            size_kb = backup_path.stat().st_size / 1024
            # Get absolute path for display
            abs_backup_path = backup_path.resolve()

            logging.info(f"Created backup for {selected_account.name}: {backup_path}")
            backup_msg = get_message("backup_success", name=selected_account.name)
            self._ui(self._set_status_styled,
                f"{backup_msg} ({size_kb:.1f} KB) → {abs_backup_path}",
                "success",
                5.0
            )

        except Exception as e:
            log_error("Backup failed", exception=e)
            self._ui(self._set_status_styled, f"❌ Backup failed: {e}", "error", 5.0)

    @work(exclusive=True)
    async def action_delete_wallet(self) -> None:
        """Delete a wallet after selection and confirmation."""
        if not self.accounts:
            self._set_status("ℹ️ No wallets available")
            return

        # Show wallet selection modal
        selected_account = await self.push_screen_wait(
            DeleteWalletSelectorScreen(
                self.accounts,
                title="Delete Wallet",
                message="Select wallet to delete:",
                button_label="Delete",
                button_variant="error"
            )
        )

        if not selected_account:
            self._set_status("🔥 Delete cancelled - Saved from the flames! 😅")
            return

        wallet_name = selected_account.name
        wallet_addr = selected_account.address

        # Show confirmation dialog
        confirmed = await self.push_screen_wait(
            ConfirmScreen(
                f"Are you sure you want to delete wallet '[b]{wallet_name}[/b]'?\n\n"
                f"Address: [dim]{wallet_addr}[/dim]\n\n"
                f"[yellow]⚠️ This will burn the wallet like overcooked toast![/yellow]\n"
                f"[yellow]Once burned, there's no unburning it! 🔥🍞[/yellow]\n\n"
                f"[dim](The wallet will only be removed from this app,\n"
                f"not from the blockchain)[/dim]",
                title="🔥 Burn Wallet?",
                yes_label="Burn It! 🔥",
                no_label="No, Keep It!"
            )
        )

        if not confirmed:
            self._set_status("🔥 Delete cancelled - Wallet saved from the flames! Phew! 😅")
            return

        # Remove from accounts list
        try:
            accounts_data = self.store.get("accounts", [])
            accounts_data = [a for a in accounts_data if a.get("address") != wallet_addr]
            self.store["accounts"] = accounts_data
            save_store(self.store)

            # Reload accounts
            self.accounts = list_accounts(self.store)

            # Clear selection only if we deleted the currently selected wallet
            if self.selected and self.selected.address == wallet_addr:
                self.selected = None
                # Clear UI
                self._update_status_balance()
                self._render_history([])

            # Show success message first
            logging.info(f"Deleted wallet: {wallet_name} ({wallet_addr})")
            delete_msg = get_message("delete_success", name=wallet_name)
            self._set_status_styled(
                delete_msg,
                style="warning",
                duration=5.0
            )

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
            # Step 0: Choose import type
            import_type = await self.push_screen_wait(ImportTypeSelectorScreen())
            if not import_type:
                self._set_status(get_message("import_cancel"))
                return

            # Handle different import types
            if import_type == "backup":
                await self._import_from_backup()
            elif import_type == "secret":
                await self._import_with_secret_key()
            elif import_type == "watch":
                await self._import_watch_only()
        finally:
            self._set_busy(False)

    async def _import_from_backup(self) -> None:
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
                    fun_note=f"Time to reheat some fresh bread from the pantry! 🥖📂\nDefault location: {backup_dir_abs}"
                )
            )
            if not backup_path_str:
                self._set_status("↩️ Import cancelled - Bread stays in storage! 📦")
                return

            backup_path = Path(backup_path_str.strip()).expanduser()

            # Validate file exists
            if not backup_path.exists():
                self._set_status(f"❌ Backup file not found: {backup_path}")
                return

            if not backup_path.is_file():
                self._set_status(f"❌ Path is not a file: {backup_path}")
                return

            # Read and parse backup file
            self._set_status("🔍 Reading the recipe from the pantry...")
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
            except json.JSONDecodeError as e:
                log_error("Invalid JSON in backup file", exception=e)
                self._set_status(f"❌ Invalid backup file format! Recipe got soggy! 💧")
                return
            except Exception as e:
                log_error("Failed to read backup file", exception=e)
                self._set_status(f"❌ Failed to read backup: {e}")
                return

            # Validate backup structure
            if not isinstance(backup_data, dict):
                self._set_status("❌ Invalid backup: Not a valid recipe book! 📖")
                return

            wallet_data = backup_data.get("wallet")
            if not wallet_data:
                self._set_status("❌ Invalid backup: No wallet data found in recipe! 🤷")
                return

            # Extract wallet info
            name = wallet_data.get("name", "Imported Wallet")
            addr = wallet_data.get("address")
            enc = wallet_data.get("enc")

            if not addr:
                self._set_status("❌ Invalid backup: Missing address in wallet data!")
                return

            if not is_tz_address(addr):
                self._set_status(f"❌ Invalid address in backup: {addr}")
                return

            # Check if wallet already exists
            for existing in self.accounts:
                if existing.address == addr:
                    self._set_status(f"⚠️ Wallet with address {addr[:10]}...{addr[-8:]} already exists!")
                    return

            # Step 2: Optionally rename the wallet
            self._set_status(f"✨ Found wallet: {name}")
            new_name = await self.push_screen_wait(
                PromptScreen(
                    "📝 Step 2: Confirm/Rename Wallet",
                    placeholder=name,
                    ok_label="🎉 Import!",
                    wallet_info=f"[b cyan]Original:[/b cyan] {name} | [b cyan]Address:[/b cyan] {addr[:10]}...{addr[-8:]}",
                    fun_note="Keep the name or give it a fresh label! Like renaming bread... baguette? 🥖"
                )
            )
            if new_name:
                name = new_name.strip()

            if not name:
                self._set_status("↩️ Import cancelled - Nameless bread stays in the pantry! 🏷️")
                return

            # Import the wallet
            upsert_account(self.store, Account(name=name, address=addr, enc=enc))

            # Restore recent destinations if available
            recent_dests = backup_data.get("recent_destinations", [])
            if recent_dests:
                self.recent_to_by_wallet[addr] = recent_dests

            save_store(self.store)
            self._render_accounts()

            # Success message
            success_msg = get_message("import_backup", name=name)
            if enc:
                backup_msg = "Restored pastry with full powers! Ready to send! 🔥"
            else:
                backup_msg = "Restored as display-only! Watch mode activated! 👀"
            self._set_status_styled(
                f"✓ {success_msg} {backup_msg} ✨",
                style="success",
                duration=5.0
            )
            logging.info(f"Imported wallet from backup: {name} ({addr})")

        except Exception as e:
            log_error("Backup import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)

    async def _import_with_secret_key(self) -> None:
        """Import wallet with secret key (auto-derives address)."""
        try:
            # Step 1: Wallet name
            name = await self.push_screen_wait(
                PromptScreen(
                    "🎯 Step 1: Name Your Wallet",
                    placeholder="e.g., My Savings, Trading Account...",
                    ok_label="Next →",
                    fun_note="Choose a memorable name! Like naming a pet, but for money. 💰"
                )
            )
            if not name:
                self._set_status(get_message("import_cancel"))
                return

            # Step 2: Secret key
            self._set_status("🔐 Next step! Enter your secret key...")
            secret = await self.push_screen_wait(
                PromptScreen(
                    "🔑 Step 2: Secret Key",
                    placeholder="edsk...",
                    ok_label="Next →",
                    wallet_info=f"[b cyan]Wallet:[/b cyan] {name}",
                    fun_note="We'll magically figure out your address from this! 🔮✨"
                )
            )

            if not secret:
                self._set_status("↩️ Import cancelled - No flour, no bread! 🌾")
                return

            # Derive address from secret key
            self._set_status("🔮 Deriving your address from the secret key...")
            try:
                secret = secret.strip()
                key = key_from_encoded_secret(secret)
                addr = key.public_key_hash()
                self._set_status(f"✨ Address derived: {addr[:10]}...{addr[-8:]}")
            except Exception as e:
                log_error("Failed to derive address from secret key", exception=e)
                self._set_status(f"❌ Invalid secret key! Can't bake bread with bad flour! 😅 Error: {e}")
                return

            # Step 3: Passphrase to encrypt
            self._set_status("🛡️ Perfect! Now let's secure that key...")
            pw = await self.push_screen_wait(
                PromptScreen(
                    "🔐 Step 3: Create Passphrase",
                    password=True,
                    placeholder="Strong passphrase (you'll need this to send XTZ)",
                    ok_label="🎉 Import!",
                    wallet_info=f"[b cyan]Wallet:[/b cyan] {name} | [b cyan]Address:[/b cyan] {addr[:10]}...{addr[-8:]}",
                    fun_note="Make it strong! Like a coffee, but for security. ☕🔒"
                )
            )
            if not pw:
                self._set_status("↩️ Import cancelled - Can't lock the bakery without a key! 🔐🥖")
                return

            enc = encrypt_secret(secret, pw)
            upsert_account(self.store, Account(name=name, address=addr, enc=enc))
            save_store(self.store)
            self._render_accounts()

            success_msg = get_message("import_secret", name=name)
            self._set_status_styled(
                f"✓ {success_msg} Full wallet powers unlocked! 🔥",
                style="success",
                duration=5.0
            )

        except Exception as e:
            log_error("Secret key import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)

    async def _import_watch_only(self) -> None:
        """Import watch-only wallet (no secret key)."""
        try:
            # Step 1: Wallet name
            name = await self.push_screen_wait(
                PromptScreen(
                    "🎯 Step 1: Name Your Wallet",
                    placeholder="e.g., Cold Storage Monitor, Friend's Wallet...",
                    ok_label="Next →",
                    fun_note="Choose a memorable name! Like naming a pet, but for money. 💰"
                )
            )
            if not name:
                self._set_status(get_message("import_cancel"))
                return

            # Step 2: Address
            self._set_status("👀 Watch-only mode! Let's get your address...")
            addr = await self.push_screen_wait(
                PromptScreen(
                    "🔑 Step 2: Your Tezos Address",
                    placeholder="tz1... or tz2... or tz3... or tz4...",
                    ok_label="🎉 Import!",
                    wallet_info=f"[b cyan]Wallet:[/b cyan] {name}",
                    fun_note="Watch-only = You can monitor but not send. Like a diet at the bakery! 🪟🥖"
                )
            )
            if not addr:
                self._set_status("↩️ Import cancelled - Wallet left unbaked! 🥐")
                return

            addr = addr.strip()
            if not is_tz_address(addr):
                self._set_status("❌ Invalid account address. Must be tz1/tz2/tz3/tz4")
                return

            upsert_account(self.store, Account(name=name, address=addr, enc=None))
            save_store(self.store)
            self._render_accounts()

            success_msg = get_message("import_watch", name=name)
            self._set_status_styled(
                f"✓ {success_msg} Watch-only mode activated! 🥖",
                style="success",
                duration=5.0
            )

        except Exception as e:
            log_error("Watch-only import failed", exception=e)
            self._set_status_styled(f"❌ Import failed: {e}", style="error", duration=5.0)

    @work(exclusive=True)
    async def action_send(self) -> None:
        if not self.selected:
            self._set_status("ℹ️ No account selected")
            return
        if self.selected.enc is None:
            self._set_status("⚠️ Selected account is watch-only. Add a secret key to send")
            return


        if self._send_in_progress:
            self._set_status("⏳ Send operation already in progress…")
            return

        # Get recent destinations for the selected wallet only
        wallet_recents = self._get_recent_to_for_wallet(self.selected.address)
        to_addr = await self.push_screen_wait(
            DestinationPickerScreen(wallet_recents, self.accounts, self.selected.address)
        )
        if not to_addr:
            return

        to_addr = to_addr.strip()
        if not is_tezos_destination(to_addr):
            self._set_status("❌ Invalid destination. Must be tz1/tz2/tz3/tz4 or KT1")
            return

        amount_str = await self.push_screen_wait(
            SendAmountScreen(
                "💰 How much XTZ to send?",
                placeholder="e.g., 0.123 or 1.5",
                ok_label="Next →",
                fun_note="Remember: fees are extra! Like shipping, but for blockchain. 📦"
            )
        )
        if not amount_str:
            return

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("amount must be > 0")
        except Exception as e:
            log_error("Invalid amount format", exception=e, amount_str=amount_str)
            self._set_status("❌ Invalid amount")
            return

        # Validate sufficient balance
        try:
            current_balance_mutez = get_balance_mutez(self.rpc, self.selected.address)
            current_balance_xtz = mutez_to_xtz(current_balance_mutez)

            # Conservative estimate: amount + max typical fee (0.01 XTZ for reveal + tx)
            # This is a rough check; actual fee will be calculated during confirmation
            estimated_max_fee = Decimal("0.01")
            total_needed = amount + estimated_max_fee

            if current_balance_xtz < total_needed:
                self._set_status(
                    f"❌ Insufficient balance. "
                    f"Have: {format_xtz(current_balance_xtz)} XTZ, "
                    f"Need: ~{format_xtz(total_needed)} XTZ (including fees)"
                )
                logging.warning(
                    f"Insufficient balance check: have {current_balance_xtz} XTZ, "
                    f"need ~{total_needed} XTZ for {amount} XTZ send"
                )
                return
        except Exception as e:
            # If balance check fails, log it but allow user to proceed
            # (they might have balance but RPC is temporarily unavailable)
            log_warning("Balance check failed, allowing user to proceed", exception=e)

        pw = await self.push_screen_wait(
            SendPassphraseScreen(
                "🔐 Enter Your Passphrase",
                password=True,
                placeholder="Your wallet passphrase",
                wallet_info=f"[b cyan]Wallet:[/b cyan] {self.selected.name}",
                ok_label="🚀 Send!",
                fun_note="The moment of truth! Like opening a safe, but cooler. 🔓✨"
            )
        )
        if not pw:
            return

        try:
            secret = decrypt_secret(self.selected.enc, pw)
            key = key_from_encoded_secret(secret)
        except Exception as e:
            log_error("Failed to decrypt secret key", exception=e)
            self._set_status(f"❌ Decrypt key failed: {e}")
            return

        self._send_in_progress = True

        # Disable underlying buttons while the confirm modal is open.
        # This prevents accidental clicks/keypresses from re-triggering the send flow when the modal closes.
        self._set_busy(True)

        resp = await self.push_screen_wait(
            ConfirmSendScreen(self.rpc, key, self.selected.address, to_addr, amount)
        )
        if not resp or not resp.get("ok"):
            self._set_status("↩️ Transaction cancelled - Order cancelled, bread stays in the bakery! 🥖💼")
            self._set_busy(False)
            self._send_in_progress = False
            return

        from_addr = self.selected.address
        self._send_and_refresh(
            from_addr,
            key,
            to_addr,
            amount,
            fee_mutez=resp.get("fee_mutez"),
            gas_limit=resp.get("gas_limit"),
            storage_limit=resp.get("storage_limit"),
        )

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
                    self._ui(self._set_status_styled, f"✓ 🥐 Baked to perfection! | 👨‍🍳 Baker: {baker_short}", "success")
                else:
                    self._ui(self._set_status_styled, f"✓ 🥐 Baked to perfection! ✨ | Hash: {oph_short}", "success")

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

