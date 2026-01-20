from typing import Optional, Any, Dict
from decimal import Decimal
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time

from pytezos import pytezos
from pytezos.crypto.key import Key


def get_client(rpc: str, key: Optional[Key] = None):
    return pytezos.using(shell=rpc, key=key)


def get_balance_mutez(rpc: str, address: str) -> int:
    client = get_client(rpc)
    return int(client.shell.contracts[address].balance())


def mutez_to_xtz(m: int) -> Decimal:
    return Decimal(m) / Decimal(1_000_000)


def xtz_to_mutez(x: Decimal) -> int:
    return int((x * Decimal(1_000_000)).to_integral_value())


def key_from_encoded_secret(encoded: str) -> Key:
    return Key.from_encoded_key(encoded)


def _contains_unrevealed_key(err: Any) -> bool:
    try:
        s = str(err)
    except Exception:
        s = ""
    if "unrevealed_key" in s:
        return True

    try:
        r = repr(err)
    except Exception:
        r = ""
    return "unrevealed_key" in r


def _tzkt_base_from_rpc(rpc: str) -> str:
    rpc_l = (rpc or "").lower()
    if "ghostnet" in rpc_l:
        return "https://api.ghostnet.tzkt.io"
    return "https://api.tzkt.io"


def _urlopen_json_with_retries(req: urllib.request.Request, timeout: int = 15, retries: int = 3) -> Any:
    """
    Fetch JSON via urllib with a few retries to smooth out transient TLS/EOF issues.
    Returns parsed JSON (dict/list).
    """
    ctx = ssl.create_default_context()
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = resp.read().decode("utf-8")
            return json.loads(data)
        except (ssl.SSLError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_err = e
            if attempt >= retries:
                break
            # small backoff
            time.sleep(0.4 * attempt)
        except Exception as e:
            # non-network errors: don't spin
            raise
    raise last_err if last_err else RuntimeError("Failed to fetch JSON")


def get_xtz_history(rpc: str, address: str, limit: int = 20) -> list[dict]:
    base = _tzkt_base_from_rpc(rpc)
    endpoint = f"{base}/v1/operations/transactions"

    params = {
        "anyof.sender.target": address,
        "status": "applied",
        "limit": str(limit),
        "sort.desc": "level",
    }

    url = endpoint + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "tui-tezos-wallet/0.1"},
        method="GET",
    )
    items = _urlopen_json_with_retries(req, timeout=15, retries=3)
    out: list[dict] = []

    for it in items:
        sender = (it.get("sender") or {}).get("address")
        target = (it.get("target") or {}).get("address")
        amount_mutez = int(it.get("amount") or 0)

        if sender == address:
            direction = "OUT"
            counterparty = target or "?"
        elif target == address:
            direction = "IN"
            counterparty = sender or "?"
        else:
            direction = "?"
            counterparty = "?"

        out.append(
            {
                "ts": it.get("timestamp") or "",
                "direction": direction,
                "amount_xtz": mutez_to_xtz(amount_mutez),
                "counterparty": counterparty,
                "hash": it.get("hash") or "",
            }
        )

    return out


# ---------------------------------------------------------------------
# Fee/Gas estimation helpers (for UI confirm screen)
# ---------------------------------------------------------------------

def is_revealed(rpc: str, address: str) -> bool:
    """
    True si la cuenta tz* tiene manager_key revelada.
    """
    client = get_client(rpc)
    try:
        mk = client.shell.contracts[address].manager_key()
        if mk is None:
            return False
        if isinstance(mk, str):
            return bool(mk)
        if isinstance(mk, dict):
            return bool(mk.get("key"))
        return bool(mk)
    except Exception:
        # Conservador: si no podemos chequear, asumimos que NO está revelada
        return False


def _extract_limits_from_op(op) -> Dict[str, int]:
    """
    op: OperationGroup ya autofilled
    Retorna: fee_mutez, gas_limit, storage_limit
    """
    try:
        payload = op.json_payload()
        contents = []
        if isinstance(payload, list) and payload:
            contents = (payload[0] or {}).get("contents", []) or []
        elif isinstance(payload, dict):
            contents = payload.get("contents", []) or []

        c0 = contents[0] if contents else {}
        fee = int(c0.get("fee") or 0)
        gas = int(c0.get("gas_limit") or 0)
        storage = int(c0.get("storage_limit") or 0)
        return {"fee_mutez": fee, "gas_limit": gas, "storage_limit": storage}
    except Exception:
        return {"fee_mutez": 0, "gas_limit": 0, "storage_limit": 0}


