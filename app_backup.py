from __future__ import annotations
from decimal import Decimal
import re
import threading
import urllib.request
import urllib.error
import time
import json
from typing import Any, Callable, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, ListView, ListItem, Label, Button, Input, Static

from wallet.store import load_store, save_store, list_accounts, upsert_account, Account
from wallet.crypto import encrypt_secret, decrypt_secret
from wallet.tezos import (
    get_balance_mutez,
    mutez_to_xtz,
    key_from_encoded_secret,
    send_xtz,
    get_xtz_history,
    estimate_send_xtz,
)

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


def network_from_rpc(rpc: str) -> str:
    return "ghostnet" if "ghostnet" in (rpc or "").lower() else "mainnet"


def tzkt_ui_base_from_rpc(rpc: str) -> str:
    return "https://ghostnet.tzkt.io" if network_from_rpc(rpc) == "ghostnet" else "https://tzkt.io"


def _xtz_to_mutez(x: Decimal) -> int:
    return int((x * Decimal(1_000_000)).to_integral_value())


# --- RPC capability probing (public RPCs can be read-only / restricted) ---
# We probe for two endpoints:
# - /injection/operation (needed to broadcast operations)
# - /chains/main/blocks/head/helpers/scripts/run_operation (needed for simulation/autofill)
#
# We intentionally treat 405/415 as "exists" because those endpoints typically require POST.

_OK_CODES = {200, 405, 415}

# Candidates ordered by preference. We will probe them at runtime and pick the first
# one that supports BOTH simulation (run_operation) and injection.
_MAINNET_RPC_CANDIDATES = [
    "https://mainnet.tezos.ecadinfra.com",
    "https://mainnet.smartpy.io",
    "https://mainnet.api.tez.ie",
    # Fallbacks (may be read-only / throttled / flaky depending on policy/region):
    "https://rpc.tzkt.io/mainnet",
    "https://rpc.tzbeta.net",
]

_GHOSTNET_RPC_CANDIDATES = [
    "https://ghostnet.tezos.marigold.dev",
    "https://ghostnet.tezos.ecadinfra.com",
    "https://ghostnet.smartpy.io",
    "https://rpc.tzkt.io/ghostnet",
]


def _http_code(url: str, timeout_s: float = 2.5) -> int:
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
        except Exception:
            return 0
    except Exception:
        return 0




def _fetch_json(url: str, timeout_s: float = 5.0) -> Any:
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


def find_baker_for_operation(rpc: str, oph: str, max_depth: int = 20) -> Optional[str]:
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
                timeout_s=4.0,
            )
        except Exception:
            continue

        try:
            if any(oph == h for vp in op_hashes for h in vp):
                try:
                    header = _fetch_json(
                        f"{rpc}/chains/main/blocks/{block_id}/header",
                        timeout_s=4.0,
                    )
                    baker = header.get("baker")
                    if isinstance(baker, str) and baker.startswith("tz"):
                        return baker
                except Exception:
                    return None
                return None
        except Exception:
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


class PromptScreen(ModalScreen[str]):
    def __init__(self, title: str, placeholder: str = "", password: bool = False):
        super().__init__()
        self._title = title
        self._placeholder = placeholder
        self._password = password

    def compose(self) -> ComposeResult:
        yield Static(self._title)
        yield Input(placeholder=self._placeholder, password=self._password, id="inp")
        with Horizontal():
            yield Button("OK", id="ok", variant="primary")
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


class NetworkPickerScreen(ModalScreen[str]):
    """Picker para elegir red sin escribir (↑/↓ + Enter o click)."""

    def __init__(self, current: str):
        super().__init__()
        self.current = current  # "mainnet" / "ghostnet"

    def compose(self) -> ComposeResult:
        yield Static("Select network (Enter to confirm, Esc to cancel)")
        yield ListView(id="networks")
        with Horizontal():
            yield Button("Select", id="select", variant="primary")
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
        except Exception:
            pass

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


