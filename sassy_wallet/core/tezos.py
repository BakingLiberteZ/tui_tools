from typing import Optional, Any, Dict, List
from decimal import Decimal
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time
import requests

from pytezos import pytezos
from pytezos.crypto.key import Key
from pytezos.crypto.encoding import base58_decode

from .logger import safe_log_exception, log_error


# Watermark for operation signing
OPERATION_WATERMARK = b"\x03"


def inject_signed_operation(rpc: str, signed_op_hex: str) -> str:
    """
    Inject a signed operation directly to the RPC.

    Args:
        rpc: RPC endpoint
        signed_op_hex: Hex-encoded signed operation (forged_bytes + signature)

    Returns:
        Operation hash
    """
    url = f"{rpc}/injection/operation?chain=main"
    data = json.dumps(signed_op_hex).encode("utf-8")  # Body: "deadbeef..." (JSON string)
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    log_error(f"[INJECTION DEBUG] URL: {url}")
    log_error(f"[INJECTION DEBUG] Body length: {len(data)} bytes")
    log_error(f"[INJECTION DEBUG] Body first 100 chars: {data[:100]}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode().strip().strip('"')
            log_error(f"[INJECTION DEBUG] Success! Op hash: {result}")
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        log_error(f"[INJECTION DEBUG] Failed: {e.code} - {error_body}")
        raise RuntimeError(f"Injection failed: {e.code} - {error_body}")


def sign_and_inject_from_rpc_forge(rpc: str, key: Key, rpc_forged_hex: str) -> str:
    """
    Sign RPC-forged bytes and inject the operation.

    This avoids forge mismatch issues between PyTezos and the RPC by using
    the RPC's forge as the source of truth.

    Args:
        rpc: RPC endpoint
        key: Private key for signing
        rpc_forged_hex: Hex-encoded forged operation from RPC

    Returns:
        Operation hash
    """
    # 1) Convert hex to bytes
    forged_bytes = bytes.fromhex(rpc_forged_hex)

    # 2) Add operation watermark (0x03) - REQUIRED for Tezos operations
    watermarked = OPERATION_WATERMARK + forged_bytes

    # 3) Sign (returns base58: "sig..." or raw bytes depending on PyTezos version)
    sig_result = key.sign(watermarked, generic=True)

    # DEBUG logging BEFORE processing
    log_error(f"[SIGNATURE DEBUG] sig_result type: {type(sig_result).__name__}")
    log_error(f"[SIGNATURE DEBUG] sig_result repr: {repr(sig_result)[:100]}...")
    log_error(f"[SIGNATURE DEBUG] sig_result is str: {isinstance(sig_result, str)}")
    log_error(f"[SIGNATURE DEBUG] sig_result is bytes: {isinstance(sig_result, bytes)}")

    # 4) Convert to raw bytes (must be exactly 64 bytes)
    # ONLY decode if it's explicitly a string, otherwise treat as bytes
    if isinstance(sig_result, str):
        # Base58 string like "sigXXX...", decode it
        log_error(f"[SIGNATURE DEBUG] Decoding as base58 string...")
        sig_bytes = base58_decode(sig_result)
    else:
        # Bytes or bytes-like object, use directly
        log_error(f"[SIGNATURE DEBUG] Using as raw bytes...")
        sig_bytes = bytes(sig_result) if not isinstance(sig_result, bytes) else sig_result

    log_error(f"[SIGNATURE DEBUG] sig_bytes length: {len(sig_bytes)} bytes")
    log_error(f"[SIGNATURE DEBUG] sig_bytes hex: {sig_bytes.hex()}")

    # CRITICAL CHECK: Must be exactly 64 bytes
    if len(sig_bytes) != 64:
        raise RuntimeError(f"Signature bytes length invalid: {len(sig_bytes)} (expected 64)")

    # 5) Combine: forged + signature bytes
    signed_op_hex = rpc_forged_hex + sig_bytes.hex()

    # DEBUG: Verify concatenation
    log_error(f"[SIGNATURE DEBUG] Forged part: {len(rpc_forged_hex)} chars")
    log_error(f"[SIGNATURE DEBUG] Signature part: {len(sig_bytes.hex())} chars (should be 128)")
    log_error(f"[SIGNATURE DEBUG] Total: {len(signed_op_hex)} chars (should be {len(rpc_forged_hex)} + 128)")
    log_error(f"[SIGNATURE DEBUG] First 80: {signed_op_hex[:80]}")
    log_error(f"[SIGNATURE DEBUG] Last 80: {signed_op_hex[-80:]}")

    # CRITICAL CHECK: Total length must be correct
    expected_length = len(rpc_forged_hex) + 128  # 64 bytes = 128 hex chars
    if len(signed_op_hex) != expected_length:
        raise RuntimeError(f"Signed op length {len(signed_op_hex)} != expected {expected_length}")

    # 6) Inject the hex
    return inject_signed_operation(rpc, signed_op_hex)


def get_client(rpc: str, key: Optional[Key] = None) -> Any:
    """Get PyTezos client instance. Returns pytezos client object."""
    return pytezos.using(shell=rpc, key=key)


def get_counter(rpc: str, address: str) -> int:
    """
    Get the current counter for an address directly from RPC.
    This is the counter value to use for the NEXT operation.
    """
    client = get_client(rpc)
    counter_str = client.shell.contracts[address].counter()
    # The counter() call returns the last used counter, so we need to increment by 1
    return int(counter_str) + 1


def check_pending_operations(rpc: str, address: str) -> Optional[dict]:
    """
    Check if there are pending operations for an address in the mempool.

    Returns:
        dict with 'has_pending', 'pending_count', 'operations' if pending ops found
        None if no pending operations
    """
    try:
        # Get pending operations from mempool
        client = get_client(rpc)

        # Try to get pending operations from the mempool
        # The mempool contains operations that have been submitted but not yet included in a block
        try:
            pending_ops = client.shell.mempool.pending_operations()
        except Exception:
            # Some RPCs don't expose mempool, return None
            return None

        if not pending_ops:
            return None

        # Look for operations from this address
        user_pending_ops = []

        # Check in 'applied' (waiting to be included)
        if isinstance(pending_ops, dict) and 'applied' in pending_ops:
            for op in pending_ops['applied']:
                try:
                    # Check if this operation is from our address
                    if isinstance(op, dict) and 'contents' in op:
                        for content in op['contents']:
                            if isinstance(content, dict):
                                source = content.get('source', '')
                                if source == address:
                                    user_pending_ops.append({
                                        'hash': op.get('hash', 'unknown'),
                                        'kind': content.get('kind', 'unknown'),
                                        'counter': content.get('counter', 'unknown'),
                                    })
                except Exception:
                    continue

        # Check in 'unprocessed' (waiting to be validated)
        if isinstance(pending_ops, dict) and 'unprocessed' in pending_ops:
            for op in pending_ops['unprocessed']:
                try:
                    if isinstance(op, dict) and 'contents' in op:
                        for content in op['contents']:
                            if isinstance(content, dict):
                                source = content.get('source', '')
                                if source == address:
                                    user_pending_ops.append({
                                        'hash': op.get('hash', 'unknown'),
                                        'kind': content.get('kind', 'unknown'),
                                        'counter': content.get('counter', 'unknown'),
                                        'status': 'unprocessed'
                                    })
                except Exception:
                    continue

        if user_pending_ops:
            return {
                'has_pending': True,
                'pending_count': len(user_pending_ops),
                'operations': user_pending_ops,
            }

        return None

    except Exception as e:
        log_error("Failed to check pending operations", exception=e)
        return None


def get_balance_mutez(rpc: str, address: str) -> int:
    client = get_client(rpc)
    return int(client.shell.contracts[address].balance())


@safe_log_exception(default_return=None, user_message="Failed to get delegation info")
def get_delegation_info(rpc: str, address: str) -> Optional[str]:
    """
    Get the baker address this account is delegated to.
    Returns None if not delegated.
    """
    base = _tzkt_base_from_rpc(rpc)
    url = f"{base}/v1/accounts/{address}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "sassy-wallet/1.3.0"},
        method="GET",
    )
    data = _urlopen_json_with_retries(req, timeout=15, retries=3)

    # Check if delegated
    delegate = data.get("delegate")
    if delegate and isinstance(delegate, dict):
        delegate_address = delegate.get("address")
        return delegate_address if delegate_address else None

    return None