def estimate_send_xtz(
    rpc: str,
    key: Key,
    to_addr: str,
    amount_xtz: Decimal,
) -> Dict[str, Any]:
    """
    Estima parámetros sugeridos para:
      - reveal (si aplica)
      - transaction

    Devuelve:
    {
      "from": "tz1...",
      "to": "...",
      "amount_xtz": Decimal(...),
      "reveal_needed": bool,
      "reveal": {"fee_mutez": int, "gas_limit": int, "storage_limit": int} | None,
      "tx": {"fee_mutez": int, "gas_limit": int, "storage_limit": int},
      "total_fee_mutez": int,
      "total_fee_xtz": Decimal
    }
    """
    client = get_client(rpc, key=key)
    from_addr = key.public_key_hash()

    reveal_needed = not is_revealed(rpc, from_addr)

    reveal_info = None
    if reveal_needed:
        try:
            rev_op = client.reveal().autofill()
            reveal_info = _extract_limits_from_op(rev_op)
        except Exception:
            reveal_info = {"fee_mutez": 0, "gas_limit": 0, "storage_limit": 0}

    try:
        tx_op = client.transaction(destination=to_addr, amount=amount_xtz).autofill()
        tx_info = _extract_limits_from_op(tx_op)
    except Exception:
        tx_info = {"fee_mutez": 0, "gas_limit": 0, "storage_limit": 0}

    # Some RPCs / pytezos versions may return 0s for fee/gas/storage on autofill.
    # That's still fine for sending (we use autofill at inject time), but for UI we
    # prefer sensible non-zero hints.
    if int(tx_info.get("fee_mutez") or 0) == 0 and int(tx_info.get("gas_limit") or 0) == 0:
        tx_info = {"fee_mutez": 1200, "gas_limit": 2000, "storage_limit": 0}
    if reveal_needed and reveal_info is not None:
        if int(reveal_info.get("fee_mutez") or 0) == 0 and int(reveal_info.get("gas_limit") or 0) == 0:
            reveal_info = {"fee_mutez": 1300, "gas_limit": 10000, "storage_limit": 0}

    # Fees
    reveal_fee_mutez = int((reveal_info or {}).get("fee_mutez", 0))
    tx_fee_mutez = int(tx_info.get("fee_mutez") or 0)
    total_fee_mutez = tx_fee_mutez + reveal_fee_mutez

    # Fee presets for UI.
    # Important: overrides apply ONLY to the transaction fee (not reveal), so keep reveal on autofill.
    # - economy: use autofill (no overrides)
    # - normal: use suggested tx fee
    # - priority: suggested tx fee + 50% padding
    priority_tx_fee_mutez = int((Decimal(tx_fee_mutez) * Decimal("1.5")).to_integral_value())
    fee_options = {
        "economy": {
            "label": "Economy (autofill)",
            "tx_fee_mutez": None,
            "total_fee_mutez": total_fee_mutez,
            "total_fee_xtz": mutez_to_xtz(total_fee_mutez),
        },
        "normal": {
            "label": "Normal (suggested)",
            "tx_fee_mutez": tx_fee_mutez,
            "total_fee_mutez": reveal_fee_mutez + tx_fee_mutez,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + tx_fee_mutez),
        },
        "priority": {
            "label": "Priority (+50%)",
            "tx_fee_mutez": priority_tx_fee_mutez,
            "total_fee_mutez": reveal_fee_mutez + priority_tx_fee_mutez,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + priority_tx_fee_mutez),
        },
    }

    return {
        "from": from_addr,
        "to": to_addr,
        "amount_xtz": amount_xtz,
        "reveal_needed": reveal_needed,
        "reveal": reveal_info if reveal_needed else None,
        "tx": tx_info,
      "reveal_fee_mutez": reveal_fee_mutez,
      "tx_fee_mutez": tx_fee_mutez,
        "total_fee_mutez": total_fee_mutez,
        "total_fee_xtz": mutez_to_xtz(total_fee_mutez),
      "fee_options": fee_options,
    }


# ---------------------------------------------------------------------
# Sending (supports optional overrides for TX)
# ---------------------------------------------------------------------


def _is_missing_helpers(err: Exception) -> bool:
    """Detect RPCs that don't expose simulation helpers (run_operation/simulate_operation)."""
    s = str(err)
    return (
        'helpers/scripts/run_operation' in s
        or 'helpers/scripts/simulate_operation' in s
        or 'Not found' in s and 'helpers/scripts' in s
    )


