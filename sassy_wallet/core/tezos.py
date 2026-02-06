from typing import Optional, Any, Dict, List, Callable
from decimal import Decimal
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time
import requests
from threading import RLock

from pytezos import pytezos
from pytezos.crypto.key import Key
from pytezos.crypto.encoding import base58_decode
from pytezos.rpc.errors import RpcError

from sassy_wallet import __version__
from .logger import safe_log_exception, log_error, log_debug, log_info, log_warning
from .validation import normalize_https_url, normalize_rpc_url


# Watermark for operation signing
OPERATION_WATERMARK = b"\x03"
_SSL_CONTEXT = ssl.create_default_context()
_USER_AGENT = f"sassy-wallet/{__version__}"
_TZKT_ACCOUNT_CACHE_TTL = 30.0
_TZKT_ACCOUNT_CACHE_MAX = 256
_tzkt_account_cache: dict[str, tuple[float, dict]] = {}
_tzkt_account_cache_lock = RLock()
_TZKT_HISTORY_CACHE_TTL = 10.0
_TZKT_HISTORY_CACHE_MAX = 256
_tzkt_history_cache: dict[str, tuple[float, list]] = {}
_tzkt_history_cache_lock = RLock()
_TZKT_STAKE_STATUS_CACHE_TTL = 15.0
_TZKT_STAKE_STATUS_CACHE_MAX = 512
_tzkt_stake_status_cache: dict[tuple[str, str], tuple[float, int]] = {}
_tzkt_stake_status_cache_lock = RLock()
_RPC_CHAIN_STATE_CACHE_TTL = 12.0
_RPC_CHAIN_STATE_CACHE_MAX = 256
_rpc_chain_state_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_rpc_chain_state_cache_lock = RLock()
_RPC_IO_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    urllib.error.URLError,
    urllib.error.HTTPError,
    ssl.SSLError,
    requests.RequestException,
)
_PARSE_EXCEPTIONS = (TypeError, ValueError, KeyError, IndexError, AttributeError)
_OP_RETRY_EXCEPTIONS = _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS + (RuntimeError, RpcError)
_PENDING_UNKNOWN = "unknown"


def _validate_request_url(req: urllib.request.Request) -> None:
    """Validate request URL before any urlopen call."""
    try:
        normalize_https_url(req.full_url, allow_query=True, allow_fragment=False)
    except ValueError as e:
        raise RuntimeError(f"Blocked unsafe URL: {e}") from e


def _cache_set_bounded(cache: dict[Any, tuple[float, Any]], key: Any, value: tuple[float, Any], *, max_size: int) -> None:
    """Insert into a timestamped cache and evict oldest entries when above capacity."""
    cache[key] = value
    if len(cache) <= max_size:
        return
    while len(cache) > max_size:
        oldest_key = min(cache, key=lambda k: cache[k][0])
        cache.pop(oldest_key, None)


def _inject_reveal_with_counter_retry(
    rpc: str,
    key: Key,
    *,
    is_counter_error: Callable[[Exception], bool],
    max_retries: int = 3,
) -> str:
    rpc = normalize_rpc_url(rpc)
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                settling_time = 3.0
                log_debug(f"Waiting {settling_time}s before reveal retry {attempt + 1}")
                time.sleep(settling_time)

            # pytezos uses `shell` keyword for RPC URL; this is not subprocess shell execution.
            fresh_client = pytezos.using(shell=rpc, key=key)  # nosec B604
            op = fresh_client.reveal()
            op = op.autofill()
            op = op.sign()
            result = op.inject()

            if isinstance(result, dict):
                return str(result.get("hash", str(result)))
            return str(result)

        except _OP_RETRY_EXCEPTIONS as e:
            last_error = e
            if is_counter_error(e) and attempt < max_retries:
                wait_time = 5.0 * (attempt + 1)
                log_error(f"Counter error on reveal attempt {attempt + 1}, waiting {wait_time}s", exception=e)
                time.sleep(wait_time)
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("Reveal retry loop exited unexpectedly")


def _is_counter_sync_error(exception: Exception) -> bool:
    """Check whether an RPC failure is caused by counter desynchronization."""
    error_str = str(exception).lower()
    return "counter" in error_str and ("not yet reached" in error_str or "already used" in error_str)


def inject_signed_operation(rpc: str, signed_op_hex: str) -> str:
    """
    Inject a signed operation directly to the RPC.

    Args:
        rpc: RPC endpoint
        signed_op_hex: Hex-encoded signed operation (forged_bytes + signature)

    Returns:
        Operation hash
    """
    rpc = normalize_rpc_url(rpc)
    url = f"{rpc}/injection/operation?chain=main"
    data = json.dumps(signed_op_hex).encode("utf-8")  # Body: "deadbeef..." (JSON string)
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    log_debug(f"[INJECTION DEBUG] URL: {url}")
    log_debug(f"[INJECTION DEBUG] Body length: {len(data)} bytes")

    try:
        data_bytes = _urlopen_bytes_with_retries(req, timeout=30, retries=3)
        result = data_bytes.decode().strip().strip('"')
        log_debug(f"[INJECTION DEBUG] Success! Op hash: {result}")
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
    log_debug(f"[SIGNATURE DEBUG] sig_result type: {type(sig_result).__name__}")
    log_debug(f"[SIGNATURE DEBUG] sig_result repr: {repr(sig_result)[:100]}...")
    log_debug(f"[SIGNATURE DEBUG] sig_result is str: {isinstance(sig_result, str)}")
    log_debug(f"[SIGNATURE DEBUG] sig_result is bytes: {isinstance(sig_result, bytes)}")

    # 4) Convert to raw bytes (must be exactly 64 bytes)
    # ONLY decode if it's explicitly a string, otherwise treat as bytes
    if isinstance(sig_result, str):
        # Base58 string like "sigXXX...", decode it
        log_debug(f"[SIGNATURE DEBUG] Decoding as base58 string...")
        sig_bytes = base58_decode(sig_result.encode("utf-8"))
    else:
        # Bytes or bytes-like object, use directly
        log_debug(f"[SIGNATURE DEBUG] Using as raw bytes...")
        sig_bytes = bytes(sig_result) if not isinstance(sig_result, bytes) else sig_result

    log_debug(f"[SIGNATURE DEBUG] sig_bytes length: {len(sig_bytes)} bytes")

    # CRITICAL CHECK: Must be exactly 64 bytes
    if len(sig_bytes) != 64:
        raise RuntimeError(f"Signature bytes length invalid: {len(sig_bytes)} (expected 64)")

    # 5) Combine: forged + signature bytes
    signed_op_hex = rpc_forged_hex + sig_bytes.hex()

    # DEBUG: Verify concatenation
    log_debug(f"[SIGNATURE DEBUG] Forged part: {len(rpc_forged_hex)} chars")
    log_debug(f"[SIGNATURE DEBUG] Signature part: {len(sig_bytes.hex())} chars (should be 128)")
    log_debug(f"[SIGNATURE DEBUG] Total: {len(signed_op_hex)} chars (should be {len(rpc_forged_hex)} + 128)")

    # CRITICAL CHECK: Total length must be correct
    expected_length = len(rpc_forged_hex) + 128  # 64 bytes = 128 hex chars
    if len(signed_op_hex) != expected_length:
        raise RuntimeError(f"Signed op length {len(signed_op_hex)} != expected {expected_length}")

    # 6) Inject the hex
    return inject_signed_operation(rpc, signed_op_hex)


def get_client(rpc: str, key: Optional[Key] = None) -> Any:
    """Get PyTezos client instance. Returns pytezos client object."""
    rpc = normalize_rpc_url(rpc)
    # pytezos uses `shell` keyword for RPC URL; this is not subprocess shell execution.
    return pytezos.using(shell=rpc, key=key)  # nosec B604


def get_counter(rpc: str, address: str) -> int:
    """
    Get the current counter for an address directly from RPC.
    This is the counter value to use for the NEXT operation.
    """
    client = get_client(rpc)
    counter_str = client.shell.contracts[address].counter()
    # The counter() call returns the last used counter, so we need to increment by 1
    return int(counter_str) + 1