@safe_log_exception(default_return=0, user_message="Failed to get staking balance")
def get_staking_balance(rpc: str, address: str) -> int:
    """
    Get the staking balance (staked amount) for this account in mutez.
    Returns 0 if not staking or if information is unavailable.
    """
    base = _tzkt_base_from_rpc(rpc)
    url = f"{base}/v1/accounts/{address}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "sassy-wallet/1.3.0"},
        method="GET",
    )
    data = _urlopen_json_with_retries(req, timeout=15, retries=3)

    # Get staked balance (if available)
    staked_balance = data.get("stakedBalance", 0)
    return int(staked_balance) if staked_balance else 0


@safe_log_exception(default_return=None, user_message="Failed to get baker info")
def get_baker_info(rpc: str, baker_address: str) -> Optional[dict]:
    """
    Get comprehensive information about a baker from TzKT API.

    Args:
        rpc: RPC endpoint
        baker_address: Baker's address (tz1/tz2/tz3/tz4)

    Returns:
        Dictionary with baker info:
        {
            'address': str,          # Full address
            'alias': Optional[str],  # Alias or Tezos Domain name
            'balance': int,          # Balance in mutez
        }
        Or None if information is unavailable
    """
    base = _tzkt_base_from_rpc(rpc)
    url = f"{base}/v1/accounts/{baker_address}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "sassy-wallet/1.3.0"},
        method="GET",
    )
    data = _urlopen_json_with_retries(req, timeout=15, retries=3)

    if data is None:
        return None

    # Extract relevant information
    balance = data.get("balance")
    if balance is None:
        return None

    # Get alias or domain name
    alias = data.get("alias")

    return {
        'address': baker_address,
        'alias': alias,
        'balance': int(balance),
    }


def get_baker_staking_balance(rpc: str, baker_address: str) -> Optional[int]:
    """
    Get the baker's own balance in mutez (balance in their wallet).
    This is used to determine the baker's size tier for commentary.
    Returns None if information is unavailable.

    Args:
        rpc: RPC endpoint
        baker_address: Baker's address (tz1/tz2/tz3/tz4)

    Returns:
        Baker's balance in mutez, or None if unavailable
    """
    baker_info = get_baker_info(rpc, baker_address)
    if baker_info:
        return baker_info['balance']
    return None


