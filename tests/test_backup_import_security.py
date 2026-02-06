from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import pytest

from sassy_wallet.ui import app as ui_app
from sassy_wallet.ui.app import ImportWizardScreen, WalletApp


_VALID_TZ1 = "tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb"
_VALID_TZ1_B = "tz1aSkwEot3L2kmUvcoxzjMomb9mvBNuzFK6"
_VALID_TZ1_C = "tz1burnburnburnburnburnburnburjAYjjX"
_VALID_KT1 = "KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton"


class _WizardDummy:
    def __init__(self) -> None:
        self.error = ""

    def _set_error(self, message: str) -> None:
        self.error = message


def test_load_backup_file_rejects_oversized_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ui_app.Config, "BACKUP_MAX_FILE_BYTES", 64)
    backup_path = tmp_path / "oversized.json"
    backup_path.write_text(json.dumps({"blob": "x" * 512}), encoding="utf-8")

    dummy = _WizardDummy()
    loaded = ImportWizardScreen._load_backup_file(cast(Any, dummy), backup_path)

    assert loaded is None
    assert "too large" in dummy.error.lower()


class _BackupImportDummy:
    _validate_backup_wallet_address = WalletApp._validate_backup_wallet_address
    _parse_backup_enc_blob = WalletApp._parse_backup_enc_blob
    _sanitize_backup_recent_destinations = WalletApp._sanitize_backup_recent_destinations
    _sanitize_backup_recent_map = WalletApp._sanitize_backup_recent_map

    def __init__(self) -> None:
        self.store: dict = {"accounts": []}
        self.accounts = []
        self.recent_to_by_wallet: dict = {}
        self.status_messages: list[str] = []
        self.status_styled_messages: list[tuple[str, str]] = []

    def _set_status(self, message: str) -> None:
        self.status_messages.append(message)

    def _set_status_styled(self, message: str, style: str, duration: float) -> None:
        self.status_styled_messages.append((message, style))

    def _set_status_styled_locked(self, message: str, style: str) -> None:
        self.status_styled_messages.append((message, style))

    def _render_accounts(self) -> None:
        return None

    def _select_account_by_address(self, _address: str) -> None:
        return None


def test_import_backup_payload_skips_malformed_entries_and_sanitizes_recents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _BackupImportDummy()

    def _fake_upsert(store: dict, account) -> None:
        store.setdefault("accounts", [])
        store["accounts"].append(
            {"name": account.name, "address": account.address, "enc": account.enc}
        )

    monkeypatch.setattr(ui_app, "upsert_account", _fake_upsert)
    monkeypatch.setattr(ui_app, "save_store", lambda _store: None)
    monkeypatch.setattr(ui_app.Config, "BACKUP_MAX_ACCOUNTS", 10)

    payload = {
        "backup_type": "multi_wallets_encrypted",
        "accounts": [
            {"name": "Wallet One", "address": _VALID_TZ1, "enc": None},
            "not-a-dict",
            {"name": 123, "address": _VALID_TZ1_B, "enc": None},
        ],
        "recent_to_by_wallet": {
            _VALID_TZ1: [_VALID_KT1, "not-an-address", _VALID_KT1],
            "bad-key": [_VALID_KT1],
        },
    }

    result = asyncio.run(WalletApp._import_from_backup_payload(cast(Any, dummy), payload))

    assert result is False
    assert len(dummy.store["accounts"]) == 1
    assert dummy.store["accounts"][0]["address"] == _VALID_TZ1
    assert dummy.recent_to_by_wallet[_VALID_TZ1] == [_VALID_KT1]
    assert any("Restored 1 wallet(s). Skipped 2." in msg for msg, _ in dummy.status_styled_messages)


def test_import_backup_payload_rejects_when_all_entries_are_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _BackupImportDummy()
    monkeypatch.setattr(ui_app, "upsert_account", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(ui_app, "save_store", lambda _store: None)

    payload = {
        "backup_type": "multi_wallets_encrypted",
        "accounts": ["broken-entry", {"name": "X", "address": "tz1bad", "enc": None}],
    }

    result = asyncio.run(WalletApp._import_from_backup_payload(cast(Any, dummy), payload))

    assert result is False
    assert any("no valid wallet entries" in msg.lower() for msg in dummy.status_messages)


def test_import_backup_payload_rejects_excessive_account_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _BackupImportDummy()
    monkeypatch.setattr(ui_app.Config, "BACKUP_MAX_ACCOUNTS", 2)

    payload = {
        "backup_type": "multi_wallets_encrypted",
        "accounts": [
            {"name": "A", "address": _VALID_TZ1, "enc": None},
            {"name": "B", "address": _VALID_TZ1_B, "enc": None},
            {"name": "C", "address": _VALID_TZ1_C, "enc": None},
        ],
    }

    result = asyncio.run(WalletApp._import_from_backup_payload(cast(Any, dummy), payload))

    assert result is False
    assert any("too many wallets" in msg.lower() for msg in dummy.status_messages)