def send_xtz(
    rpc: str,
    key: Key,
    to_addr: str,
    amount_xtz: Decimal,
    fee_mutez: Optional[int] = None,
    gas_limit: Optional[int] = None,
    storage_limit: Optional[int] = None,
):
    """Envía XTZ.

    Objetivos:
    - Decimal (no float)
    - Reveal automático si la cuenta aún no está revelada
    - Normaliza resultado de inject() para devolver op hash (op...)
    - Overrides aplican SOLO a la TX (para no romper reveal con valores manuales)

    Compatibilidad RPC:
    - Algunos RPC (proxies / indexers) NO exponen helpers/scripts/run_operation.
      En ese caso intentamos un camino "no-simulación" (fill) con valores manuales,
      o devolvemos un error con instrucciones claras.
    """

    client = get_client(rpc, key=key)

    # Defaults razonables si el usuario eligió un preset y/o si el RPC no soporta simulación.
    # (Se aplican únicamente cuando no podemos usar autofill helpers.)
    DEFAULT_TX_FEE = 1200
    DEFAULT_TX_GAS = 2000
    DEFAULT_TX_STORAGE = 0

    DEFAULT_REVEAL_FEE = 1300
    DEFAULT_REVEAL_GAS = 10000
    DEFAULT_REVEAL_STORAGE = 0

    def _build_tx_op():
        """Intenta construir el op con fee/gas/storage en el contenido (si pytezos lo soporta)."""
        try:
            return client.transaction(
                destination=to_addr,
                amount=amount_xtz,
                fee=int(fee_mutez if fee_mutez is not None else 0),
                gas_limit=int(gas_limit if gas_limit is not None else 0),
                storage_limit=int(storage_limit if storage_limit is not None else 0),
            )
        except TypeError:
            # pytezos viejo: no acepta fee/gas/storage en el constructor
            return client.transaction(destination=to_addr, amount=amount_xtz)

    def _build_reveal_op():
        try:
            return client.reveal(
                fee=DEFAULT_REVEAL_FEE,
                gas_limit=DEFAULT_REVEAL_GAS,
                storage_limit=DEFAULT_REVEAL_STORAGE,
            )
        except TypeError:
            return client.reveal()

    def _inject(op, *, kind: str):
        """Autofill+sign+inject con fallback si el RPC no soporta helpers/scripts."""
        try:
            # Preferimos autofill (obtiene counter/branch + fees/limits por simulación)
            if fee_mutez is not None or gas_limit is not None or storage_limit is not None:
                op = op.autofill(
                    fee=int(fee_mutez) if fee_mutez is not None else None,
                    gas_limit=int(gas_limit) if gas_limit is not None else None,
                    storage_limit=int(storage_limit) if storage_limit is not None else None,
                )
            else:
                op = op.autofill()

        except Exception as e:
            # Fallback: RPC no expone helpers/scripts
            if _is_missing_helpers(e):
                # Intentamos un camino de "fill" (sin simulación) si existe.
                # Para que esto funcione, necesitamos fee/gas/storage ya seteados en el contenido.
                # Si el user no pasó overrides, ponemos defaults.
                if fee_mutez is None:
                    local_fee = DEFAULT_REVEAL_FEE if kind == 'reveal' else DEFAULT_TX_FEE
                else:
                    local_fee = int(fee_mutez)

                if gas_limit is None:
                    local_gas = DEFAULT_REVEAL_GAS if kind == 'reveal' else DEFAULT_TX_GAS
                else:
                    local_gas = int(gas_limit)

                if storage_limit is None:
                    local_storage = DEFAULT_REVEAL_STORAGE if kind == 'reveal' else DEFAULT_TX_STORAGE
                else:
                    local_storage = int(storage_limit)

                # Si el constructor no soportó fee/gas/storage, no tenemos forma segura de setearlo.
                # En ese caso, devolvemos un error claro para que el usuario cambie de RPC.
                payload_ok = True
                try:
                    payload = op.json_payload()
                    # chequeo naive: fee existe en contenido
                    contents = []
                    if isinstance(payload, list) and payload:
                        contents = (payload[0] or {}).get('contents', []) or []
                    elif isinstance(payload, dict):
                        contents = payload.get('contents', []) or []
                    c0 = contents[0] if contents else {}
                    has_fee_field = 'fee' in c0
                    # si fee está vacío/0, seguimos (vamos a intentar construir op con params)
                except Exception:
                    has_fee_field = False

                # Intentar reconstruir el op con params si podemos
                if kind == 'tx':
                    try:
                        op = client.transaction(
                            destination=to_addr,
                            amount=amount_xtz,
                            fee=local_fee,
                            gas_limit=local_gas,
                            storage_limit=local_storage,
                        )
                    except TypeError:
                        payload_ok = False
                else:
                    try:
                        op = client.reveal(
                            fee=local_fee,
                            gas_limit=local_gas,
                            storage_limit=local_storage,
                        )
                    except TypeError:
                        payload_ok = False

                if not payload_ok:
                    raise RuntimeError(
                        "Tu RPC no soporta helpers/scripts (run_operation/simulate_operation) "
                        "y esta versión de pytezos no permite setear fee/gas/storage sin autofill. "
                        "Solución: usa un RPC de nodo completo (Octez) que soporte helpers/scripts."
                    ) from e

                # fill (counter/branch) sin simulación
                if hasattr(op, 'fill'):
                    op = op.fill()
                else:
                    raise RuntimeError(
                        "Tu RPC no soporta helpers/scripts y pytezos no tiene op.fill() disponible. "
                        "Solución: cambia a un RPC de nodo completo (Octez)."
                    ) from e
            else:
                raise

        # Sign+inject
        res = op.sign().inject(_async=False)
        if isinstance(res, dict) and 'hash' in res:
            return res['hash']
        return res

    try:
        return _inject(_build_tx_op(), kind='tx')

    except Exception as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal SIEMPRE separado
        try:
            reveal_oph = _inject(_build_reveal_op(), kind='reveal')
        except Exception as rev_e:
            raise RuntimeError(f"Reveal failed: {rev_e}") from rev_e

        # Retry send
        try:
            return _inject(_build_tx_op(), kind='tx')
        except Exception as send_e:
            raise RuntimeError(f"Send failed after reveal ({reveal_oph}): {send_e}") from send_e