@safe_log_exception(default_return=[], user_message="Failed to get public bakers list")
def get_public_bakers(rpc: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get a list of public bakers (delegates) with aliases or Tezos Domains from TzKT API.
    Returns active bakers sorted by staked balance (largest first).

    Args:
        rpc: RPC endpoint
        limit: Maximum number of bakers to return (default: 50)

    Returns:
        List of dictionaries with baker information:
        [
            {
                'address': str,          # Full baker address
                'alias': str,            # Baker alias or Tezos Domain name
                'balance': int,          # Baker's balance in mutez
                'stakedBalance': int,    # Total staked balance in mutez
            },
            ...
        ]
        Empty list if information is unavailable.
    """
    base = _tzkt_base_from_rpc(rpc)

    # Get active delegates sorted by staked balance (descending)
    # API parameters confirmed with tzkt.io API testing:
    # - active=true (NOT active.eq=true)
    # - sort.desc=stakedBalance (NOT stakingBalance)
    # - limit=N
    params = {
        "active": "true",
        "sort.desc": "stakedBalance",
        "limit": str(limit * 2),  # Request more to filter those with aliases
    }

    url = f"{base}/v1/delegates?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "sassy-wallet/1.3.0"},
        method="GET",
    )
    data = _urlopen_json_with_retries(req, timeout=15, retries=3)

    if not isinstance(data, list):
        return []

    # Filter only bakers with aliases and extract relevant information
    bakers = []
    for baker in data:
        alias = baker.get("alias")
        # Only include bakers with aliases or Tezos Domains
        if alias:
            bakers.append({
                'address': baker.get("address", ""),
                'alias': alias,
                'balance': int(baker.get("balance", 0)),
                'stakedBalance': int(baker.get("stakedBalance", 0)),
            })

            # Stop when we have enough bakers with aliases
            if len(bakers) >= limit:
                break

    return bakers


def mutez_to_xtz(m: int) -> Decimal:
    return Decimal(m) / Decimal(1_000_000)


def xtz_to_mutez(x: Decimal) -> int:
    return int((x * Decimal(1_000_000)).to_integral_value())


def key_from_encoded_secret(encoded: str) -> Key:
    return Key.from_encoded_key(encoded)


def _contains_unrevealed_key(err: Any) -> bool:
    try:
        s = str(err)
    except Exception as e:
        log_error("Failed to convert error to string", exception=e)
        s = ""
    if "unrevealed_key" in s:
        return True

    try:
        r = repr(err)
    except Exception as e:
        log_error("Failed to get repr of error", exception=e)
        r = ""
    return "unrevealed_key" in r


def is_wallet_revealed(rpc: str, address: str) -> bool:
    """
    Check if a wallet's public key has been revealed on the blockchain.

    Returns:
        True if wallet is revealed (has made at least one operation)
        False if wallet is unrevealed (never signed a transaction)
    """
    try:
        client = get_client(rpc)
        # Get manager key - will be None if unrevealed
        manager_key = client.shell.contracts[address].manager_key()

        # If manager_key is None or empty, wallet is not revealed
        if manager_key is None or manager_key == {}:
            return False

        return True
    except Exception as e:
        # If we can't determine, assume it's revealed to avoid false warnings
        log_error(f"Could not check reveal status for {address}", exception=e)
        return True


def _tzkt_base_from_rpc(rpc: str) -> str:
    rpc_l = (rpc or "").lower()
    if "ghostnet" in rpc_l:
        return "https://api.ghostnet.tzkt.io"
    return "https://api.tzkt.io"


def _urlopen_json_with_retries(req: urllib.request.Request, timeout: int = 15, retries: int = 3) -> Dict[str, Any]:
    """
    Fetch JSON via urllib with a few retries to smooth out transient TLS/EOF issues.
    Returns parsed JSON (typically a dict).
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
            log_error(f"Network error on attempt {attempt}/{retries}", exception=e, url=req.full_url)
            if attempt >= retries:
                break
            # small backoff
            time.sleep(0.4 * attempt)
        except Exception as e:
            # non-network errors: don't spin
            log_error("Non-network error in URL fetch", exception=e, url=req.full_url)
            raise
    if last_err:
        log_error("All retry attempts exhausted", exception=last_err, url=req.full_url)
        raise last_err
    else:
        raise RuntimeError("Failed to fetch JSON")


def get_xtz_history(rpc: str, address: str, limit: int = 20) -> List[Dict[str, Any]]:
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
        headers={"User-Agent": "sassy-wallet/1.3.0"},
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

@safe_log_exception(default_return=False, user_message="Failed to check if account is revealed")
def is_revealed(rpc: str, address: str) -> bool:
    """
    True si la cuenta tz* tiene manager_key revelada.
    """
    # Defensive: if address is a Key object, extract the address string
    if hasattr(address, 'public_key_hash'):
        address = address.public_key_hash()

    client = get_client(rpc)
    mk = client.shell.contracts[address].manager_key()
    if mk is None:
        return False
    if isinstance(mk, str):
        return bool(mk)
    if isinstance(mk, dict):
        return bool(mk.get("key"))
    return bool(mk)


@safe_log_exception(
    default_return={"fee_mutez": 0, "gas_limit": 0, "storage_limit": 0},
    user_message="Failed to extract limits from operation"
)
def _extract_limits_from_op(op) -> Dict[str, int]:
    """
    op: OperationGroup ya autofilled
    Retorna: fee_mutez, gas_limit, storage_limit
    """
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


def estimate_send_xtz(
    rpc: str,
    key: Key,
    to_addr: str,
    amount_xtz: Decimal,
) -> Dict[str, Any]:  # Contains: from, to, amount_xtz, reveal_needed, reveal, tx, etc.
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
        except Exception as e:
            log_error("Failed to estimate reveal operation", exception=e, address=from_addr)
            reveal_info = {"fee_mutez": 0, "gas_limit": 0, "storage_limit": 0}

    try:
        tx_op = client.transaction(destination=to_addr, amount=amount_xtz).autofill()
        tx_info = _extract_limits_from_op(tx_op)
    except Exception as e:
        log_error("Failed to estimate transaction operation", exception=e, from_addr=from_addr, to_addr=to_addr)
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


def estimate_stake(rpc: str, from_addr: str, amount_xtz: Decimal) -> Dict[str, Any]:
    """
    Estimate parameters for staking operation.
    Uses conservative fixed values since autofill often underestimates for staking.

    Args:
        rpc: RPC endpoint
        from_addr: Source address (tz1/tz2/tz3/tz4)
        amount_xtz: Amount to stake in XTZ

    Returns dict with same structure as estimate_send_xtz for UI compatibility.
    """
    reveal_needed = not is_revealed(rpc, from_addr)

    # Reveal defaults (if needed)
    reveal_fee_mutez = 1300 if reveal_needed else 0
    reveal_info = {"fee_mutez": 1300, "gas_limit": 10000, "storage_limit": 0} if reveal_needed else None

    # Staking defaults - conservative values that work
    # Economy: moderate values
    # Normal: safe values (DEFAULT)
    # Priority: extra safe with padding
    economy_fee = 6000   # 0.006 XTZ
    economy_gas = 25000

    normal_fee = 8000    # 0.008 XTZ (our current default)
    normal_gas = 30000

    priority_fee = 12000  # 0.012 XTZ
    priority_gas = 35000

    tx_info = {"fee_mutez": normal_fee, "gas_limit": normal_gas, "storage_limit": 0}

    # Fee options for UI
    fee_options = {
        "economy": {
            "label": "Economy",
            "tx_fee_mutez": economy_fee,
            "gas_limit": economy_gas,
            "total_fee_mutez": reveal_fee_mutez + economy_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + economy_fee),
        },
        "normal": {
            "label": "Normal (recommended)",
            "tx_fee_mutez": normal_fee,
            "gas_limit": normal_gas,
            "total_fee_mutez": reveal_fee_mutez + normal_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + normal_fee),
        },
        "priority": {
            "label": "Priority (extra safe)",
            "tx_fee_mutez": priority_fee,
            "gas_limit": priority_gas,
            "total_fee_mutez": reveal_fee_mutez + priority_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + priority_fee),
        },
    }

    return {
        "from": from_addr,
        "to": from_addr,  # Staking is to yourself
        "amount_xtz": amount_xtz,
        "reveal_needed": reveal_needed,
        "reveal": reveal_info,
        "tx": tx_info,
        "reveal_fee_mutez": reveal_fee_mutez,
        "tx_fee_mutez": normal_fee,
        "total_fee_mutez": reveal_fee_mutez + normal_fee,
        "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + normal_fee),
        "fee_options": fee_options,
    }


