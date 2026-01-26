import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, TypedDict

from .crypto import EncryptedBlob
from .logger import log_error

DEFAULT_PATH = Path("data/wallet.json")


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


def load_store(path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    """
    Carga el store desde JSON.
    - Si no existe, crea un store por defecto.
    - Si el JSON está corrupto/invalidado, lo respalda y crea uno nuevo
      para que la app no muera con JSONDecodeError.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        return _default_store()

    raw = path.read_text("utf-8").strip()
    if not raw:
        return _default_store()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        backup = path.with_suffix(".json.bak")
        try:
            backup.write_text(raw, encoding="utf-8")
        except Exception as e:
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

    return data


def save_store(data: Dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


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
    return tp  # type: ignore[return-value]


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
