import json
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, TypedDict

from .crypto import EncryptedBlob
from .logger import log_error, log_info, log_debug

STORE_PATH_ENV = "SASSY_WALLET_STORE_PATH"
DATA_DIR_ENV = "SASSY_WALLET_DATA_DIR"
_STORE_IO_EXCEPTIONS = (OSError, PermissionError)
_STORE_WRITE_EXCEPTIONS = _STORE_IO_EXCEPTIONS + (TypeError, ValueError)
_PRIVATE_FILE_MODE = 0o600
_PRIVATE_DIR_MODE = 0o700

_LAST_MIGRATION: Optional[Dict[str, str]] = None


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except _STORE_IO_EXCEPTIONS as e:
        log_debug("Failed to chmod path", exception=str(e), path=str(path), mode=oct(mode))


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=_PRIVATE_DIR_MODE)
    _chmod_best_effort(path, _PRIVATE_DIR_MODE)


def ensure_private_file(path: Path) -> None:
    if path.exists():
        _chmod_best_effort(path, _PRIVATE_FILE_MODE)


def ensure_private_files_in_dir(path: Path, *, suffixes: tuple[str, ...] = ()) -> None:
    """
    Enforce private permissions on existing files inside a directory.

    If `suffixes` is provided, only files with matching suffixes are updated.
    """
    ensure_private_dir(path)
    for entry in path.iterdir():
        if not entry.is_file():
            continue
        if suffixes and entry.suffix not in suffixes:
            continue
        ensure_private_file(entry)