def estimate_delegation(rpc: str, from_addr: str, baker_address: str) -> Dict[str, Any]:
    """
    Estimate parameters for delegation operation.
    Uses conservative fixed values since delegation operations need moderate gas.

    Args:
        rpc: RPC endpoint
        from_addr: Source address (tz1/tz2/tz3/tz4)
        baker_address: Baker's address

    Returns dict with same structure as estimate_send_xtz for UI compatibility.
    """
    reveal_needed = not is_revealed(rpc, from_addr)

    # Reveal defaults (if needed)
    reveal_fee_mutez = 1300 if reveal_needed else 0
    reveal_info = {"fee_mutez": 1300, "gas_limit": 10000, "storage_limit": 0} if reveal_needed else None

    # Delegation defaults - conservative values that work
    # Delegation typically needs less gas than staking
    # Economy: moderate values
    # Normal: safe values (DEFAULT)
    # Priority: extra safe with padding
    economy_fee = 3000   # 0.003 XTZ
    economy_gas = 15000

    normal_fee = 5000    # 0.005 XTZ (DEFAULT)
    normal_gas = 20000

    priority_fee = 8000  # 0.008 XTZ
    priority_gas = 25000

    tx_info = {"fee_mutez": normal_fee, "gas_limit": normal_gas, "storage_limit": 0}

    # Fee options for UI
    fee_options = {
        "economy": {
            "label": "Economy",
            "tx_fee_mutez": economy_fee,
            "gas_limit": economy_gas,
            "total_fee_mutez": reveal_fee_mutez + economy_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + economy_fee),
        },
        "normal": {
            "label": "Normal (recommended)",
            "tx_fee_mutez": normal_fee,
            "gas_limit": normal_gas,
            "total_fee_mutez": reveal_fee_mutez + normal_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + normal_fee),
        },
        "priority": {
            "label": "Priority (extra safe)",
            "tx_fee_mutez": priority_fee,
            "gas_limit": priority_gas,
            "total_fee_mutez": reveal_fee_mutez + priority_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + priority_fee),
        },
    }

    return {
        "from": from_addr,
        "to": baker_address,  # Delegating to baker
        "baker": baker_address,
        "reveal_needed": reveal_needed,
        "reveal": reveal_info,
        "tx": tx_info,
        "reveal_fee_mutez": reveal_fee_mutez,
        "tx_fee_mutez": normal_fee,
        "total_fee_mutez": reveal_fee_mutez + normal_fee,
        "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + normal_fee),
        "fee_options": fee_options,
    }