class ReceiveScreen(ModalScreen[None]):
    def __init__(self, address: str):
        super().__init__()
        self.address = address

    def compose(self) -> ComposeResult:
        lines = [
            "[b]Receive funds[/b]",
            "",
            "Copy this address:",
            f"[b]{self.address}[/b]",
            "",
            "Enter / click Copy to copy to clipboard.",
            "Esc to close.",
        ]
        yield Static("\n".join(lines), id="recv_text", markup=True)
        with Horizontal():
            yield Button("Copy", id="copy", variant="primary")
            yield Button("Close", id="close")

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
            self.dismiss(None)
        if getattr(event, "key", None) == "enter":
            self._copy_and_close()

    def _copy_and_close(self) -> None:
        try:
            self.app.copy_to_clipboard(self.address)  # type: ignore[attr-defined]
            self.app._set_status("✅ Address copied to clipboard.")  # type: ignore[attr-defined]
        except Exception:
            self.app._set_status(f"Copy failed. Address: {self.address}")  # type: ignore[attr-defined]
        self.dismiss(None)

    @on(Button.Pressed, "#copy")
    def copy_pressed(self) -> None:
        self._copy_and_close()

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.dismiss(None)


class TxDetailsScreen(ModalScreen[None]):
    def __init__(self, rpc: str, tx: dict):
        super().__init__()
        self.rpc = rpc
        self.tx = tx

    def compose(self) -> ComposeResult:
        ts = (self.tx.get("ts") or "").replace("T", " ").replace("Z", "")
        direction = self.tx.get("direction") or "?"
        amt: Decimal = self.tx.get("amount_xtz") or Decimal(0)
        cp = self.tx.get("counterparty") or "?"
        h = self.tx.get("hash") or ""
        baker = self.tx.get("baker") or ""
        tzkt = f"{tzkt_ui_base_from_rpc(self.rpc)}/{h}" if h else ""

        lines = [
            "[b]Transaction details[/b]",
            "",
            f"Time:         {ts}",
            f"Direction:    {direction}",
            f"Amount:       {amt} XTZ",
            f"Counterparty: {cp}",
            "",
            f"Hash:         {h}",
            (f"Baker:        {baker}" if baker else ""),
            f"TzKT:         {tzkt}",
            "",
            "Press Esc to close.",
        ]
        yield Static("\n".join(lines), id="tx_details", markup=True)
        yield Button("Close", id="close", variant="primary")

    @on(Button.Pressed, "#close")
    def close_pressed(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if getattr(event, "key", None) == "escape":
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
    #summary { padding: 0 0 1 0; }
    #fee_title { padding: 0 0 0 0; }
    #fee_list { height: 4; }
    #advanced { padding: 1 0 0 0; }
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
            self._est_timer = self.set_interval(0.15, self._tick_est_pulse)

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
                f"Network:   {net}",
                "",
                f"From:      {self.from_addr}",
                f"To:        {self.to_addr}",
                "",
                f"Amount:    {self.amount} XTZ",
                "",
                f"Fee:       {'[reverse]estimating…[/reverse]' if ((self._est_i // 3) % 2) else '[b]estimating…[/b]'}",
            ]
        elif err:
            lines = [
                "[b]Confirm transaction[/b]",
                "",
                f"Network:   {net}",
                "",
                f"From:      {self.from_addr}",
                f"To:        {self.to_addr}",
                "",
                f"Amount:    {self.amount} XTZ",
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
                f"Network:   {net}",
                "",
                f"From:      {self.from_addr}",
                f"To:        {self.to_addr}",
                "",
                f"Amount:    {self.amount} XTZ",
                "",
                f"Fee ({self._fee_choice}): {chosen_total} XTZ",
            ]

            if self._advanced:
                lines += [
                    f"Reveal:    {'yes (first send)' if reveal_needed else 'no'}",
                    "",
                    f"[dim]Suggested limits:[/dim] gas={gas}, storage={storage}",
                    "[dim]Tip:[/dim] use Economy/Normal/Priority, Advanced only if you know what you’re doing.",
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
                texts.append(f"{mark}{title} — total fee: {total_xtz} XTZ")

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
            except Exception:
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
        except Exception:
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
            except Exception:
                pass
            self.send_pressed()


class DestinationPickerScreen(ModalScreen[str]):
    """Input + lista de últimos destinos (click/enter). Flechas funcionan si lista tiene foco."""
    def __init__(self, recents: list[str]):
        super().__init__()
        self.recents = recents[:10]

    def compose(self) -> ComposeResult:
        yield Static("Destination (tz1/tz2/tz3/tz4 or KT1). Enter to confirm. Esc to cancel.")
        yield Input(placeholder="Paste address here…", id="dest_inp")
        yield Static("Recent destinations (↓ to focus list, Enter to use):", id="recent_title")
        yield ListView(id="recent_list")
        with Horizontal():
            yield Button("OK", id="ok", variant="primary")
            yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#dest_inp", Input).focus()
        lv = self.query_one("#recent_list", ListView)
        lv.clear()
        if not self.recents:
            lv.append(ListItem(Label("No recent destinations.")))
            return
        for a in self.recents:
            lv.append(ListItem(Label(a)))

    def _current_value(self) -> str:
        return (self.query_one("#dest_inp", Input).value or "").strip()

    @on(Input.Submitted, "#dest_inp")
    def submitted(self, event: Input.Submitted) -> None:
        self.dismiss((event.value or "").strip())

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
            except Exception:
                pass

        if key == "enter":
            try:
                lv = self.query_one("#recent_list", ListView)
                if lv.has_focus and self.recents:
                    idx = lv.index or 0
                    if 0 <= idx < len(self.recents):
                        self.dismiss(self.recents[idx])
                        return
            except Exception:
                pass


class WalletApp(App):
    CSS = """
    Screen { padding: 1; }

    #status { height: 3; }

    #rpc_row { height: 1; }
    #rpc { height: 1; }
    #net_badge {
        padding: 0 1;
        margin-left: 1;
        height: 1;
        content-align: center middle;
    }
    .mainnet_badge { background: #16a34a; color: black; }
    .ghostnet_badge { background: #f59e0b; color: black; }

    #accounts { height: 6; }
    #hist_title { height: 1; }
    #history { height: 16; }

    #recv_text { padding: 1; }
    #tx_details { padding: 1; }
    """

    BINDINGS = [
        ("a", "add_account", "Add account"),
        ("r", "refresh", "Refresh"),
        ("s", "send", "Send XTZ"),
        ("x", "receive", "Receive"),
        ("d", "tx_details", "Tx details"),
        ("enter", "tx_details", "Tx details"),
        ("m", "more_history", "More history"),
        ("n", "network", "Network"),
        ("up", "nav_up", "Up"),
        ("down", "nav_down", "Down"),
        ("q", "quit", "Quit"),
    ]

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self):
        super().__init__()
        self.store = load_store()
        self.rpc = self.store.get("rpc") or "https://ghostnet.tezos.marigold.dev"
        self.accounts = list_accounts(self.store)
        self.selected: Account | None = None

        self.history_cache: dict[tuple[str, int], list[dict]] = {}
        self.history_items: list[dict] = []
        self.history_selected_index: int | None = None
        self.history_limit: int = 20

        self._spin_msg: str | None = None
        self._spin_i: int = 0
        self._spin_timer = None

        self._last_status: str = ""

        self._send_in_progress: bool = False

        self.recent_to: list[str] = (
            list(self.store.get("recent_to", []))
            if isinstance(self.store.get("recent_to", []), list)
            else []
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Horizontal(id="rpc_row"):
                yield Static(f"RPC: {self.rpc}", id="rpc")
                yield Static("", id="net_badge")

            yield ListView(id="accounts")
            yield Static("Select an account to see balance.", id="status", markup=True)

            with Horizontal():
                yield Button("Add (a)", id="add")
                yield Button("Refresh (r)", id="refresh")
                yield Button("Send (s)", id="send")
                yield Button("Receive (x)", id="recv")

            yield Static(f"History (last {self.history_limit}):  (m = more)", id="hist_title")
            yield ListView(id="history")

        yield Footer()

    def on_mount(self) -> None:
        self._update_net_badge()
        self._render_accounts()
        # Auto-pick an RPC that supports BOTH simulation and injection.
        # Many public RPCs are read-only or restrict sensitive endpoints.
        self._autodetect_rpc()

    @work(exclusive=True, thread=True)
    def _autodetect_rpc(self) -> None:
        """Detect and switch to a working RPC (supports injection + simulation).

        Runs in a worker thread (network I/O).
        """
        current = self.rpc
        self._ui(self._set_status, "🔎 Checking RPC capabilities…")

        best, can_send, can_sim = choose_working_rpc(current)

        if best != current:
            self.rpc = best
            self.store["rpc"] = self.rpc
            save_store(self.store)
            self._ui(self._update_rpc_label)
            self._ui(self._update_net_badge)

            # History & balances depend on the RPC; refresh caches.
            self._invalidate_history_cache()
            self.history_limit = 20
            self._ui(self._update_history_title)

        if can_send and can_sim:
            msg = f"✅ RPC OK (simulation + injection): {self.rpc}"
        elif can_send and not can_sim:
            msg = f"⚠️ RPC allows sending, but simulation is restricted: {self.rpc}"
        else:
            msg = f"⚠️ RPC appears read-only / restricted: {self.rpc}"

        self._ui(self._set_status, msg)

    # -------------------------
    # Thread-safe UI bridge
    # -------------------------
    def _ui(self, fn: Callable, *args, **kwargs):
        try:
            app_tid = getattr(self, "_thread_id", None)
            if app_tid is not None and threading.get_ident() == app_tid:
                return fn(*args, **kwargs)
        except Exception:
            pass
        return self.call_from_thread(fn, *args, **kwargs)

    # -------------------------
    # Spinner
    # -------------------------
    def _start_spinner(self, msg: str) -> None:
        self._spin_msg = msg
        self._spin_i = 0
        if self._spin_timer is None:
            self._spin_timer = self.set_interval(0.1, self._tick_spinner)
        self._tick_spinner()

    def _stop_spinner(self) -> None:
        self._spin_msg = None
        self._spin_i = 0
        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None
        if self._last_status:
            self.query_one("#status", Static).update(self._last_status)

    def _tick_spinner(self) -> None:
        if not self._spin_msg:
            return
        frame = self.SPINNER_FRAMES[self._spin_i % len(self.SPINNER_FRAMES)]
        # Simple pulse effect for better visibility (status widget has markup=True).
        pulse = (self._spin_i // 3) % 2
        msg = self._spin_msg
        if pulse:
            msg = f"[reverse]{msg}[/reverse]"
        else:
            msg = f"[b]{msg}[/b]"
        self._spin_i += 1
        self.query_one("#status", Static).update(f"{frame} {msg}")

    # -------------------------
    # UI helpers
    # -------------------------
    def _set_status(self, text: str) -> None:
        self._last_status = text
        self.query_one("#status", Static).update(text)

    def _set_busy(self, busy: bool) -> None:
        for bid in ("#add", "#refresh", "#send", "#recv"):
            try:
                self.query_one(bid, Button).disabled = busy
            except Exception:
                pass

    def _update_rpc_label(self) -> None:
        self.query_one("#rpc", Static).update(f"RPC: {self.rpc}")

    def _update_net_badge(self) -> None:
        badge = self.query_one("#net_badge", Static)
        net = network_from_rpc(self.rpc)
        badge.remove_class("mainnet_badge")
        badge.remove_class("ghostnet_badge")
        if net == "mainnet":
            badge.add_class("mainnet_badge")
            badge.update("MAINNET")
        else:
            badge.add_class("ghostnet_badge")
            badge.update("GHOSTNET")

    def _update_history_title(self) -> None:
        self.query_one("#hist_title", Static).update(
            f"History (last {self.history_limit}):  (m = more)"
        )

    # -------------------------
    # Global arrows nav
    # -------------------------
    def action_nav_up(self) -> None:
        w = self.focused
        if isinstance(w, ListView):
            idx = w.index or 0
            w.index = max(0, idx - 1)
            return
        try:
            hv = self.query_one("#history", ListView)
            hv.focus()
            idx = hv.index or 0
            hv.index = max(0, idx - 1)
        except Exception:
            pass

    def action_nav_down(self) -> None:
        w = self.focused
        if isinstance(w, ListView):
            n = len(w.children)
            if n <= 0:
                return
            idx = w.index or 0
            w.index = min(n - 1, idx + 1)
            return
        try:
            hv = self.query_one("#history", ListView)
            hv.focus()
            n = len(hv.children)
            if n <= 0:
                return
            idx = hv.index or 0
            hv.index = min(n - 1, idx + 1)
        except Exception:
            pass

    # -------------------------
    # Accounts
    # -------------------------
    def _render_accounts(self) -> None:
        lv = self.query_one("#accounts", ListView)
        lv.clear()

        self.accounts = list_accounts(self.store)
        for a in self.accounts:
            tag = " (watch)" if a.enc is None else ""
            lv.append(ListItem(Label(f"{a.name} — {a.address}{tag}")))

        if self.accounts:
            self.selected = self.accounts[0]
            self._update_status_balance()
            self._load_history_for_selected(force=True)
            lv.focus()
        else:
            self.selected = None
            self._set_status("No accounts yet. Press 'a' to add one.")
            self._render_history([])

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

    def _update_status_balance(self) -> None:
        if not self.selected:
            return
        try:
            bal = get_balance_mutez(self.rpc, self.selected.address)
            self._set_status(
                f"Balance: {mutez_to_xtz(bal):.6f} XTZ   |   {self.selected.name}"
            )
        except Exception as e:
            self._set_status(f"Balance error: {e}")

    # -------------------------
    # History
    # -------------------------
    def _render_history(self, items: list[dict]) -> None:
        hv = self.query_one("#history", ListView)
        hv.clear()

        self.history_items = items
        self.history_selected_index = None

        if not items:
            hv.append(ListItem(Label("No transactions found.")))
            return

        for it in items:
            ts = (it.get("ts") or "").replace("T", " ").replace("Z", "")
            direction = it.get("direction") or "?"
            amt: Decimal = it.get("amount_xtz") or Decimal(0)
            cp = it.get("counterparty") or "?"
            h = it.get("hash") or ""
            h_short = (h[:8] + "…" + h[-4:]) if len(h) > 16 else h

            if direction == "IN":
                dcol = "[green]IN[/green]"
                acol = f"[green]{amt:.6f}[/green]"
            elif direction == "OUT":
                dcol = "[red]OUT[/red]"
                acol = f"[red]{amt:.6f}[/red]"
            else:
                dcol = direction
                acol = f"{amt:.6f}"

            baker = it.get("baker") or ""
            baker_part = f"  |  baker: {baker}" if baker else ""
            line = f"{ts}  {dcol}  {acol} XTZ  ↔  {cp}  |  {h_short}{baker_part}"
            hv.append(ListItem(Label(line, markup=True)))

    def _history_cache_key(self, address: str) -> tuple[str, int]:
        return (address, self.history_limit)

    def _invalidate_history_cache(self, address: str | None = None) -> None:
        if address:
            for k in list(self.history_cache.keys()):
                if k[0] == address:
                    self.history_cache.pop(k, None)
        else:
            self.history_cache.clear()

    def _load_history_for_selected(self, force: bool = False) -> None:
        if not self.selected:
            return
        addr = self.selected.address
        key = self._history_cache_key(addr)

        self._update_history_title()

        if not force and key in self.history_cache:
            self._render_history(self.history_cache[key])
            return

        self._load_history(addr, self.history_limit)

    @work(exclusive=True, thread=True)
    def _load_history(self, address: str, limit: int) -> None:
        self._ui(self._start_spinner, "Loading history…")
        try:
            items = get_xtz_history(self.rpc, address, limit=limit)
            self.history_cache[(address, limit)] = items
            self._ui(self._render_history, items)
        except Exception as e:
            self._ui(self._render_history, [])
            self._ui(self._set_status, f"History error: {e}")
        finally:
            self._ui(self._stop_spinner)
            self._ui(self._update_status_balance)

    # -------------------------
    # Recents helpers
    # -------------------------
    def _push_recent_to(self, addr: str) -> None:
        addr = (addr or "").strip()
        if not addr:
            return
        self.recent_to = [x for x in self.recent_to if x != addr]
        self.recent_to.insert(0, addr)
        self.recent_to = self.recent_to[:10]
        self.store["recent_to"] = self.recent_to
        save_store(self.store)

    # -------------------------
    # Actions
    # -------------------------
    def action_refresh(self) -> None:
        self._update_status_balance()
        if self.selected:
            self._invalidate_history_cache(self.selected.address)
            self._load_history_for_selected(force=True)

    def action_more_history(self) -> None:
        if not self.selected:
            self._set_status("No account selected.")
            return
        self.history_limit += 20
        self._invalidate_history_cache(self.selected.address)
        self._load_history_for_selected(force=True)

    def action_tx_details(self) -> None:
        if not self.history_items:
            self._set_status("No history items.")
            return
        if self.history_selected_index is None:
            self._set_status("Select a history row first.")
            return
        idx = self.history_selected_index
        if idx < 0 or idx >= len(self.history_items):
            self._set_status("Invalid selection.")
            return
        self.push_screen(TxDetailsScreen(self.rpc, self.history_items[idx]))

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

        self._update_rpc_label()
        self._update_net_badge()

        self._invalidate_history_cache()
        self.history_limit = 20
        self._update_history_title()

        if can_send and can_sim:
            self._set_status(f"✅ Network set to {choice}. RPC OK: {self.rpc}. Refreshing…")
        elif can_send and not can_sim:
            self._set_status(f"⚠️ Network set to {choice}. RPC can send but can't simulate: {self.rpc}. Refreshing…")
        else:
            self._set_status(f"⚠️ Network set to {choice}. RPC looks restricted: {self.rpc}. Refreshing…")
        if self.selected:
            self._update_status_balance()
            self._load_history_for_selected(force=True)

    def action_receive(self) -> None:
        if not self.selected:
            self._set_status("No account selected.")
            return
        self.push_screen(ReceiveScreen(self.selected.address))

    @work(exclusive=True)
    async def action_add_account(self) -> None:
        self._set_busy(True)
        try:
            name = await self.push_screen_wait(PromptScreen("Account name:"))
            if not name:
                self._set_status("Cancelled.")
                return

            self._set_status("Enter Tezos account address…")
            addr = await self.push_screen_wait(PromptScreen("Tezos account (tz1/tz2/tz3/tz4):"))
            if not addr:
                self._set_status("Cancelled: missing address.")
                return

            addr = addr.strip()
            if not is_tz_address(addr):
                self._set_status("Invalid account address. Must be tz1/tz2/tz3/tz4.")
                return

            secret = await self.push_screen_wait(PromptScreen("Secret key (edsk...) OPTIONAL (blank = watch-only):"))

            enc = None
            if secret:
                pw = await self.push_screen_wait(PromptScreen("Passphrase to encrypt key:", password=True))
                if not pw:
                    self._set_status("Cancelled: no passphrase.")
                    return
                enc = encrypt_secret(secret, pw)

            upsert_account(self.store, Account(name=name, address=addr, enc=enc))
            save_store(self.store)
            self._render_accounts()
            self._set_status("Account saved.")
        finally:
            self._set_busy(False)

    @work(exclusive=True)
    async def action_send(self) -> None:
        if not self.selected:
            self._set_status("No account selected.")
            return
        if self.selected.enc is None:
            self._set_status("Selected account is watch-only. Add a secret key to send.")
            return


        if self._send_in_progress:
            self._set_status("Send already in progress…")
            return

        to_addr = await self.push_screen_wait(DestinationPickerScreen(self.recent_to))
        if not to_addr:
            return

        to_addr = to_addr.strip()
        if not is_tezos_destination(to_addr):
            self._set_status("Invalid destination. Must be tz1/tz2/tz3/tz4 or KT1.")
            return

        amount_str = await self.push_screen_wait(PromptScreen("Amount (XTZ), e.g. 0.123:"))
        if not amount_str:
            return

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("amount must be > 0")
        except Exception:
            self._set_status("Invalid amount.")
            return

        pw = await self.push_screen_wait(PromptScreen("Passphrase to decrypt key:", password=True))
        if not pw:
            return

        try:
            secret = decrypt_secret(self.selected.enc, pw)
            key = key_from_encoded_secret(secret)
        except Exception as e:
            self._set_status(f"Decrypt key failed: {e}")
            return

        self._send_in_progress = True

        # Disable underlying buttons while the confirm modal is open.
        # This prevents accidental clicks/keypresses from re-triggering the send flow when the modal closes.
        self._set_busy(True)

        resp = await self.push_screen_wait(
            ConfirmSendScreen(self.rpc, key, self.selected.address, to_addr, amount)
        )
        if not resp or not resp.get("ok"):
            self._set_status("Cancelled.")
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
        self._ui(self._set_busy, True)
        self._ui(self._start_spinner, "Injecting to chain…")
        try:
            oph = send_xtz(
                self.rpc,
                key,
                to_addr,
                amount,
                fee_mutez=fee_mutez,
                gas_limit=gas_limit,
                storage_limit=storage_limit,
            )

            self._push_recent_to(to_addr)

            tzkt = tzkt_ui_base_from_rpc(self.rpc)
            self._ui(self._set_status, f"✅ Injected: {oph}  |  {tzkt}/{oph}")

            self._invalidate_history_cache(from_addr)

            # Poll history until the injected op shows up (indexers can lag).
            # Keep the spinner running until we either see the op hash in history
            # or we hit a short timeout.
            items: list[dict] = []
            found = False
            for _ in range(20):  # ~20s max
                try:
                    items = get_xtz_history(self.rpc, from_addr, limit=self.history_limit)
                except Exception:
                    items = []
                if any((it.get("hash") or "") == oph for it in (items or [])):
                    found = True
                    break
                time.sleep(1)

            if items:
                self.history_cache[(from_addr, self.history_limit)] = items
                self._ui(self._render_history, items)
                self._ui(self._update_status_balance)

            if found:
                baker = find_baker_for_operation(self.rpc, oph, max_depth=20)

                if items and baker:
                    # Attach baker to the matching history row
                    for it in items:
                        if (it.get('hash') or '') == oph:
                            it['baker'] = baker
                    self.history_cache[(from_addr, self.history_limit)] = items
                    self._ui(self._render_history, items)

                if baker:
                    self._ui(self._set_status, f"✅ Tx processed · Block baked by {baker} · {oph}")
                else:
                    self._ui(self._set_status, f"✅ Tx processed · {oph}")
            else:
                # Still injected, but not yet indexed; user can refresh later.
                self._ui(self._set_status, f"✅ Injected: {oph} (waiting for history/indexer…)")

            def _focus_hist():
                try:
                    self.query_one("#history", ListView).focus()
                except Exception:
                    pass

            self._ui(_focus_hist)

        except Exception as e:
            self._ui(self._set_status, f"Send failed: {e}")
        finally:
            self._ui(self._stop_spinner)
            self._ui(self._set_busy, False)
            self._ui(setattr, self, '_send_in_progress', False)

    # --- Button wiring ---
    @on(Button.Pressed, "#add")
    def on_add_pressed(self) -> None:
        self.action_add_account()

    @on(Button.Pressed, "#refresh")
    def on_refresh_pressed(self) -> None:
        self.action_refresh()

    @on(Button.Pressed, "#send")
    def on_send_pressed(self) -> None:
        self.action_send()

    @on(Button.Pressed, "#recv")
    def on_recv_pressed(self) -> None:
        self.action_receive()


if __name__ == "__main__":
    WalletApp().run()