def _extract_pending_ops_from_bucket(
    pending_ops: dict[str, Any],
    *,
    bucket: str,
    address: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    if not isinstance(pending_ops, dict) or bucket not in pending_ops:
        return extracted

    for op in pending_ops[bucket]:
        try:
            if not isinstance(op, dict) or "contents" not in op:
                continue
            for content in op["contents"]:
                if not isinstance(content, dict):
                    continue
                if content.get("source", "") != address:
                    continue
                item: dict[str, Any] = {
                    "hash": op.get("hash", _PENDING_UNKNOWN),
                    "kind": content.get("kind", _PENDING_UNKNOWN),
                    "counter": content.get("counter", _PENDING_UNKNOWN),
                }
                if status is not None:
                    item["status"] = status
                extracted.append(item)
        except _PARSE_EXCEPTIONS:
            continue
    return extracted


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
        except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS:
            # Some RPCs don't expose mempool, return None
            return None

        if not pending_ops:
            return None

        user_pending_ops = _extract_pending_ops_from_bucket(
            pending_ops,
            bucket="applied",
            address=address,
        )
        user_pending_ops.extend(
            _extract_pending_ops_from_bucket(
                pending_ops,
                bucket="unprocessed",
                address=address,
                status="unprocessed",
            )
        )

        if user_pending_ops:
            return {
                'has_pending': True,
                'pending_count': len(user_pending_ops),
                'operations': user_pending_ops,
            }

        return None

    except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS as e:
        log_error("Failed to check pending operations", exception=e)
        return None


def get_balance_mutez(rpc: str, address: str) -> int:
    client = get_client(rpc)
    return int(client.shell.contracts[address].balance())


def _rpc_contract_url(rpc: str, address: str, field: str) -> str:
    base = normalize_rpc_url(rpc)
    return f"{base}/chains/main/blocks/head/context/contracts/{address}/{field}"


def _rpc_urlopen_json(
    req: urllib.request.Request,
    *,
    timeout: int = 10,
    retries: int = 1,
) -> Any:
    """RPC-specific JSON fetch that treats 404 as 'not available' without error spam."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            _validate_request_url(req)
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:  # nosec B310
                data = resp.read().decode("utf-8")
            return json.loads(data)
        except urllib.error.HTTPError as e:
            # 404 = field not supported on this RPC/protocol; treat as None quietly.
            if getattr(e, "code", None) == 404:
                return None
            last_err = e
            if attempt >= retries:
                break
            time.sleep(0.2 * attempt)
        except (ssl.SSLError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_err = e
            if attempt >= retries:
                break
            time.sleep(0.2 * attempt)
        except _PARSE_EXCEPTIONS as e:
            last_err = e
            break
    if last_err:
        log_debug("RPC JSON fetch failed", exception=str(last_err), url=req.full_url)
    return None


def _rpc_get_contract_value(rpc: str, address: str, field: str) -> Any:
    url = _rpc_contract_url(rpc, address, field)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT},
        method="GET",
    )
    return _rpc_urlopen_json(req, timeout=10, retries=1)


def _rpc_get_contract_int(rpc: str, address: str, field: str) -> Optional[int]:
    val = _rpc_get_contract_value(rpc, address, field)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _rpc_get_delegate(rpc: str, address: str) -> Optional[str]:
    val = _rpc_get_contract_value(rpc, address, "delegate")
    if isinstance(val, str) and val.startswith("tz"):
        return val.strip() or None
    return None


def get_wallet_chain_state_rpc(
    rpc: str,
    address: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Best-effort snapshot of on-chain wallet state via RPC (authoritative when available).

    Returns:
        {
            "delegate": Optional[str],
            "balance_mutez": int,
            "staked_mutez": int,
            "unstaked_mutez": int,
            "staking_active": Optional[bool],  # None if RPC doesn't expose staking fields
        }
    """
    cache_key = (rpc, address)
    now = time.time()
    if not force_refresh:
        with _rpc_chain_state_cache_lock:
            cached = _rpc_chain_state_cache.get(cache_key)
            if cached:
                ts, data = cached
                if now - ts < _RPC_CHAIN_STATE_CACHE_TTL:
                    return dict(data)
                _rpc_chain_state_cache.pop(cache_key, None)

    delegate = _rpc_get_delegate(rpc, address)
    balance = _rpc_get_contract_int(rpc, address, "balance")

    staked = None
    for key in ("staked_balance", "staking_balance"):
        staked = _rpc_get_contract_int(rpc, address, key)
        if staked is not None:
            break

    unstaked = None
    for key in ("unstaked_balance", "unfinalized_unstake_balance"):
        unstaked = _rpc_get_contract_int(rpc, address, key)
        if unstaked is not None:
            break

    staking_active: Optional[bool] = None
    if staked is not None or unstaked is not None:
        staking_active = bool((staked or 0) > 0 or (unstaked or 0) > 0)

    result = {
        "delegate": delegate,
        "balance_mutez": int(balance or 0),
        "staked_mutez": int(staked or 0),
        "unstaked_mutez": int(unstaked or 0),
        "staking_active": staking_active,
    }

    with _rpc_chain_state_cache_lock:
        _cache_set_bounded(
            _rpc_chain_state_cache,
            cache_key,
            (now, dict(result)),
            max_size=_RPC_CHAIN_STATE_CACHE_MAX,
        )
    return result


@safe_log_exception(default_return=None, user_message="Failed to get delegation info")
def get_delegation_info(rpc: str, address: str, *, force_refresh: bool = False) -> Optional[str]:
    """
    Get the baker address this account is delegated to.
    Returns None if not delegated.
    """
    data = _tzkt_get_account(rpc, address, force_refresh=force_refresh)

    # Check if delegated
    delegate = data.get("delegate")
    if isinstance(delegate, str):
        return delegate.strip() or None
    if isinstance(delegate, dict):
        delegate_address = delegate.get("address")
        return delegate_address if delegate_address else None

    return None


@safe_log_exception(default_return=0, user_message="Failed to get staking balance")
def get_staking_balance(rpc: str, address: str, *, force_refresh: bool = False) -> int:
    """
    Get the staking balance (staked amount) for this account in mutez.
    Returns 0 if not staking or if information is unavailable.
    """
    data = _tzkt_get_account(rpc, address, force_refresh=force_refresh)

    # Get staked balance (TzKT schema can vary across versions/networks)
    staking_obj = data.get("staking") if isinstance(data, dict) else None
    staked_balance = None
    if isinstance(data, dict):
        staked_balance = data.get("stakedBalance")
        if staked_balance is None:
            staked_balance = data.get("stakingBalance")
        if staked_balance is None:
            staked_balance = data.get("staked_balance")
    if staked_balance is None and isinstance(staking_obj, dict):
        staked_balance = staking_obj.get("stakedBalance")
        if staked_balance is None:
            staked_balance = staking_obj.get("stakingBalance")
    try:
        return int(staked_balance) if staked_balance else 0
    except (TypeError, ValueError):
        return 0


@safe_log_exception(default_return=None, user_message="Failed to get baker info")
def get_baker_info(rpc: str, baker_address: str, *, force_refresh: bool = False) -> Optional[dict]:
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
    data = _tzkt_get_account(rpc, baker_address, force_refresh=force_refresh)

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


def _get_wallet_chain_state_tzkt(rpc: str, address: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Best-effort snapshot of wallet state via TzKT (indexer)."""
    data = _tzkt_get_account(rpc, address, force_refresh=force_refresh)
    delegate = None
    raw_delegate = data.get("delegate") if isinstance(data, dict) else None
    if isinstance(raw_delegate, str):
        delegate = raw_delegate.strip() or None
    elif isinstance(raw_delegate, dict):
        delegate_addr = raw_delegate.get("address")
        delegate = delegate_addr if isinstance(delegate_addr, str) and delegate_addr else None

    balance = 0
    staked = 0
    stake_related = 0
    if isinstance(data, dict):
        try:
            balance = int(data.get("balance") or 0)
        except (TypeError, ValueError):
            balance = 0
        staking_obj = data.get("staking") if isinstance(data.get("staking"), dict) else None

        raw_staked = data.get("stakedBalance")
        if raw_staked is None:
            raw_staked = data.get("stakingBalance")
        if raw_staked is None:
            raw_staked = data.get("staked_balance")
        if raw_staked is None and isinstance(staking_obj, dict):
            raw_staked = staking_obj.get("stakedBalance") or staking_obj.get("stakingBalance")

        raw_unstaked = data.get("unstakedBalance")
        if raw_unstaked is None:
            raw_unstaked = data.get("unfinalizedUnstakeBalance")
        if raw_unstaked is None and isinstance(staking_obj, dict):
            raw_unstaked = (
                staking_obj.get("unstakedBalance")
                or staking_obj.get("unfinalizedUnstakeBalance")
                or staking_obj.get("unstakingBalance")
            )
        try:
            staked = int(raw_staked) if raw_staked else 0
        except (TypeError, ValueError):
            staked = 0
        try:
            stake_related = int(raw_unstaked) if raw_unstaked else 0
        except (TypeError, ValueError):
            stake_related = 0

    staking_active = bool((staked > 0) or (stake_related > 0))
    if not staking_active and delegate:
        try:
            staking_active = infer_is_staking(rpc, address, force_refresh=force_refresh)
        except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS as e:
            log_warning("Failed to infer staking status", exception=e, address=address)
            staking_active = False

    return {
        "delegate": delegate,
        "balance_mutez": balance,
        "staked_mutez": staked,
        "unstaked_mutez": stake_related,
        "staking_active": staking_active,
    }


def get_wallet_chain_state(
    rpc: str,
    address: str,
    *,
    force_refresh: bool = False,
    prefer_rpc: bool = False,
) -> dict[str, Any]:
    """
    Best-effort snapshot of wallet state.

    - If prefer_rpc=True, try RPC first and fall back to TzKT for missing staking info.
    - Otherwise use TzKT directly (existing behavior).
    """
    if not prefer_rpc:
        return _get_wallet_chain_state_tzkt(rpc, address, force_refresh=force_refresh)

    try:
        rpc_state = get_wallet_chain_state_rpc(rpc, address, force_refresh=force_refresh)
    except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS as e:
        log_warning("RPC chain-state fetch failed; falling back to TzKT", exception=e, address=address)
        return _get_wallet_chain_state_tzkt(rpc, address, force_refresh=force_refresh)

    # If RPC doesn't expose staking fields, enrich from TzKT.
    if rpc_state.get("staking_active") is None:
        tzkt_state = _get_wallet_chain_state_tzkt(rpc, address, force_refresh=force_refresh)
        merged = dict(tzkt_state)
        if rpc_state.get("delegate") is not None:
            merged["delegate"] = rpc_state["delegate"]
        if rpc_state.get("balance_mutez") is not None:
            merged["balance_mutez"] = rpc_state["balance_mutez"]
        # Prefer RPC staked if we managed to read it (even if 0).
        if rpc_state.get("staked_mutez") is not None:
            merged["staked_mutez"] = rpc_state["staked_mutez"]
        if rpc_state.get("unstaked_mutez") is not None:
            merged["unstaked_mutez"] = rpc_state["unstaked_mutez"]
        return merged

    return rpc_state


def mutez_to_xtz(m: int) -> Decimal:
    return Decimal(m) / Decimal(1_000_000)


def xtz_to_mutez(x: Decimal) -> int:
    return int((x * Decimal(1_000_000)).to_integral_value())


def key_from_encoded_secret(encoded: str, passphrase: str | None = None) -> Key:
    if passphrase:
        try:
            return Key.from_encoded_key(encoded, passphrase=passphrase)
        except TypeError:
            return Key.from_encoded_key(encoded)
    return Key.from_encoded_key(encoded)


def key_from_mnemonic_ledger(
    mnemonic: str, passphrase: str = "", derivation_path: str = ""
) -> Key:  # nosec B107
    # Empty BIP39 passphrase is a valid and common default.
    """Derive a Tezos key from a BIP39 mnemonic using a derivation path."""
    try:
        from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
    except ImportError as e:
        raise RuntimeError("bip_utils is required for mnemonic import") from e

    seed = Bip39SeedGenerator(mnemonic).Generate(passphrase)
    if derivation_path:
        bip44_ctx = Bip44.FromSeedAndPath(seed, derivation_path)
        bip44_acc = bip44_ctx
    else:
        bip44_ctx = Bip44.FromSeed(seed, Bip44Coins.TEZOS)
        bip44_acc = (
            bip44_ctx.Purpose()
            .Coin()
            .Account(0)
            .Change(Bip44Changes.CHAIN_EXT)
            .AddressIndex(0)
        )
    secret_exponent = bip44_acc.PrivateKey().Raw().ToBytes()
    return Key.from_secret_exponent(secret_exponent, curve=b"ed")


def _contains_unrevealed_key(err: Any) -> bool:
    try:
        s = str(err)
    except (TypeError, ValueError) as e:
        log_error("Failed to convert error to string", exception=e)
        s = ""
    s_low = s.lower()
    if "unrevealed_key" in s_low or "unrevealed manager key" in s_low:
        return True

    try:
        r = repr(err)
    except (TypeError, ValueError) as e:
        log_error("Failed to get repr of error", exception=e)
        r = ""
    r_low = r.lower()
    return "unrevealed_key" in r_low or "unrevealed manager key" in r_low


def _is_gas_exhausted_error(err: Exception) -> bool:
    try:
        s = str(err).lower()
    except (TypeError, ValueError):
        return False
    return "gas_exhausted" in s and "operation" in s


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
    except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS as e:
        # If we can't determine, assume it's revealed to avoid false warnings
        log_error(f"Could not check reveal status for {address}", exception=e)
        return True


def _tzkt_base_from_rpc(rpc: str) -> str:
    rpc_l = normalize_rpc_url(rpc).lower()
    if "ghostnet" in rpc_l:
        return "https://api.ghostnet.tzkt.io"
    return "https://api.tzkt.io"


def _tzkt_account_url(rpc: str, address: str) -> str:
    base = _tzkt_base_from_rpc(rpc)
    return f"{base}/v1/accounts/{address}"


def _extract_addr(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            addr = value.get("address")
            if isinstance(addr, str):
                return addr
        elif isinstance(value, str):
            return value
    return ""


def _delegate_from_updates(updates: list[dict]) -> str:
    for update in updates:
        if not isinstance(update, dict):
            continue
        if update.get("kind") == "freezer" and update.get("category") == "deposits":
            staker = update.get("staker")
            if isinstance(staker, dict):
                delegate = staker.get("delegate")
                if isinstance(delegate, str):
                    return delegate
        if update.get("kind") == "staking" and isinstance(update.get("delegate"), str):
            return update.get("delegate")
    return ""


def _format_baker_label(rpc: str, baker_addr: str) -> str:
    if not baker_addr:
        return "?"
    info = get_baker_info(rpc, baker_addr)
    alias = info.get("alias") if info else None
    return alias or baker_addr


def invalidate_tzkt_account_cache(rpc: str, address: str) -> None:
    """Drop cached TzKT account data for this RPC/address."""
    url = _tzkt_account_url(rpc, address)
    with _tzkt_account_cache_lock:
        _tzkt_account_cache.pop(url, None)


def _tzkt_get_account(rpc: str, address: str, *, force_refresh: bool = False) -> dict:
    base = _tzkt_base_from_rpc(rpc)
    url = f"{base}/v1/accounts/{address}"

    now = time.time()
    if not force_refresh:
        with _tzkt_account_cache_lock:
            cached = _tzkt_account_cache.get(url)
            if cached:
                ts, data = cached
                if now - ts < _TZKT_ACCOUNT_CACHE_TTL:
                    return data
                _tzkt_account_cache.pop(url, None)
    else:
        with _tzkt_account_cache_lock:
            _tzkt_account_cache.pop(url, None)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT},
        method="GET",
    )
    data = _urlopen_json_with_retries(req, timeout=15, retries=3)
    if not isinstance(data, dict):
        log_warning("Unexpected TzKT response type", url=url, response_type=type(data).__name__)
        return {}

    resp_address = data.get("address")
    if not isinstance(resp_address, str) or resp_address != address:
        log_warning("TzKT response missing or mismatched address", url=url, response_address=resp_address)
        return {}

    with _tzkt_account_cache_lock:
        _cache_set_bounded(
            _tzkt_account_cache,
            url,
            (now, data),
            max_size=_TZKT_ACCOUNT_CACHE_MAX,
        )
    return data


def _tzkt_latest_entrypoint_level(
    rpc: str,
    address: str,
    *,
    entrypoint: str,
    force_refresh: bool = False,
) -> int:
    """
    Return latest applied operation level for a given entrypoint (stake/unstake), or 0 if none.
    Uses a small in-memory cache to avoid repeated calls when listing many wallets.
    """
    base = _tzkt_base_from_rpc(rpc)
    cache_key = (f"{base}|{address}", entrypoint)
    now = time.time()
    if not force_refresh:
        with _tzkt_stake_status_cache_lock:
            cached = _tzkt_stake_status_cache.get(cache_key)
            if cached:
                ts, level = cached
                if now - ts < _TZKT_STAKE_STATUS_CACHE_TTL:
                    return level
                _tzkt_stake_status_cache.pop(cache_key, None)
    else:
        with _tzkt_stake_status_cache_lock:
            _tzkt_stake_status_cache.pop(cache_key, None)

    def _first_level(items: Any) -> int:
        if not isinstance(items, list) or not items:
            return 0
        # Prefer an item that explicitly matches the requested kind/type when available.
        for it in items:
            if not isinstance(it, dict):
                continue
            op_type = it.get("type") or it.get("kind") or it.get("action")
            if op_type and str(op_type).lower() not in (entrypoint,):
                continue
            try:
                return int(it.get("level") or 0)
            except (TypeError, ValueError):
                return 0
        it0 = items[0]
        if isinstance(it0, dict):
            try:
                return int(it0.get("level") or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    level = 0
    candidates: list[tuple[str, dict[str, str]]] = [
        # Protocol staking operations (if TzKT supports this endpoint).
        (f"{base}/v1/operations/staking", {"sender": address, "type": entrypoint, "status": "applied", "limit": "1", "sort.desc": "level"}),
        (f"{base}/v1/operations/staking", {"sender": address, "action": entrypoint, "status": "applied", "limit": "1", "sort.desc": "level"}),
        (f"{base}/v1/operations/staking", {"sender": address, "kind": entrypoint, "status": "applied", "limit": "1", "sort.desc": "level"}),
        # Unfiltered staking list (best-effort; filter client-side via _first_level).
        (f"{base}/v1/operations/staking", {"sender": address, "status": "applied", "limit": "5", "sort.desc": "level"}),
        # Legacy stake-as-self-transaction entrypoint.
        (f"{base}/v1/operations/transactions", {"sender": address, "entrypoint": entrypoint, "status": "applied", "limit": "1", "sort.desc": "level"}),
    ]

    for base_url, params in candidates:
        url = base_url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}, method="GET")
        try:
            data = _urlopen_json_with_retries(req, timeout=15, retries=3)
        except urllib.error.HTTPError as e:
            log_debug("TzKT stake-status query failed", exception=str(e), url=url)
            continue
        except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS + (RuntimeError,) as e:
            log_debug("TzKT stake-status query failed", exception=str(e), url=url)
            continue

        level = _first_level(data)
        if level > 0:
            break

    with _tzkt_stake_status_cache_lock:
        _cache_set_bounded(
            _tzkt_stake_status_cache,
            cache_key,
            (now, level),
            max_size=_TZKT_STAKE_STATUS_CACHE_MAX,
        )
    return level


def infer_is_staking(rpc: str, address: str, *, force_refresh: bool = False) -> bool:
    """
    Infer staking status when stakedBalance is missing/lagging.

    Heuristic:
    - If last stake op is newer than last unstake op => staking likely active.
    - If no stake ops => not staking.
    """
    stake_level = _tzkt_latest_entrypoint_level(rpc, address, entrypoint="stake", force_refresh=force_refresh)
    if stake_level <= 0:
        return False
    unstake_level = _tzkt_latest_entrypoint_level(rpc, address, entrypoint="unstake", force_refresh=force_refresh)
    return stake_level >= unstake_level


def _urlopen_json_with_retries(req: urllib.request.Request, timeout: int = 15, retries: int = 3) -> Any:
    """
    Fetch JSON via urllib with a few retries to smooth out transient TLS/EOF issues.
    Returns parsed JSON (typically a dict).
    """
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            _validate_request_url(req)
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:  # nosec B310
                data = resp.read().decode("utf-8")
            return json.loads(data)
        except (ssl.SSLError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_err = e
            log_error(f"Network error on attempt {attempt}/{retries}", exception=e, url=req.full_url)
            if attempt >= retries:
                break
            # small backoff
            time.sleep(0.4 * attempt)
        except _PARSE_EXCEPTIONS + (RuntimeError,) as e:
            # non-network errors: don't spin
            log_error("Non-network error in URL fetch", exception=e, url=req.full_url)
            raise
    if last_err:
        log_error("All retry attempts exhausted", exception=last_err, url=req.full_url)
        raise last_err
    else:
        raise RuntimeError("Failed to fetch JSON")


def _urlopen_bytes_with_retries(req: urllib.request.Request, timeout: int = 15, retries: int = 3) -> bytes:
    """
    Fetch raw bytes via urllib with a few retries to smooth out transient TLS/EOF issues.
    Returns response body bytes.
    """
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            _validate_request_url(req)
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:  # nosec B310
                return resp.read()
        except (ssl.SSLError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_err = e
            log_error(f"Network error on attempt {attempt}/{retries}", exception=e, url=req.full_url)
            if attempt >= retries:
                break
            time.sleep(0.4 * attempt)
        except _PARSE_EXCEPTIONS + (RuntimeError,) as e:
            log_error("Non-network error in URL fetch", exception=e, url=req.full_url)
            raise
    if last_err:
        log_error("All retry attempts exhausted", exception=last_err, url=req.full_url)
        raise last_err
    raise RuntimeError("Failed to fetch bytes")


def get_xtz_history(rpc: str, address: str, limit: int = 20) -> List[Dict[str, Any]]:
    base = _tzkt_base_from_rpc(rpc)

    tx_params = {
        "anyof.sender.target": address,
        "status": "applied",
        "limit": str(limit * 2),
        "sort.desc": "level",
        "withMetadata": "true",
    }
    tx_url = f"{base}/v1/operations/transactions?" + urllib.parse.urlencode(tx_params)

    stake_params = {
        "sender": address,
        "entrypoint": "stake",
        "status": "applied",
        "limit": str(limit * 2),
        "sort.desc": "level",
        "withMetadata": "true",
    }
    stake_url = f"{base}/v1/operations/transactions?" + urllib.parse.urlencode(stake_params)

    unstake_params = {
        "sender": address,
        "entrypoint": "unstake",
        "status": "applied",
        "limit": str(limit * 2),
        "sort.desc": "level",
        "withMetadata": "true",
    }
    unstake_url = f"{base}/v1/operations/transactions?" + urllib.parse.urlencode(unstake_params)

    deleg_params = {
        "sender": address,
        "status": "applied",
        "limit": str(limit * 2),
        "sort.desc": "level",
    }
    deleg_url = f"{base}/v1/operations/delegations?" + urllib.parse.urlencode(deleg_params)

    now = time.time()
    cache_key = f"{tx_url}|{stake_url}|{unstake_url}|{deleg_url}"
    with _tzkt_history_cache_lock:
        cached = _tzkt_history_cache.get(cache_key)
        if cached:
            ts, data = cached
            if now - ts < _TZKT_HISTORY_CACHE_TTL:
                return data
            _tzkt_history_cache.pop(cache_key, None)

    def _fetch_list(url: str) -> list[dict]:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT},
            method="GET",
        )
        data = _urlopen_json_with_retries(req, timeout=15, retries=3)
        return data if isinstance(data, list) else []

    tx_items = _fetch_list(tx_url)
    stake_items = _fetch_list(stake_url)
    unstake_items = _fetch_list(unstake_url)
    deleg_items = _fetch_list(deleg_url)
    out: list[dict] = []
    seen_hashes: set[str] = set()

    def _extract_delegate(it: dict) -> tuple[str, str]:
        for key in ("newDelegate", "delegate", "target", "destination"):
            val = it.get(key)
            if isinstance(val, dict):
                addr = val.get("address") or ""
                alias = val.get("alias") or ""
                return addr, alias
            if isinstance(val, str):
                return val, ""
        return "", ""

    for it in tx_items:
        sender = _extract_addr(it, "sender", "source")
        target = _extract_addr(it, "target", "destination")
        amount_mutez = int(it.get("amount") or 0)
        params = it.get("parameter") or it.get("parameters") or {}
        entrypoint = params.get("entrypoint") if isinstance(params, dict) else None
        metadata = it.get("metadata") or {}
        op_res = metadata.get("operation_result") or {}
        updates = op_res.get("balance_updates") or metadata.get("balance_updates") or []

        if sender == address and target == address and entrypoint == "stake":
            direction = "STK"
            baker_addr = _delegate_from_updates(updates)
            if not baker_addr:
                baker_addr = get_delegation_info(rpc, address) or ""
            counterparty = _format_baker_label(rpc, baker_addr)
            baker_label = counterparty
        elif sender == address and target == address and entrypoint == "unstake":
            direction = "UST"
            baker_addr = _delegate_from_updates(updates)
            if not baker_addr:
                baker_addr = get_delegation_info(rpc, address) or ""
            counterparty = _format_baker_label(rpc, baker_addr)
            baker_label = counterparty
        elif sender == address:
            direction = "OUT"
            counterparty = target or "?"
        elif target == address:
            direction = "IN"
            counterparty = sender or "?"
        else:
            direction = "?"
            counterparty = "?"

        item = {
            "ts": it.get("timestamp") or "",
            "direction": direction,
            "amount_xtz": mutez_to_xtz(amount_mutez),
            "counterparty": counterparty,
            "hash": it.get("hash") or "",
            "kind": "transaction",
            "entrypoint": entrypoint or "",
        }
        if direction in ("STK", "UST"):
            item["baker"] = baker_label
        if item["hash"]:
            seen_hashes.add(item["hash"])
        out.append(item)

    for it in stake_items:
        h = it.get("hash") or ""
        if h in seen_hashes:
            continue
        amount_mutez = int(it.get("amount") or 0)
        metadata = it.get("metadata") or {}
        op_res = metadata.get("operation_result") or {}
        updates = op_res.get("balance_updates") or metadata.get("balance_updates") or []
        baker_addr = _delegate_from_updates(updates)
        if not baker_addr:
            baker_addr = get_delegation_info(rpc, address) or ""
        counterparty = _format_baker_label(rpc, baker_addr)
        item = {
            "ts": it.get("timestamp") or "",
            "direction": "STK",
            "amount_xtz": mutez_to_xtz(amount_mutez),
            "counterparty": counterparty,
            "hash": h,
            "kind": "transaction",
            "entrypoint": "stake",
            "baker": counterparty,
        }
        if h:
            seen_hashes.add(h)
        out.append(item)

    for it in unstake_items:
        h = it.get("hash") or ""
        if h in seen_hashes:
            continue
        amount_mutez = int(it.get("amount") or 0)
        metadata = it.get("metadata") or {}
        op_res = metadata.get("operation_result") or {}
        updates = op_res.get("balance_updates") or metadata.get("balance_updates") or []
        baker_addr = _delegate_from_updates(updates)
        if not baker_addr:
            baker_addr = get_delegation_info(rpc, address) or ""
        counterparty = _format_baker_label(rpc, baker_addr)
        item = {
            "ts": it.get("timestamp") or "",
            "direction": "UST",
            "amount_xtz": mutez_to_xtz(amount_mutez),
            "counterparty": counterparty,
            "hash": h,
            "kind": "transaction",
            "entrypoint": "unstake",
            "baker": counterparty,
        }
        if h:
            seen_hashes.add(h)
        out.append(item)

    for it in deleg_items:
        delegate_addr, delegate_alias = _extract_delegate(it)
        direction = "DEL" if delegate_addr else "UND"
        if delegate_alias:
            counterparty = delegate_alias
        elif delegate_addr:
            counterparty = _format_baker_label(rpc, delegate_addr)
        else:
            counterparty = "—"

        out.append(
            {
                "ts": it.get("timestamp") or "",
                "direction": direction,
                "amount_xtz": Decimal(0),
                "counterparty": counterparty,
                "hash": it.get("hash") or "",
                "kind": "delegation",
            }
        )

    out.sort(key=lambda x: x.get("ts") or "", reverse=True)
    out = out[:limit]

    with _tzkt_history_cache_lock:
        _cache_set_bounded(
            _tzkt_history_cache,
            cache_key,
            (now, out),
            max_size=_TZKT_HISTORY_CACHE_MAX,
        )
    return out


def has_outgoing_tx(rpc: str, address: str) -> bool:
    """Return True if the address has at least one outgoing transaction."""
    base = _tzkt_base_from_rpc(rpc)
    params = {
        "sender": address,
        "status": "applied",
        "limit": "1",
        "sort.desc": "level",
    }
    url = f"{base}/v1/operations/transactions?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT},
        method="GET",
    )
    data = _urlopen_json_with_retries(req, timeout=10, retries=2)
    return isinstance(data, list) and len(data) > 0


def resolve_tx_by_hash(rpc: str, address: str, oph: str) -> Optional[Dict[str, Any]]:
    """Resolve a transaction by hash from TzKT and format it for history."""
    if not oph:
        return None
    base = _tzkt_base_from_rpc(rpc)
    params = {
        "hash": oph,
        "limit": "1",
        "withMetadata": "true",
    }
    url = f"{base}/v1/operations/transactions?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT},
            method="GET",
        )
        data = _urlopen_json_with_retries(req, timeout=15, retries=2)
        if not isinstance(data, list) or not data:
            data = None
        it = data[0]
    except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS + (RuntimeError,):
        it = None

    if it is None:
        # Fallback: generic operations endpoint
        try:
            url = f"{base}/v1/operations/{oph}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT},
                method="GET",
            )
            data = _urlopen_json_with_retries(req, timeout=15, retries=2)
            if isinstance(data, list) and data:
                it = data[0]
            elif isinstance(data, dict):
                it = data
        except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS + (RuntimeError,):
            return None
        if it is None:
            return None

    sender = _extract_addr(it, "sender", "source")
    target = _extract_addr(it, "target", "destination")
    if sender != address and target != address:
        # Allow delegation-like ops where target isn't set but sender matches.
        if sender != address:
            return None
    amount_mutez = int(it.get("amount") or 0)
    params = it.get("parameter") or it.get("parameters") or {}
    entrypoint = params.get("entrypoint") if isinstance(params, dict) else None
    metadata = it.get("metadata") or {}
    op_res = metadata.get("operation_result") or {}
    updates = op_res.get("balance_updates") or metadata.get("balance_updates") or []
    op_type = it.get("type") or it.get("kind") or ""

    if sender == address and target == address and entrypoint == "stake":
        direction = "STK"
        baker_addr = _delegate_from_updates(updates)
        if not baker_addr:
            baker_addr = get_delegation_info(rpc, address) or ""
        counterparty = _format_baker_label(rpc, baker_addr)
        baker_label = counterparty
    elif sender == address and target == address and entrypoint == "unstake":
        direction = "UST"
        baker_addr = _delegate_from_updates(updates)
        if not baker_addr:
            baker_addr = get_delegation_info(rpc, address) or ""
        counterparty = _format_baker_label(rpc, baker_addr)
        baker_label = counterparty
    elif op_type == "delegation" and sender == address:
        direction = "DEL"
        delegate = _extract_addr(it, "newDelegate", "delegate", "target", "destination")
        counterparty = _format_baker_label(rpc, delegate) if delegate else "—"
    elif sender == address:
        direction = "OUT"
        counterparty = target or "?"
    elif target == address:
        direction = "IN"
        counterparty = sender or "?"
    else:
        direction = "?"
        counterparty = "?"

    item_kind = "delegation" if op_type == "delegation" else "transaction"
    item = {
        "ts": it.get("timestamp") or "",
        "direction": direction,
        "amount_xtz": mutez_to_xtz(amount_mutez),
        "counterparty": counterparty,
        "hash": it.get("hash") or "",
        "kind": item_kind,
        "entrypoint": (entrypoint or "delegation") if op_type == "delegation" else (entrypoint or ""),
        "status": (it.get("status") or "CONFIRMED").upper(),
    }
    if direction in ("STK", "UST"):
        item["baker"] = baker_label
    return item


def invalidate_history_cache() -> None:
    """Clear cached TzKT history data."""
    with _tzkt_history_cache_lock:
        _tzkt_history_cache.clear()


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
        except _OP_RETRY_EXCEPTIONS as e:
            log_error("Failed to estimate reveal operation", exception=e, address=from_addr)
            reveal_info = {"fee_mutez": 0, "gas_limit": 0, "storage_limit": 0}

    try:
        tx_op = client.transaction(destination=to_addr, amount=amount_xtz).autofill()
        tx_info = _extract_limits_from_op(tx_op)
    except _OP_RETRY_EXCEPTIONS as e:
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

    # Delegation is usually cheap, but change-baker with active stake can consume
    # significantly more gas due to implicit unstake mechanics.
    # Detect stake context and raise suggested limits proactively.
    has_stake_context = False
    try:
        chain_state = get_wallet_chain_state(rpc, from_addr, force_refresh=False, prefer_rpc=True)
        staked_mutez = int(chain_state.get("staked_mutez") or 0)
        unstaked_mutez = int(chain_state.get("unstaked_mutez") or 0)
        has_stake_context = bool(staked_mutez > 0 or unstaked_mutez > 0)
    except _RPC_IO_EXCEPTIONS + _PARSE_EXCEPTIONS + (RuntimeError,) as chain_state_err:
        log_debug(
            "Could not determine stake context for delegation estimate",
            address=from_addr,
            exception=str(chain_state_err),
        )

    if has_stake_context:
        economy_fee = 6000
        economy_gas = 25000
        normal_fee = 8000
        normal_gas = 30000
        priority_fee = 12000
        priority_gas = 60000
    else:
        economy_fee = 600
        economy_gas = 800
        normal_fee = 800   # ~0.0008 XTZ
        normal_gas = 1000  # generous margin over typical ~169 gas
        priority_fee = 1200
        priority_gas = 2000

    tx_info = {"fee_mutez": normal_fee, "gas_limit": normal_gas, "storage_limit": 0}

    # Fee options for UI
    fee_options = {
        "economy": {
            "label": "Economy (autofill)",
            "tx_fee_mutez": None,
            "gas_limit": None,
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


def _is_unsupported_manager_op(err: Exception | str) -> bool:
    """Detect RPC/protocol errors when a manager operation kind is unsupported."""
    s = str(err)
    return "No case matched" in s and "At /kind" in s and "unexpected string" in s


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
        use_overrides = kind == "tx"
        override_fee = fee_mutez if use_overrides else None
        override_gas = gas_limit if use_overrides else None
        override_storage = storage_limit if use_overrides else None
        try:
            # Preferimos autofill (obtiene counter/branch + fees/limits por simulación)
            if override_fee is not None or override_gas is not None or override_storage is not None:
                op = op.autofill(
                    fee=int(override_fee) if override_fee is not None else None,
                    gas_limit=int(override_gas) if override_gas is not None else None,
                    storage_limit=int(override_storage) if override_storage is not None else None,
                )
            else:
                op = op.autofill()

        except _OP_RETRY_EXCEPTIONS as e:
            # Fallback: RPC no expone helpers/scripts
            if _is_missing_helpers(e):
                # Intentamos un camino de "fill" (sin simulación) si existe.
                # Para que esto funcione, necesitamos fee/gas/storage ya seteados en el contenido.
                # Si el user no pasó overrides, ponemos defaults.
                if override_fee is None:
                    local_fee = DEFAULT_REVEAL_FEE if kind == 'reveal' else DEFAULT_TX_FEE
                else:
                    local_fee = int(override_fee)

                if override_gas is None:
                    local_gas = DEFAULT_REVEAL_GAS if kind == 'reveal' else DEFAULT_TX_GAS
                else:
                    local_gas = int(override_gas)

                if override_storage is None:
                    local_storage = DEFAULT_REVEAL_STORAGE if kind == 'reveal' else DEFAULT_TX_STORAGE
                else:
                    local_storage = int(override_storage)

                # Si el constructor no soportó fee/gas/storage, no tenemos forma segura de setearlo.
                # En ese caso, devolvemos un error claro para que el usuario cambie de RPC.
                payload_ok = True
                # Best-effort payload probe for older pytezos compatibility.
                # Result is intentionally ignored; we only want to trigger any payload-shape issues early.
                try:
                    payload = op.json_payload()
                    if isinstance(payload, list) and payload:
                        _ = (payload[0] or {}).get('contents', []) or []
                    elif isinstance(payload, dict):
                        _ = payload.get('contents', []) or []
                except _PARSE_EXCEPTIONS as probe_err:
                    log_debug("Payload probe failed; continuing with compatibility fallback", exception=str(probe_err))

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

    except _OP_RETRY_EXCEPTIONS as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal SIEMPRE separado
        try:
            reveal_oph = _inject(_build_reveal_op(), kind='reveal')
        except _OP_RETRY_EXCEPTIONS as rev_e:
            raise RuntimeError(f"Reveal failed: {rev_e}") from rev_e

        # Retry send
        try:
            return _inject(_build_tx_op(), kind='tx')
        except _OP_RETRY_EXCEPTIONS as send_e:
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
    rpc = normalize_rpc_url(rpc)
    source_address = key.public_key_hash()

    # Check if wallet is revealed (has made at least one operation)
    if not is_wallet_revealed(rpc, source_address):
        log_warning(f"⚠️ Wallet {source_address[:10]}... is not revealed. Will attempt reveal operation first.")
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

    def _inject_with_retry(max_retries: int = 3):
        """Build, autofill, sign, and inject with counter error retry logic."""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # On retry attempts, wait for blockchain to settle
                if attempt > 0:
                    settling_time = 3.0  # Wait for blockchain to process previous attempt
                    log_debug(f"Waiting {settling_time}s for blockchain to settle before retry {attempt + 1}")
                    time.sleep(settling_time)

                # Create completely fresh client with NO shared state
                # IMPORTANT: using() creates a NEW instance each time
                # pytezos uses `shell` keyword for RPC URL; this is not subprocess shell execution.
                fresh_client = pytezos.using(shell=rpc, key=key)  # nosec B604

                # Build delegation operation (counter=None means autofill will handle it)
                op = fresh_client.delegation(baker_address)

                # Always autofill to get branch/counter/gas/storage from chain.
                op = op.autofill()

                overrides_used = fee_mutez is not None or gas_limit is not None or storage_limit is not None
                if overrides_used:
                    # Preserve autofilled limits when caller only overrides fee (or one of the limits).
                    payload = op.json_payload()
                    contents = []
                    if isinstance(payload, list) and payload:
                        contents = (payload[0] or {}).get("contents", []) or []
                    elif isinstance(payload, dict):
                        contents = payload.get("contents", []) or []
                    c0 = contents[0] if contents else {}

                    fill_kwargs: dict[str, int] = {}
                    if fee_mutez is not None:
                        fill_kwargs["fee"] = int(fee_mutez)
                    if gas_limit is not None:
                        fill_kwargs["gas_limit"] = int(gas_limit)
                    else:
                        try:
                            fill_kwargs["gas_limit"] = int(c0.get("gas_limit"))  # type: ignore[arg-type]
                        except (TypeError, ValueError, AttributeError) as gas_err:
                            log_debug("Could not derive gas_limit from payload", exception=str(gas_err))
                    if storage_limit is not None:
                        fill_kwargs["storage_limit"] = int(storage_limit)
                    else:
                        try:
                            fill_kwargs["storage_limit"] = int(c0.get("storage_limit"))  # type: ignore[arg-type]
                        except (TypeError, ValueError, AttributeError) as storage_err:
                            log_debug("Could not derive storage_limit from payload", exception=str(storage_err))

                    if fill_kwargs and hasattr(op, "fill"):
                        op = op.fill(**fill_kwargs)

                # Sanity check: ensure we're injecting a delegation op to the intended baker.
                try:
                    payload = op.json_payload()
                    contents = []
                    if isinstance(payload, list) and payload:
                        contents = (payload[0] or {}).get("contents", []) or []
                    elif isinstance(payload, dict):
                        contents = payload.get("contents", []) or []
                    c0 = contents[0] if contents else {}
                    if c0.get("kind") != "delegation" or c0.get("delegate") != baker_address:
                        raise RuntimeError(
                            "Unexpected delegation operation payload. "
                            f"kind={c0.get('kind')!r} delegate={c0.get('delegate')!r}"
                        )
                except _OP_RETRY_EXCEPTIONS as e:
                    log_error("Delegation op sanity check failed", exception=e, baker=baker_address)
                    raise

                def _inject_delegate_once(
                    *,
                    fee_override: Optional[int] = None,
                    gas_override: Optional[int] = None,
                    storage_override: Optional[int] = None,
                ):
                    candidate = fresh_client.delegation(baker_address)
                    if fee_override is not None or gas_override is not None or storage_override is not None:
                        try:
                            candidate = candidate.autofill(
                                fee=int(fee_override) if fee_override is not None else None,
                                gas_limit=int(gas_override) if gas_override is not None else None,
                                storage_limit=int(storage_override) if storage_override is not None else None,
                            )
                        except TypeError:
                            candidate = candidate.autofill()
                    else:
                        candidate = candidate.autofill()

                    fill_kwargs: dict[str, int] = {}
                    if fee_override is not None:
                        fill_kwargs["fee"] = int(fee_override)
                    if gas_override is not None:
                        fill_kwargs["gas_limit"] = int(gas_override)
                    if storage_override is not None:
                        fill_kwargs["storage_limit"] = int(storage_override)
                    if fill_kwargs and hasattr(candidate, "fill"):
                        candidate = candidate.fill(**fill_kwargs)

                    candidate = candidate.sign()
                    return candidate.inject()

                # Sign and inject - trust autofill() to have set everything correctly.
                try:
                    op = op.sign()
                    result = op.inject()
                except _OP_RETRY_EXCEPTIONS as inject_err:
                    if not _is_gas_exhausted_error(inject_err):
                        raise
                    log_warning(
                        "Gas exhausted on delegation; retrying with pure autofill",
                        exception=inject_err,
                        rpc=rpc,
                        overrides_used=overrides_used,
                    )
                    try:
                        result = _inject_delegate_once()
                    except _OP_RETRY_EXCEPTIONS as autofill_err:
                        if not _is_gas_exhausted_error(autofill_err):
                            raise
                        # Last-resort envelope for delegation when stake-related side effects
                        # make simulation severely underestimate gas.
                        safe_gas = max(int(gas_limit or 0), 1_000_000)
                        # Tezos minimal fee scales with gas; keep this safely above the
                        # minimum for the high-gas fallback to avoid fee-related rejections.
                        safe_fee = max(int(fee_mutez or 0), 120_000)
                        safe_storage = max(int(storage_limit or 0), 0)
                        log_warning(
                            "Gas exhausted on delegation with pure autofill; retrying with conservative safety overrides",
                            exception=autofill_err,
                            rpc=rpc,
                            fee_mutez=safe_fee,
                            gas_limit=safe_gas,
                            storage_limit=safe_storage,
                        )
                        result = _inject_delegate_once(
                            fee_override=safe_fee,
                            gas_override=safe_gas,
                            storage_override=safe_storage,
                        )

                # Normalize result
                if isinstance(result, dict):
                    return result.get("hash", str(result))
                return str(result)

            except _OP_RETRY_EXCEPTIONS as e:
                last_error = e
                # Check if it's a counter error and we have retries left
                if _is_counter_sync_error(e) and attempt < max_retries:
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
    except _OP_RETRY_EXCEPTIONS as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal first (also with retry logic)
        log_warning("Wallet not revealed. Attempting reveal operation first...")

        def _inject_reveal_with_retry(max_retries: int = 3):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    # Wait before retry
                    if attempt > 0:
                        settling_time = 3.0
                        log_debug(f"Waiting {settling_time}s before reveal retry {attempt + 1}")
                        time.sleep(settling_time)

                    # Create fresh client with NO shared state
                    # pytezos uses `shell` keyword for RPC URL; this is not subprocess shell execution.
                    fresh_client = pytezos.using(shell=rpc, key=key)  # nosec B604

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
                except _OP_RETRY_EXCEPTIONS as e:
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
        except _OP_RETRY_EXCEPTIONS as rev_e:
            raise RuntimeError(
                f"Failed to reveal wallet public key. "
                f"This wallet has never been used before and needs to reveal its public key first. "
                f"Error: {rev_e}"
            ) from rev_e

        # Wait longer for reveal to propagate through the network
        log_info(f"Reveal successful ({reveal_oph}), waiting 8s for network propagation")
        time.sleep(8)

        # Retry delegation with fresh client after reveal
        log_info("Reveal complete. Retrying delegation...")
        try:
            return _inject_with_retry()
        except _OP_RETRY_EXCEPTIONS as del_e:
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
    rpc = normalize_rpc_url(rpc)
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
        log_warning(f"⚠️ Wallet {source_address[:10]}... is not revealed. Will attempt reveal operation first.")
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
                    log_debug(f"Waiting {settling_time}s for blockchain to settle before retry {attempt + 1}")
                    time.sleep(settling_time)

                # Read counter from RPC (FRESH on each retry)
                try:
                    rpc_counter = get_counter(rpc, source_address) - 1  # get_counter already adds +1
                    log_debug(f"[Attempt {attempt + 1}] RPC counter for {source_address[:10]}: {rpc_counter}")
                    counter_to_use = rpc_counter + 1
                    log_debug(f"[Attempt {attempt + 1}] Will use counter: {counter_to_use}")
                except _RPC_IO_EXCEPTIONS + (RuntimeError, ValueError, TypeError, AttributeError) as counter_err:
                    log_error(f"Failed to read counter from RPC", exception=counter_err)
                    raise

                # Check mempool for pending ops
                try:
                    pending_info = check_pending_operations(rpc, source_address)
                    if pending_info and pending_info.get('has_pending'):
                        log_warning(f"⚠️ WARNING: {pending_info.get('pending_count', 0)} pending ops in mempool")
                except _RPC_IO_EXCEPTIONS + (RuntimeError, ValueError, TypeError, AttributeError) as pending_err:
                    log_debug("Could not read mempool pending ops", exception=str(pending_err))

                # Create completely fresh client with NO shared state
                client = get_client(rpc, key=key)

                # ============================================================
                # PRUEBA 0: Verificar que key corresponde al source
                # ============================================================
                key_pkh = key.public_key_hash()
                log_debug(f"[DEBUG] source_address: {source_address}")
                log_debug(f"[DEBUG] key.public_key_hash(): {key_pkh}")
                if source_address != key_pkh:
                    raise RuntimeError(f"KEY MISMATCH! source={source_address} but key.pkh={key_pkh}")
                log_debug(f"[DEBUG] ✅ Key matches source address")

                # Get branch from head block
                try:
                    branch = client.shell.head.hash()
                    log_debug(f"[Attempt {attempt + 1}] Got branch: {branch}")
                except _RPC_IO_EXCEPTIONS + (RuntimeError, ValueError, TypeError, AttributeError) as branch_err:
                    log_error(f"Failed to get branch", exception=branch_err)
                    raise

                def _forge_and_inject(op_contents: dict, *, label: str) -> str:
                    log_debug(f"[Attempt {attempt + 1}] Operation contents ({label}):")
                    log_debug(f"  - kind: {op_contents.get('kind')}")
                    log_debug(f"  - counter: {counter_to_use}")
                    log_debug(f"  - gas_limit: {DEFAULT_STAKE_GAS}")
                    log_debug(f"  - storage_limit: {DEFAULT_STAKE_STORAGE}")
                    log_debug(f"  - fee: {DEFAULT_STAKE_FEE} mutez")
                    log_debug(f"  - amount: {amount_mutez} mutez")

                    forge_payload = {"branch": branch, "contents": [op_contents]}
                    log_debug(f"[Attempt {attempt + 1}] Requesting forge from RPC ({label})...")

                    forge_url = f"{rpc}/chains/main/blocks/head/helpers/forge/operations"
                    forge_response = requests.post(
                        forge_url,
                        json=forge_payload,
                        headers={'content-type': 'application/json'},
                        timeout=30
                    )

                    if forge_response.status_code != 200:
                        raise RuntimeError(f"RPC forge failed ({label}): {forge_response.status_code} - {forge_response.text}")

                    rpc_forged_hex = forge_response.text.strip().strip('"')
                    log_debug(f"[Attempt {attempt + 1}] RPC forged bytes ({label}): {rpc_forged_hex}")

                    log_debug(f"[Attempt {attempt + 1}] Signing RPC-forged bytes ({label})...")
                    result = sign_and_inject_from_rpc_forge(rpc, key, rpc_forged_hex)
                    log_info(f"[Attempt {attempt + 1}] ✅ Inject successful ({label})!")
                    return result if not isinstance(result, dict) else result.get("hash", str(result))

                log_debug(f"[Attempt {attempt + 1}] Building stake op: {amount_xtz} XTZ")

                stake_op = {
                    'kind': 'stake',
                    'source': source_address,
                    'fee': str(DEFAULT_STAKE_FEE),
                    'counter': str(counter_to_use),
                    'gas_limit': str(DEFAULT_STAKE_GAS),
                    'storage_limit': str(DEFAULT_STAKE_STORAGE),
                    'amount': str(amount_mutez),
                }

                legacy_op = {
                    'kind': 'transaction',
                    'source': source_address,
                    'destination': source_address,
                    'fee': str(DEFAULT_STAKE_FEE),
                    'counter': str(counter_to_use),
                    'gas_limit': str(DEFAULT_STAKE_GAS),
                    'storage_limit': str(DEFAULT_STAKE_STORAGE),
                    'amount': str(amount_mutez),
                    'parameters': {'entrypoint': 'stake', 'value': {'prim': 'Unit'}},
                }

                try:
                    result = _forge_and_inject(legacy_op, label="stake-legacy")
                except _OP_RETRY_EXCEPTIONS as legacy_err:
                    log_warning("Legacy stake transaction failed, trying stake op", exception=legacy_err)
                    try:
                        result = _forge_and_inject(stake_op, label="stake-op")
                    except _OP_RETRY_EXCEPTIONS as stake_err:
                        if _is_unsupported_manager_op(stake_err):
                            raise RuntimeError(
                                "RPC/protocol does not support stake operations on this network."
                            ) from stake_err
                        raise

                return str(result)

            except _OP_RETRY_EXCEPTIONS as e:
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
    except _OP_RETRY_EXCEPTIONS as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal first
        log_warning("Wallet not revealed. Attempting reveal operation first...")

        try:
            reveal_oph = _inject_reveal_with_counter_retry(
                rpc,
                key,
                is_counter_error=_is_counter_sync_error,
            )
        except _OP_RETRY_EXCEPTIONS as rev_e:
            raise RuntimeError(
                f"Failed to reveal wallet public key. "
                f"This wallet has never been used before and needs to reveal its public key first. "
                f"Error: {rev_e}"
            ) from rev_e

        log_info(f"Reveal successful ({reveal_oph}), waiting 8s for network propagation")
        time.sleep(8)

        log_info("Reveal complete. Retrying stake...")
        try:
            return _inject_with_retry()
        except _OP_RETRY_EXCEPTIONS as stake_e:
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
    rpc = normalize_rpc_url(rpc)
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
        log_warning(f"⚠️ Wallet {source_address[:10]}... is not revealed. Will attempt reveal operation first.")
        # Note: We don't raise here - we let the normal flow handle the reveal

    # Convert XTZ to mutez for transaction amount
    amount_mutez = xtz_to_mutez(amount_xtz)

    # Unstaking defaults - same as staking
    # Use provided values or defaults
    DEFAULT_UNSTAKE_FEE = fee_mutez if fee_mutez is not None else 8000       # ~0.008 XTZ (higher for safety)
    DEFAULT_UNSTAKE_GAS = gas_limit if gas_limit is not None else 30000      # Conservative: 30k gas for unstaking
    DEFAULT_UNSTAKE_STORAGE = storage_limit if storage_limit is not None else 0  # Unstaking doesn't need storage

    def _inject_with_retry(max_retries: int = 3):
        """Build, autofill, sign, and inject with counter error retry logic."""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # On retry attempts, wait for blockchain to settle
                if attempt > 0:
                    settling_time = 3.0
                    log_debug(f"Waiting {settling_time}s for blockchain to settle before retry {attempt + 1}")
                    time.sleep(settling_time)

                # Read counter from RPC (FRESH on each retry)
                try:
                    rpc_counter = get_counter(rpc, source_address) - 1  # get_counter already adds +1
                    log_debug(f"[Attempt {attempt + 1}] RPC counter for {source_address[:10]}: {rpc_counter}")
                    counter_to_use = rpc_counter + 1
                    log_debug(f"[Attempt {attempt + 1}] Will use counter: {counter_to_use}")
                except _RPC_IO_EXCEPTIONS + (RuntimeError, ValueError, TypeError, AttributeError) as counter_err:
                    log_error(f"Failed to read counter from RPC", exception=counter_err)
                    raise

                # Check mempool for pending ops
                try:
                    pending_info = check_pending_operations(rpc, source_address)
                    if pending_info and pending_info.get('has_pending'):
                        log_warning(f"⚠️ WARNING: {pending_info.get('pending_count', 0)} pending ops in mempool")
                except _RPC_IO_EXCEPTIONS + (RuntimeError, ValueError, TypeError, AttributeError) as pending_err:
                    log_debug("Could not read mempool pending ops", exception=str(pending_err))

                # Create completely fresh client with NO shared state
                client = get_client(rpc, key=key)

                # Get branch from head block
                try:
                    branch = client.shell.head.hash()
                    log_debug(f"[Attempt {attempt + 1}] Got branch: {branch}")
                except _RPC_IO_EXCEPTIONS + (RuntimeError, ValueError, TypeError, AttributeError) as branch_err:
                    log_error(f"Failed to get branch", exception=branch_err)
                    raise

                def _forge_and_inject(op_contents: dict, *, label: str) -> str:
                    log_debug(f"[Attempt {attempt + 1}] Operation contents ({label}):")
                    log_debug(f"  - kind: {op_contents.get('kind')}")
                    log_debug(f"  - counter: {counter_to_use}")
                    log_debug(f"  - gas_limit: {DEFAULT_UNSTAKE_GAS}")
                    log_debug(f"  - storage_limit: {DEFAULT_UNSTAKE_STORAGE}")
                    log_debug(f"  - fee: {DEFAULT_UNSTAKE_FEE} mutez")
                    log_debug(f"  - amount: {amount_mutez} mutez")

                    forge_payload = {"branch": branch, "contents": [op_contents]}
                    log_debug(f"[Attempt {attempt + 1}] Requesting forge from RPC ({label})...")

                    forge_url = f"{rpc}/chains/main/blocks/head/helpers/forge/operations"
                    forge_response = requests.post(
                        forge_url,
                        json=forge_payload,
                        headers={'content-type': 'application/json'},
                        timeout=30
                    )

                    if forge_response.status_code != 200:
                        raise RuntimeError(f"RPC forge failed ({label}): {forge_response.status_code} - {forge_response.text}")

                    rpc_forged_hex = forge_response.text.strip().strip('"')
                    log_debug(f"[Attempt {attempt + 1}] RPC forged bytes ({label}): {rpc_forged_hex}")

                    log_debug(f"[Attempt {attempt + 1}] Signing RPC-forged bytes ({label})...")
                    result = sign_and_inject_from_rpc_forge(rpc, key, rpc_forged_hex)
                    log_info(f"[Attempt {attempt + 1}] ✅ Inject successful ({label})!")
                    return result if not isinstance(result, dict) else result.get("hash", str(result))

                log_debug(f"[Attempt {attempt + 1}] Building unstake op: {amount_xtz} XTZ")

                unstake_op = {
                    'kind': 'unstake',
                    'source': source_address,
                    'fee': str(DEFAULT_UNSTAKE_FEE),
                    'counter': str(counter_to_use),
                    'gas_limit': str(DEFAULT_UNSTAKE_GAS),
                    'storage_limit': str(DEFAULT_UNSTAKE_STORAGE),
                    'amount': str(amount_mutez),
                }

                legacy_op = {
                    'kind': 'transaction',
                    'source': source_address,
                    'destination': source_address,
                    'fee': str(DEFAULT_UNSTAKE_FEE),
                    'counter': str(counter_to_use),
                    'gas_limit': str(DEFAULT_UNSTAKE_GAS),
                    'storage_limit': str(DEFAULT_UNSTAKE_STORAGE),
                    'amount': str(amount_mutez),
                    'parameters': {'entrypoint': 'unstake', 'value': {'prim': 'Unit'}},
                }

                try:
                    result = _forge_and_inject(legacy_op, label="unstake-legacy")
                except _OP_RETRY_EXCEPTIONS as legacy_err:
                    log_warning("Legacy unstake transaction failed, trying unstake op", exception=legacy_err)
                    try:
                        result = _forge_and_inject(unstake_op, label="unstake-op")
                    except _OP_RETRY_EXCEPTIONS as unstake_err:
                        if _is_unsupported_manager_op(unstake_err):
                            raise RuntimeError(
                                "RPC/protocol does not support unstake operations on this network."
                            ) from unstake_err
                        raise

                return str(result)

            except _OP_RETRY_EXCEPTIONS as e:
                last_error = e
                if _is_counter_sync_error(e) and attempt < max_retries:
                    # Conservative backoff for counter synchronization
                    wait_time = 5.0 * (attempt + 1)  # 5s, 10s, 15s
                    log_error(f"Counter error on unstake attempt {attempt + 1}, waiting {wait_time}s", exception=e)
                    time.sleep(wait_time)
                    continue
                else:
                    raise last_error

    try:
        return _inject_with_retry()
    except _OP_RETRY_EXCEPTIONS as e:
        if not _contains_unrevealed_key(e):
            raise

        # Reveal first
        log_warning("Wallet not revealed. Attempting reveal operation first...")

        try:
            reveal_oph = _inject_reveal_with_counter_retry(
                rpc,
                key,
                is_counter_error=_is_counter_sync_error,
            )
        except _OP_RETRY_EXCEPTIONS as rev_e:
            raise RuntimeError(
                f"Failed to reveal wallet public key. "
                f"This wallet has never been used before and needs to reveal its public key first. "
                f"Error: {rev_e}"
            ) from rev_e

        log_info(f"Reveal successful ({reveal_oph}), waiting 8s for network propagation")
        time.sleep(8)

        try:
            return _inject_with_retry()
        except _OP_RETRY_EXCEPTIONS as unstake_e:
            raise RuntimeError(f"Unstake failed after reveal ({reveal_oph}): {unstake_e}") from unstake_e