def estimate_unstake(rpc: str, from_addr: str, amount_xtz: Decimal) -> Dict[str, Any]:
    """
    Estimate parameters for unstaking operation.
    Uses conservative fixed values since autofill often underestimates for unstaking.

    Args:
        rpc: RPC endpoint
        from_addr: Source address (tz1/tz2/tz3/tz4)
        amount_xtz: Amount to unstake in XTZ

    Returns dict with same structure as estimate_send_xtz for UI compatibility.
    """
    reveal_needed = not is_revealed(rpc, from_addr)

    # Reveal defaults (if needed)
    reveal_fee_mutez = 1300 if reveal_needed else 0
    reveal_info = {"fee_mutez": 1300, "gas_limit": 10000, "storage_limit": 0} if reveal_needed else None

    # Unstaking defaults - conservative values similar to staking
    # Economy: moderate values
    # Normal: safe values (DEFAULT)
    # Priority: extra safe with padding
    economy_fee = 6000   # 0.006 XTZ
    economy_gas = 25000

    normal_fee = 8000    # 0.008 XTZ (DEFAULT)
    normal_gas = 30000

    priority_fee = 12000  # 0.012 XTZ
    priority_gas = 35000

    tx_info = {"fee_mutez": normal_fee, "gas_limit": normal_gas, "storage_limit": 0}

    # Fee options for UI
    fee_options = {
        "economy": {
            "label": "Economy",
            "tx_fee_mutez": economy_fee,
            "gas_limit": economy_gas,
            "total_fee_mutez": reveal_fee_mutez + economy_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + economy_fee),
        },
        "normal": {
            "label": "Normal (recommended)",
            "tx_fee_mutez": normal_fee,
            "gas_limit": normal_gas,
            "total_fee_mutez": reveal_fee_mutez + normal_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + normal_fee),
        },
        "priority": {
            "label": "Priority (extra safe)",
            "tx_fee_mutez": priority_fee,
            "gas_limit": priority_gas,
            "total_fee_mutez": reveal_fee_mutez + priority_fee,
            "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + priority_fee),
        },
    }

    return {
        "from": from_addr,
        "to": from_addr,  # Unstaking is from yourself
        "amount_xtz": amount_xtz,
        "reveal_needed": reveal_needed,
        "reveal": reveal_info,
        "tx": tx_info,
        "reveal_fee_mutez": reveal_fee_mutez,
        "tx_fee_mutez": normal_fee,
        "total_fee_mutez": reveal_fee_mutez + normal_fee,
        "total_fee_xtz": mutez_to_xtz(reveal_fee_mutez + normal_fee),
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


def delegate_to_baker(rpc: str, key: Key, baker_address: str, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> str:
    """
    Delegate to a baker.

    Args:
        rpc: RPC endpoint
        key: Account private key
        baker_address: Baker's address (tz1/tz2/tz3/tz4)
        fee_mutez: Optional transaction fee in mutez
        gas_limit: Optional gas limit
        storage_limit: Optional storage limit

    Returns:
        Operation hash (op...)
    """
    # Get source address from key
    source_address = key.public_key_hash()

    # Check if wallet is revealed (has made at least one operation)
    if not is_wallet_revealed(rpc, source_address):
        log_error(f"⚠️ Wallet {source_address[:10]}... is not revealed. Will attempt reveal operation first.")
        # Note: We don't raise here - we let the normal flow handle the reveal
        # This is just a proactive warning logged for user awareness

    # Check for pending operations BEFORE attempting
    pending_info = check_pending_operations(rpc, source_address)
    if pending_info and pending_info.get('has_pending'):
        pending_count = pending_info.get('pending_count', 0)
        raise RuntimeError(
            f"Cannot delegate: {pending_count} pending operation(s) detected for this wallet. "
            f"Please wait 1-2 minutes for them to confirm, then try again."
        )

    def _is_counter_error(e: Exception) -> bool:
        """Check if error is related to counter mismatch."""
        error_str = str(e).lower()
        return "counter" in error_str and ("not yet reached" in error_str or "already used" in error_str)

    def _inject_with_retry(max_retries: int = 3):
        """Build, autofill, sign, and inject with counter error retry logic."""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # On retry attempts, wait for blockchain to settle
                if attempt > 0:
                    settling_time = 3.0  # Wait for blockchain to process previous attempt
                    log_error(f"Waiting {settling_time}s for blockchain to settle before retry {attempt + 1}")
                    time.sleep(settling_time)

                # Create completely fresh client with NO shared state
                # IMPORTANT: using() creates a NEW instance each time
                fresh_client = pytezos.using(shell=rpc, key=key)

                # Build delegation operation (counter=None means autofill will handle it)
                op = fresh_client.delegation(baker_address)

                # Use custom fees if provided, otherwise autofill
                if fee_mutez is not None or gas_limit is not None or storage_limit is not None:
                    # Use fill() with custom parameters
                    fill_params = {}
                    if fee_mutez is not None:
                        fill_params['fee'] = fee_mutez
                    if gas_limit is not None:
                        fill_params['gas_limit'] = gas_limit
                    if storage_limit is not None:
                        fill_params['storage_limit'] = storage_limit
                    op = op.fill(**fill_params)
                else:
                    # autofill() automatically fetches: counter, gas, storage, fees
                    # It queries the blockchain directly for current state
                    op = op.autofill()

                # Sign and inject - trust autofill() to have set everything correctly
                op = op.sign()
                result = op.inject()

                # Normalize result
                if isinstance(result, dict):
                    return result.get("hash", str(result))
                return str(result)

            except Exception as e:
                last_error = e
                # Check if it's a counter error and we have retries left
                if _is_counter_error(e) and attempt < max_retries:
                    # Conservative backoff for counter synchronization
                    wait_time = 5.0 * (attempt + 1)  # 5s, 10s, 15s
                    log_error(f"Counter error on attempt {attempt + 1}, waiting {wait_time}s before retry", exception=e)
                    time.sleep(wait_time)
                    continue
                else:
                    # Not a counter error or out of retries
                    raise last_error

    try:
        return _inject_with_retry()
    except Exception as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal first (also with retry logic)
        log_error("Wallet not revealed. Attempting reveal operation first...")

        def _inject_reveal_with_retry(max_retries: int = 3):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    # Wait before retry
                    if attempt > 0:
                        settling_time = 3.0
                        log_error(f"Waiting {settling_time}s before reveal retry {attempt + 1}")
                        time.sleep(settling_time)

                    # Create fresh client with NO shared state
                    fresh_client = pytezos.using(shell=rpc, key=key)

                    # Build reveal operation
                    op = fresh_client.reveal()

                    # autofill() handles counter, gas, storage, fees
                    op = op.autofill()

                    # Sign and inject
                    op = op.sign()
                    result = op.inject()

                    if isinstance(result, dict):
                        return result.get("hash", str(result))
                    return str(result)
                except Exception as e:
                    last_error = e
                    if _is_counter_error(e) and attempt < max_retries:
                        wait_time = 5.0 * (attempt + 1)
                        log_error(f"Counter error on reveal attempt {attempt + 1}, waiting {wait_time}s", exception=e)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise last_error

        try:
            reveal_oph = _inject_reveal_with_retry()
        except Exception as rev_e:
            raise RuntimeError(
                f"Failed to reveal wallet public key. "
                f"This wallet has never been used before and needs to reveal its public key first. "
                f"Error: {rev_e}"
            ) from rev_e

        # Wait longer for reveal to propagate through the network
        log_error(f"Reveal successful ({reveal_oph}), waiting 8s for network propagation")
        time.sleep(8)

        # Retry delegation with fresh client after reveal
        log_error("Reveal complete. Retrying delegation...")
        try:
            return _inject_with_retry()
        except Exception as del_e:
            raise RuntimeError(
                f"Delegation failed after successful reveal (op: {reveal_oph}). "
                f"This may be due to network delays. Please wait 1-2 minutes and try again. "
                f"Error: {del_e}"
            ) from del_e


def stake_xtz(rpc: str, key: Key, amount_xtz: Decimal, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> str:
    """
    Stake XTZ with the current baker.
    Account must already be delegated.

    Args:
        rpc: RPC endpoint
        key: Account private key
        amount_xtz: Amount to stake in XTZ
        fee_mutez: Optional transaction fee in mutez (defaults to 8000)
        gas_limit: Optional gas limit (defaults to 30000)
        storage_limit: Optional storage limit (defaults to 0)

    Returns:
        Operation hash (op...)
    """
    # Get source address from key
    source_address = key.public_key_hash()

    # Check for pending operations BEFORE attempting
    pending_info = check_pending_operations(rpc, source_address)
    if pending_info and pending_info.get('has_pending'):
        pending_count = pending_info.get('pending_count', 0)
        raise RuntimeError(
            f"Cannot stake: {pending_count} pending operation(s) detected for this wallet. "
            f"Please wait 1-2 minutes for them to confirm, then try again."
        )

    # Check if wallet is revealed (has made at least one operation)
    if not is_wallet_revealed(rpc, source_address):
        log_error(f"⚠️ Wallet {source_address[:10]}... is not revealed. Will attempt reveal operation first.")
        # Note: We don't raise here - we let the normal flow handle the reveal

    def _is_counter_error(e: Exception) -> bool:
        """Check if error is related to counter mismatch."""
        error_str = str(e).lower()
        return "counter" in error_str and ("not yet reached" in error_str or "already used" in error_str)

    # Convert XTZ to mutez for transaction amount
    amount_mutez = xtz_to_mutez(amount_xtz)

    # Staking defaults - MUCH higher than normal transactions
    # Use provided values or defaults
    DEFAULT_STAKE_FEE = fee_mutez if fee_mutez is not None else 8000       # ~0.008 XTZ (higher for safety)
    DEFAULT_STAKE_GAS = gas_limit if gas_limit is not None else 30000      # Conservative: 30k gas for staking
    DEFAULT_STAKE_STORAGE = storage_limit if storage_limit is not None else 0  # Staking doesn't need storage

    def _inject_with_retry(max_retries: int = 3):
        """Build, autofill, sign, and inject with counter error retry logic."""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # On retry attempts, wait for blockchain to settle
                if attempt > 0:
                    settling_time = 3.0
                    log_error(f"Waiting {settling_time}s for blockchain to settle before retry {attempt + 1}")
                    time.sleep(settling_time)

                # Read counter from RPC (FRESH on each retry)
                try:
                    rpc_counter = get_counter(rpc, source_address) - 1  # get_counter already adds +1
                    log_error(f"[Attempt {attempt + 1}] RPC counter for {source_address[:10]}: {rpc_counter}")
                    counter_to_use = rpc_counter + 1
                    log_error(f"[Attempt {attempt + 1}] Will use counter: {counter_to_use}")
                except Exception as counter_err:
                    log_error(f"Failed to read counter from RPC", exception=counter_err)
                    raise

                # Check mempool for pending ops
                try:
                    pending_info = check_pending_operations(rpc, source_address)
                    if pending_info and pending_info.get('has_pending'):
                        log_error(f"⚠️ WARNING: {pending_info.get('pending_count', 0)} pending ops in mempool")
                except Exception:
                    pass

                # Create completely fresh client with NO shared state
                client = get_client(rpc, key=key)

                # ============================================================
                # PRUEBA 0: Verificar que key corresponde al source
                # ============================================================
                key_pkh = key.public_key_hash()
                log_error(f"[DEBUG] source_address: {source_address}")
                log_error(f"[DEBUG] key.public_key_hash(): {key_pkh}")
                if source_address != key_pkh:
                    raise RuntimeError(f"KEY MISMATCH! source={source_address} but key.pkh={key_pkh}")
                log_error(f"[DEBUG] ✅ Key matches source address")

                # Get branch from head block
                try:
                    branch = client.shell.head.hash()
                    log_error(f"[Attempt {attempt + 1}] Got branch: {branch}")
                except Exception as branch_err:
                    log_error(f"Failed to get branch", exception=branch_err)
                    raise

                # Build stake operation payload manually for RPC forge
                # Staking is a pseudo-operation: a transaction to self with 'stake' entrypoint
                log_error(f"[Attempt {attempt + 1}] Building stake op: {amount_xtz} XTZ")

                # Construct operation contents
                op_contents = {
                    'kind': 'transaction',  # Pseudo-operation via transaction
                    'source': source_address,
                    'destination': source_address,  # Self-transfer
                    'fee': str(DEFAULT_STAKE_FEE),
                    'counter': str(counter_to_use),
                    'gas_limit': str(DEFAULT_STAKE_GAS),
                    'storage_limit': str(DEFAULT_STAKE_STORAGE),
                    'amount': str(amount_mutez),
                    'parameters': {
                        'entrypoint': 'stake',
                        'value': {'prim': 'Unit'}
                    }
                }

                log_error(f"[Attempt {attempt + 1}] Operation contents:")
                log_error(f"  - kind: stake")
                log_error(f"  - counter: {counter_to_use}")
                log_error(f"  - gas_limit: {DEFAULT_STAKE_GAS}")
                log_error(f"  - storage_limit: {DEFAULT_STAKE_STORAGE}")
                log_error(f"  - fee: {DEFAULT_STAKE_FEE} mutez")
                log_error(f"  - amount: {amount_mutez} mutez")

                # Prepare payload for RPC forge
                forge_payload = {
                    'branch': branch,
                    'contents': [op_contents]
                }

                # Get RPC forge
                log_error(f"[Attempt {attempt + 1}] Requesting forge from RPC...")
                try:
                    forge_url = f"{rpc}/chains/main/blocks/head/helpers/forge/operations"
                    forge_response = requests.post(
                        forge_url,
                        json=forge_payload,
                        headers={'content-type': 'application/json'},
                        timeout=30
                    )

                    if forge_response.status_code != 200:
                        raise RuntimeError(f"RPC forge failed: {forge_response.status_code} - {forge_response.text}")

                    rpc_forged_hex = forge_response.text.strip().strip('"')
                    log_error(f"[Attempt {attempt + 1}] RPC forged bytes: {rpc_forged_hex}")

                except Exception as forge_err:
                    log_error(f"RPC forge request failed", exception=forge_err)
                    raise RuntimeError(f"Failed to forge operation via RPC: {forge_err}")

                # Sign and inject using RPC forge
                log_error(f"[Attempt {attempt + 1}] Signing RPC-forged bytes...")
                result = sign_and_inject_from_rpc_forge(rpc, key, rpc_forged_hex)
                log_error(f"[Attempt {attempt + 1}] ✅ Inject successful!")

                if isinstance(result, dict):
                    return result.get("hash", str(result))
                return str(result)

            except Exception as e:
                last_error = e
                if _is_counter_error(e) and attempt < max_retries:
                    # Conservative backoff for counter synchronization
                    wait_time = 5.0 * (attempt + 1)  # 5s, 10s, 15s
                    log_error(f"Counter error on stake attempt {attempt + 1}, waiting {wait_time}s", exception=e)
                    time.sleep(wait_time)
                    continue
                else:
                    raise last_error

    try:
        return _inject_with_retry()
    except Exception as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal first
        log_error("Wallet not revealed. Attempting reveal operation first...")

        def _inject_reveal_with_retry(max_retries: int = 3):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        settling_time = 3.0
                        log_error(f"Waiting {settling_time}s before reveal retry {attempt + 1}")
                        time.sleep(settling_time)

                    fresh_client = pytezos.using(shell=rpc, key=key)
                    op = fresh_client.reveal()
                    op = op.autofill()
                    op = op.sign()
                    result = op.inject()

                    if isinstance(result, dict):
                        return result.get("hash", str(result))
                    return str(result)
                except Exception as e:
                    last_error = e
                    if _is_counter_error(e) and attempt < max_retries:
                        wait_time = 5.0 * (attempt + 1)
                        log_error(f"Counter error on reveal attempt {attempt + 1}, waiting {wait_time}s", exception=e)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise last_error

        try:
            reveal_oph = _inject_reveal_with_retry()
        except Exception as rev_e:
            raise RuntimeError(
                f"Failed to reveal wallet public key. "
                f"This wallet has never been used before and needs to reveal its public key first. "
                f"Error: {rev_e}"
            ) from rev_e

        log_error(f"Reveal successful ({reveal_oph}), waiting 8s for network propagation")
        time.sleep(8)

        log_error("Reveal complete. Retrying stake...")
        try:
            return _inject_with_retry()
        except Exception as stake_e:
            raise RuntimeError(
                f"Stake failed after successful reveal (op: {reveal_oph}). "
                f"This may be due to network delays. Please wait 1-2 minutes and try again. "
                f"Error: {stake_e}"
            ) from stake_e


def unstake_xtz(rpc: str, key: Key, amount_xtz: Decimal, fee_mutez: Optional[int] = None, gas_limit: Optional[int] = None, storage_limit: Optional[int] = None) -> str:
    """
    Unstake XTZ from the current baker.
    Account must be staking.

    Args:
        rpc: RPC endpoint
        key: Account private key
        amount_xtz: Amount to unstake in XTZ
        fee_mutez: Optional transaction fee in mutez (defaults to 8000)
        gas_limit: Optional gas limit (defaults to 30000)
        storage_limit: Optional storage limit (defaults to 0)

    Returns:
        Operation hash (op...)
    """
    # Get source address from key
    source_address = key.public_key_hash()

    # Check for pending operations BEFORE attempting
    pending_info = check_pending_operations(rpc, source_address)
    if pending_info and pending_info.get('has_pending'):
        pending_count = pending_info.get('pending_count', 0)
        raise RuntimeError(
            f"Cannot unstake: {pending_count} pending operation(s) detected for this wallet. "
            f"Please wait 1-2 minutes for them to confirm, then try again."
        )

    # Check if wallet is revealed (has made at least one operation)
    if not is_wallet_revealed(rpc, source_address):
        log_error(f"⚠️ Wallet {source_address[:10]}... is not revealed. Will attempt reveal operation first.")
        # Note: We don't raise here - we let the normal flow handle the reveal

    # Convert XTZ to mutez for transaction amount
    amount_mutez = xtz_to_mutez(amount_xtz)

    # Unstaking defaults - same as staking
    # Use provided values or defaults
    DEFAULT_UNSTAKE_FEE = fee_mutez if fee_mutez is not None else 8000       # ~0.008 XTZ (higher for safety)
    DEFAULT_UNSTAKE_GAS = gas_limit if gas_limit is not None else 30000      # Conservative: 30k gas for unstaking
    DEFAULT_UNSTAKE_STORAGE = storage_limit if storage_limit is not None else 0  # Unstaking doesn't need storage

    def _is_counter_error(e: Exception) -> bool:
        """Check if error is related to counter mismatch."""
        error_str = str(e).lower()
        return "counter" in error_str and ("not yet reached" in error_str or "already used" in error_str)

    def _inject_with_retry(max_retries: int = 3):
        """Build, autofill, sign, and inject with counter error retry logic."""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # On retry attempts, wait for blockchain to settle
                if attempt > 0:
                    settling_time = 3.0
                    log_error(f"Waiting {settling_time}s for blockchain to settle before retry {attempt + 1}")
                    time.sleep(settling_time)

                # Read counter from RPC (FRESH on each retry)
                try:
                    rpc_counter = get_counter(rpc, source_address) - 1  # get_counter already adds +1
                    log_error(f"[Attempt {attempt + 1}] RPC counter for {source_address[:10]}: {rpc_counter}")
                    counter_to_use = rpc_counter + 1
                    log_error(f"[Attempt {attempt + 1}] Will use counter: {counter_to_use}")
                except Exception as counter_err:
                    log_error(f"Failed to read counter from RPC", exception=counter_err)
                    raise

                # Check mempool for pending ops
                try:
                    pending_info = check_pending_operations(rpc, source_address)
                    if pending_info and pending_info.get('has_pending'):
                        log_error(f"⚠️ WARNING: {pending_info.get('pending_count', 0)} pending ops in mempool")
                except Exception:
                    pass

                # Create completely fresh client with NO shared state
                client = get_client(rpc, key=key)

                # Get branch from head block
                try:
                    branch = client.shell.head.hash()
                    log_error(f"[Attempt {attempt + 1}] Got branch: {branch}")
                except Exception as branch_err:
                    log_error(f"Failed to get branch", exception=branch_err)
                    raise

                # Build unstake operation payload manually for RPC forge
                # Unstaking is a pseudo-operation: a transaction to self with 'unstake' entrypoint
                log_error(f"[Attempt {attempt + 1}] Building unstake op: {amount_xtz} XTZ")

                # Construct operation contents
                op_contents = {
                    'kind': 'transaction',  # Pseudo-operation via transaction
                    'source': source_address,
                    'destination': source_address,  # Self-transfer
                    'fee': str(DEFAULT_UNSTAKE_FEE),
                    'counter': str(counter_to_use),
                    'gas_limit': str(DEFAULT_UNSTAKE_GAS),
                    'storage_limit': str(DEFAULT_UNSTAKE_STORAGE),
                    'amount': str(amount_mutez),
                    'parameters': {
                        'entrypoint': 'unstake',
                        'value': {'prim': 'Unit'}
                    }
                }

                log_error(f"[Attempt {attempt + 1}] Operation contents:")
                log_error(f"  - kind: unstake")
                log_error(f"  - counter: {counter_to_use}")
                log_error(f"  - gas_limit: {DEFAULT_UNSTAKE_GAS}")
                log_error(f"  - storage_limit: {DEFAULT_UNSTAKE_STORAGE}")
                log_error(f"  - fee: {DEFAULT_UNSTAKE_FEE} mutez")
                log_error(f"  - amount: {amount_mutez} mutez")

                # Prepare payload for RPC forge
                forge_payload = {
                    'branch': branch,
                    'contents': [op_contents]
                }

                # Get RPC forge
                log_error(f"[Attempt {attempt + 1}] Requesting forge from RPC...")
                try:
                    forge_url = f"{rpc}/chains/main/blocks/head/helpers/forge/operations"
                    forge_response = requests.post(
                        forge_url,
                        json=forge_payload,
                        headers={'content-type': 'application/json'},
                        timeout=30
                    )

                    if forge_response.status_code != 200:
                        raise RuntimeError(f"RPC forge failed: {forge_response.status_code} - {forge_response.text}")

                    rpc_forged_hex = forge_response.text.strip().strip('"')
                    log_error(f"[Attempt {attempt + 1}] RPC forged bytes: {rpc_forged_hex}")

                except Exception as forge_err:
                    log_error(f"RPC forge request failed", exception=forge_err)
                    raise RuntimeError(f"Failed to forge operation via RPC: {forge_err}")

                # Sign and inject using RPC forge
                log_error(f"[Attempt {attempt + 1}] Signing RPC-forged bytes...")
                result = sign_and_inject_from_rpc_forge(rpc, key, rpc_forged_hex)
                log_error(f"[Attempt {attempt + 1}] ✅ Inject successful!")

                if isinstance(result, dict):
                    return result.get("hash", str(result))
                return str(result)

            except Exception as e:
                last_error = e
                if _is_counter_error(e) and attempt < max_retries:
                    # Conservative backoff for counter synchronization
                    wait_time = 5.0 * (attempt + 1)  # 5s, 10s, 15s
                    log_error(f"Counter error on unstake attempt {attempt + 1}, waiting {wait_time}s", exception=e)
                    time.sleep(wait_time)
                    continue
                else:
                    raise last_error

    try:
        return _inject_with_retry()
    except Exception as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal first
        log_error("Wallet not revealed. Attempting reveal operation first...")

        def _inject_reveal_with_retry(max_retries: int = 3):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        settling_time = 3.0
                        log_error(f"Waiting {settling_time}s before reveal retry {attempt + 1}")
                        time.sleep(settling_time)

                    # Create fresh client with correct pattern
                    fresh_client = pytezos.using(shell=rpc, key=key)
                    op = fresh_client.reveal()

                    # Trust autofill() completely - don't interfere
                    op = op.autofill()
                    op = op.sign()
                    result = op.inject()

                    if isinstance(result, dict):
                        return result.get("hash", str(result))
                    return str(result)

                except Exception as e:
                    last_error = e
                    if _is_counter_error(e) and attempt < max_retries:
                        # Conservative backoff for counter synchronization
                        wait_time = 5.0 * (attempt + 1)  # 5s, 10s, 15s
                        log_error(f"Counter error on reveal attempt {attempt + 1}, waiting {wait_time}s", exception=e)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise last_error

        try:
            reveal_oph = _inject_reveal_with_retry()
        except Exception as rev_e:
            raise RuntimeError(
                f"Failed to reveal wallet public key. "
                f"This wallet has never been used before and needs to reveal its public key first. "
                f"Error: {rev_e}"
            ) from rev_e

        log_error(f"Reveal successful ({reveal_oph}), waiting 8s for network propagation")
        time.sleep(8)

        try:
            return _inject_with_retry()
        except Exception as unstake_e:
            raise RuntimeError(f"Unstake failed after reveal ({reveal_oph}): {unstake_e}") from unstake_e