def write_private_text_atomic(path: Path, payload: str) -> None:
    ensure_private_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    tmp_path = Path(tmp_name)
    try:
        try:
            os.fchmod(fd, _PRIVATE_FILE_MODE)
        except (AttributeError, OSError, PermissionError):
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        ensure_private_file(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except _STORE_IO_EXCEPTIONS:
                pass


def write_private_json_atomic(
    path: Path,
    payload: Dict[str, Any],
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    text = json.dumps(payload, indent=indent, ensure_ascii=ensure_ascii)
    write_private_text_atomic(path, text)

def _default_store_path() -> Path:
    override = os.environ.get(STORE_PATH_ENV)
    if override:
        return Path(override).expanduser()
    data_dir = os.environ.get(DATA_DIR_ENV)
    if data_dir:
        return Path(data_dir).expanduser() / "wallet.json"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "sassy-wallet" / "wallet.json"


DEFAULT_PATH = _default_store_path()
LEGACY_PATH = Path("data/wallet.json")


def _has_path_override() -> bool:
    return bool(os.environ.get(STORE_PATH_ENV) or os.environ.get(DATA_DIR_ENV))


def get_store_path() -> Path:
    return _default_store_path()


def get_last_migration() -> Optional[Dict[str, str]]:
    return _LAST_MIGRATION


@dataclass
class Account:
    name: str
    address: str
    enc: Optional[EncryptedBlob]  # None => watch-only


class TxPrefs(TypedDict, total=False):
    """
    Preferencias de TX persistidas.
    - advanced: si el usuario dejó el panel Advanced abierto o no
    - fee_xtz: string (para no perder precisión ni pelear con Decimal en JSON)
    - gas_limit/storage_limit: string (vacío => None / autofill)
    """
    advanced: bool
    fee_xtz: str
    gas_limit: str
    storage_limit: str


def _default_store() -> Dict[str, Any]:
    # default: ghostnet (seguro) si no existe el archivo
    return {
        "rpc": "https://rpc.tzkt.io/ghostnet",
        "accounts": [],
        "recent_to": [],  # Legacy, kept for backwards compatibility
        "recent_to_by_wallet": {},  # New: per-wallet recent destinations
        "pending_ops": [],  # Persist pending operations across sessions
        "tx_prefs": {
            "advanced": False,
            "fee_xtz": "",
            "gas_limit": "",
            "storage_limit": "",
        },
    }


def load_store(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Carga el store desde JSON.
    - Si no existe, crea un store por defecto.
    - Si el JSON está corrupto/invalidado, lo respalda y crea uno nuevo
      para que la app no muera con JSONDecodeError.
    """
    if path is None:
        path = _default_store_path()
        default_used = True
    else:
        default_used = False

    requested_path = path
    if default_used and not _has_path_override() and not path.exists() and LEGACY_PATH.exists():
        path = LEGACY_PATH

    try:
        ensure_private_dir(path.parent)
    except _STORE_IO_EXCEPTIONS as e:
        log_error("Failed to create store directory", exception=e, path=str(path.parent))
        return _default_store()

    if not path.exists():
        return _default_store()
    ensure_private_file(path)

    try:
        raw = path.read_text("utf-8").strip()
    except _STORE_IO_EXCEPTIONS as e:
        log_error("Failed to read store file", exception=e, path=str(path))
        return _default_store()
    if not raw:
        return _default_store()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        backup = path.with_suffix(".json.bak")
        try:
            write_private_text_atomic(backup, raw)
        except _STORE_IO_EXCEPTIONS as e:
            log_error("Failed to write backup file for corrupted store", exception=e, backup_path=str(backup))
        data = _default_store()
        save_store(data, path=path)
        return data

    # Normalización mínima (retro compatible)
    defaults = _default_store()

    if "rpc" not in data or not isinstance(data.get("rpc"), str) or not data["rpc"].strip():
        data["rpc"] = defaults["rpc"]

    if "accounts" not in data or not isinstance(data["accounts"], list):
        data["accounts"] = []

    # Recents (legacy)
    if "recent_to" not in data or not isinstance(data.get("recent_to"), list):
        data["recent_to"] = []
    else:
        # limpiar entradas raras / vacías
        data["recent_to"] = [str(x).strip() for x in data["recent_to"] if str(x).strip()]

    # Recents by wallet (new structure)
    if "recent_to_by_wallet" not in data or not isinstance(data.get("recent_to_by_wallet"), dict):
        data["recent_to_by_wallet"] = {}

    # Pending ops
    if "pending_ops" not in data or not isinstance(data.get("pending_ops"), list):
        data["pending_ops"] = []

    # Tx prefs
    if "tx_prefs" not in data or not isinstance(data.get("tx_prefs"), dict):
        data["tx_prefs"] = defaults["tx_prefs"].copy()
    else:
        tp = data["tx_prefs"]
        if not isinstance(tp.get("advanced", False), bool):
            tp["advanced"] = False

        # guardamos como strings siempre
        for k in ("fee_xtz", "gas_limit", "storage_limit"):
            v = tp.get(k, "")
            if v is None:
                tp[k] = ""
            else:
                tp[k] = str(v).strip()

    if path != requested_path:
        try:
            save_store(data, path=requested_path)
            global _LAST_MIGRATION
            _LAST_MIGRATION = {"from": str(path), "to": str(requested_path)}
            log_info("Migrated legacy store to default path", from_path=str(path), to_path=str(requested_path))
        except _STORE_WRITE_EXCEPTIONS as e:
            log_error("Failed to migrate legacy store to default path", exception=e, path=str(requested_path))

    return data


def save_store(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    if path is None:
        path = _default_store_path()
    try:
        payload = json.dumps(data, indent=2, ensure_ascii=True)
        write_private_text_atomic(path, payload)
    except _STORE_WRITE_EXCEPTIONS as e:
        log_error("Failed to save store", exception=e, path=str(path))


def list_accounts(data: Dict[str, Any]) -> List[Account]:
    out: List[Account] = []
    for a in data.get("accounts", []):
        enc = a.get("enc")

        # tolerancia a errores / migraciones de clave
        if enc and isinstance(enc, dict):
            if "ct_b64" not in enc and "ctt_b64" in enc:
                enc["ct_b64"] = enc.pop("ctt_b64")
            required = ("salt_b64", "nonce_b64", "ct_b64")
            if not all(isinstance(enc.get(k), str) and enc.get(k).strip() for k in required):
                enc = None

        out.append(
            Account(
                name=a.get("name", "Unnamed"),
                address=a.get("address", ""),
                enc=EncryptedBlob(**enc) if enc else None,
            )
        )
    return out


def upsert_account(data: Dict[str, Any], acct: Account) -> None:
    accounts = data.setdefault("accounts", [])
    for i, a in enumerate(accounts):
        if a.get("address") == acct.address:
            accounts[i] = _to_dict(acct)
            return
    accounts.append(_to_dict(acct))


def get_tx_prefs(data: Dict[str, Any]) -> TxPrefs:
    tp = data.get("tx_prefs")
    if not isinstance(tp, dict):
        tp = _default_store()["tx_prefs"].copy()
        data["tx_prefs"] = tp
    # type narrowing
    return tp


def set_tx_prefs(
    data: Dict[str, Any],
    *,
    advanced: Optional[bool] = None,
    fee_xtz: Optional[str] = None,
    gas_limit: Optional[str] = None,
    storage_limit: Optional[str] = None,
) -> None:
    tp = get_tx_prefs(data)
    if advanced is not None:
        tp["advanced"] = bool(advanced)
    if fee_xtz is not None:
        tp["fee_xtz"] = str(fee_xtz).strip()
    if gas_limit is not None:
        tp["gas_limit"] = str(gas_limit).strip()
    if storage_limit is not None:
        tp["storage_limit"] = str(storage_limit).strip()


def _to_dict(acct: Account) -> Dict[str, Any]:
    d: Dict[str, Any] = {"name": acct.name, "address": acct.address}
    if acct.enc:
        d["enc"] = {
            "salt_b64": acct.enc.salt_b64,
            "nonce_b64": acct.enc.nonce_b64,
            "ct_b64": getattr(acct.enc, "ct_b64", None),
        }

        if not d["enc"]["ct_b64"] and hasattr(acct.enc, "ctt_b64"):
            d["enc"]["ct_b64"] = getattr(acct.enc, "ctt_b64")

        if not d["enc"]["ct_b64"]:
            d.pop("enc", None)

    return d
