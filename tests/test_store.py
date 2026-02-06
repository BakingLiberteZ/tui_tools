"""Tests for store path behavior and migration."""

import json
import os

from sassy_wallet.core import store


def test_load_store_migrates_legacy(tmp_path, monkeypatch):
    default_path = tmp_path / "xdg" / "sassy-wallet" / "wallet.json"
    legacy_path = tmp_path / "data" / "wallet.json"

    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_data = {"rpc": "https://legacy.example", "accounts": []}
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")

    monkeypatch.delenv(store.STORE_PATH_ENV, raising=False)
    monkeypatch.delenv(store.DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(store, "LEGACY_PATH", legacy_path)
    monkeypatch.setattr(store, "_default_store_path", lambda: default_path)

    data = store.load_store()

    assert data["rpc"] == "https://legacy.example"
    assert default_path.exists()
    migrated = json.loads(default_path.read_text(encoding="utf-8"))
    assert migrated["rpc"] == "https://legacy.example"


def test_save_store_enforces_private_permissions(tmp_path):
    if os.name != "posix":
        return

    store_path = tmp_path / "secure-data" / "wallet.json"
    data = {"rpc": "https://rpc.tzkt.io/ghostnet", "accounts": []}
    store.save_store(data, path=store_path)

    file_mode = store_path.stat().st_mode & 0o777
    dir_mode = store_path.parent.stat().st_mode & 0o777

    assert file_mode == 0o600
    assert dir_mode == 0o700


def test_load_store_restricts_existing_file_permissions(tmp_path):
    if os.name != "posix":
        return

    store_path = tmp_path / "wallet.json"
    store_path.write_text(json.dumps({"rpc": "https://rpc.tzkt.io/mainnet", "accounts": []}), encoding="utf-8")
    os.chmod(store_path, 0o664)

    data = store.load_store(path=store_path)
    assert data["rpc"] == "https://rpc.tzkt.io/mainnet"

    file_mode = store_path.stat().st_mode & 0o777
    dir_mode = store_path.parent.stat().st_mode & 0o777

    assert file_mode == 0o600
    assert dir_mode == 0o700


def test_ensure_private_files_in_dir_hardens_existing_files(tmp_path):
    if os.name != "posix":
        return

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    f1 = backup_dir / "one.json"
    f2 = backup_dir / "two.txt"
    f1.write_text("{}", encoding="utf-8")
    f2.write_text("x", encoding="utf-8")
    os.chmod(f1, 0o664)
    os.chmod(f2, 0o664)

    store.ensure_private_files_in_dir(backup_dir, suffixes=(".json",))

    mode_json = f1.stat().st_mode & 0o777
    mode_txt = f2.stat().st_mode & 0o777
    dir_mode = backup_dir.stat().st_mode & 0o777
    assert mode_json == 0o600
    assert mode_txt == 0o664
    assert dir_mode == 0o700
