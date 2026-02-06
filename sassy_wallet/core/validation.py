"""
Input validation module for Tezos wallet.

Provides robust validation for all user inputs including addresses,
amounts, and transaction parameters.
"""

from decimal import Decimal, InvalidOperation
import re
from typing import Tuple, Optional
from urllib.parse import urlsplit, urlunsplit

from pytezos.crypto.encoding import base58_decode


# Tezos address patterns with full validation
_TZ1_RE = re.compile(r"^tz1[1-9A-HJ-NP-Za-km-z]{33}$")
_TZ2_RE = re.compile(r"^tz2[1-9A-HJ-NP-Za-km-z]{33}$")
_TZ3_RE = re.compile(r"^tz3[1-9A-HJ-NP-Za-km-z]{33}$")
_TZ4_RE = re.compile(r"^tz4[1-9A-HJ-NP-Za-km-z]{33}$")
_KT1_RE = re.compile(r"^KT1[1-9A-HJ-NP-Za-km-z]{33}$")

# Combined pattern for any Tezos address
_ALL_TZ_RE = re.compile(r"^tz[1-4][1-9A-HJ-NP-Za-km-z]{33}$")

# Numeric patterns
_DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")
_INT_RE = re.compile(r"^-?\d+$")
_TZ_PATTERNS = {
    "tz1": _TZ1_RE,
    "tz2": _TZ2_RE,
    "tz3": _TZ3_RE,
    "tz4": _TZ4_RE,
}
_BASE58_DECODE_EXCEPTIONS = (ValueError, TypeError)
_URL_CONTROL_CHARS = ("\r", "\n", "\t")


def _has_valid_base58_checksum(addr: str) -> bool:
    try:
        base58_decode(addr.encode("utf-8"))
        return True
    except _BASE58_DECODE_EXCEPTIONS:
        return False


def is_valid_tz_address(addr: str) -> bool:
    """
    Check if a string is a valid Tezos tz1/tz2/tz3/tz4 address.

    Args:
        addr: Address string to validate

    Returns:
        True if valid tz address, False otherwise
    """
    if not addr:
        return False
    addr = addr.strip()
    return bool(_ALL_TZ_RE.match(addr))


def is_valid_kt1_address(addr: str) -> bool:
    """
    Check if a string is a valid Tezos KT1 address.

    Args:
        addr: Address string to validate

    Returns:
        True if valid KT1 address, False otherwise
    """
    if not addr:
        return False
    addr = addr.strip()
    return bool(_KT1_RE.match(addr))


def validate_tezos_address(addr: str, allow_kt1: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate a Tezos address and return detailed error message if invalid.

    Args:
        addr: Address string to validate
        allow_kt1: If False, only tz addresses are valid (for baker addresses)

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, None)
        If invalid: (False, "error description")
    """
    if not addr:
        return False, "Address cannot be empty"

    addr = addr.strip()

    # Check length first (all Tezos addresses are 36 characters)
    if len(addr) != 36:
        return False, f"Invalid address length: {len(addr)} (must be 36 characters)"

    # Check tz1..tz4 prefixes and base58 checksum.
    for prefix, pattern in _TZ_PATTERNS.items():
        if not addr.startswith(prefix):
            continue
        if not pattern.match(addr):
            return False, f"Invalid {prefix} address format (check for invalid characters)"
        if not _has_valid_base58_checksum(addr):
            return False, f"🥐 Wrong dough — checksum doesn't rise ({prefix})"
        return True, None

    if addr.startswith("KT1"):
        if not allow_kt1:
            return False, "KT1 addresses are not valid for this operation (must use tz1/tz2/tz3/tz4)"
        if not _KT1_RE.match(addr):
            return False, "Invalid KT1 address format (check for invalid characters)"
        if not _has_valid_base58_checksum(addr):
            return False, "🥐 Wrong dough — checksum doesn't rise (KT1)"
        return True, None

    valid_prefixes = "tz1, tz2, tz3, tz4" + (", KT1" if allow_kt1 else "")
    return False, f"Invalid address prefix (must start with {valid_prefixes})"


def validate_baker_address(addr: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a baker address (must be tz1/tz2/tz3/tz4, not KT1).

    Args:
        addr: Address string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    return validate_tezos_address(addr, allow_kt1=False)


def validate_amount(amount_str: str, min_value: Optional[Decimal] = None,
                   max_value: Optional[Decimal] = None) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Validate an amount string (for XTZ amounts).

    Args:
        amount_str: Amount string to validate
        min_value: Optional minimum value (exclusive)
        max_value: Optional maximum value (inclusive)

    Returns:
        Tuple of (is_valid, error_message, parsed_amount)
        If valid: (True, None, Decimal(amount))
        If invalid: (False, "error description", None)
    """
    if not amount_str:
        return False, "Amount cannot be empty", None

    amount_str = amount_str.strip()

    # Check if it looks like a number
    if not _DECIMAL_RE.match(amount_str):
        return False, "Invalid number format (use digits and optional decimal point)", None

    # Try to parse as Decimal
    try:
        amount = Decimal(amount_str)
    except (InvalidOperation, ValueError) as e:
        return False, f"Invalid decimal number: {str(e)}", None

    # Check minimum value (exclusive)
    if min_value is not None and amount <= min_value:
        return False, f"Amount must be greater than {min_value}", None

    # Check maximum value (inclusive)
    if max_value is not None and amount > max_value:
        return False, f"Amount must not exceed {max_value}", None

    return True, None, amount


def validate_fee(fee_str: str) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Validate a fee amount string (in XTZ).

    Args:
        fee_str: Fee string to validate

    Returns:
        Tuple of (is_valid, error_message, parsed_fee)
    """
    if not fee_str:
        return False, "Fee cannot be empty", None

    fee_str = fee_str.strip()

    if not _DECIMAL_RE.match(fee_str):
        return False, "Invalid fee format (use digits and optional decimal point)", None

    try:
        fee = Decimal(fee_str)
    except (InvalidOperation, ValueError) as e:
        return False, f"Invalid decimal number: {str(e)}", None

    if fee < 0:
        return False, "Fee must be non-negative", None

    # Reasonable maximum fee check (10 XTZ)
    if fee > Decimal("10"):
        return False, "Fee seems unusually high (maximum 10 XTZ)", None

    return True, None, fee


def validate_gas_limit(gas_str: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate a gas limit string.

    Args:
        gas_str: Gas limit string to validate

    Returns:
        Tuple of (is_valid, error_message, parsed_gas)
    """
    if not gas_str:
        return False, "Gas limit cannot be empty", None

    gas_str = gas_str.strip()

    if not _INT_RE.match(gas_str):
        return False, "Gas limit must be a whole number", None

    try:
        gas = int(gas_str)
    except (ValueError, OverflowError) as e:
        return False, f"Invalid integer: {str(e)}", None

    if gas < 0:
        return False, "Gas limit must be non-negative", None

    # Reasonable maximum check (1,000,000)
    if gas > 1_000_000:
        return False, "Gas limit seems unusually high (maximum 1,000,000)", None

    return True, None, gas


def validate_storage_limit(storage_str: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate a storage limit string.

    Args:
        storage_str: Storage limit string to validate

    Returns:
        Tuple of (is_valid, error_message, parsed_storage)
    """
    if not storage_str:
        return False, "Storage limit cannot be empty", None

    storage_str = storage_str.strip()

    if not _INT_RE.match(storage_str):
        return False, "Storage limit must be a whole number", None

    try:
        storage = int(storage_str)
    except (ValueError, OverflowError) as e:
        return False, f"Invalid integer: {str(e)}", None

    if storage < 0:
        return False, "Storage limit must be non-negative", None

    # Reasonable maximum check (10,000)
    if storage > 10_000:
        return False, "Storage limit seems unusually high (maximum 10,000)", None

    return True, None, storage


def sanitize_input(value: str) -> str:
    """
    Sanitize user input by removing dangerous characters and excessive whitespace.

    Args:
        value: Input string to sanitize

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    # Strip leading/trailing whitespace
    value = value.strip()

    # Remove null bytes and control characters (except newlines which will be stripped anyway)
    value = ''.join(char for char in value if ord(char) >= 32 or char == '\n')

    # Replace multiple spaces with single space
    value = ' '.join(value.split())

    return value


def get_address_type(addr: str) -> Optional[str]:
    """
    Get the type of a Tezos address.

    Args:
        addr: Address string

    Returns:
        One of: "tz1", "tz2", "tz3", "tz4", "KT1", or None if invalid
    """
    if not addr:
        return None

    addr = addr.strip()

    if _TZ1_RE.match(addr):
        return "tz1"
    elif _TZ2_RE.match(addr):
        return "tz2"
    elif _TZ3_RE.match(addr):
        return "tz3"
    elif _TZ4_RE.match(addr):
        return "tz4"
    elif _KT1_RE.match(addr):
        return "KT1"

    return None


def normalize_https_url(
    url: str,
    *,
    allow_query: bool = True,
    allow_fragment: bool = False,
) -> str:
    """
    Validate and normalize an HTTPS URL.

    - Only `https://` is allowed.
    - URL credentials are rejected.
    - Query/fragment can be restricted by callers.
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("URL cannot be empty")
    if any(ch in raw for ch in _URL_CONTROL_CHARS):
        raise ValueError("URL contains control characters")

    parsed = urlsplit(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme != "https":
        raise ValueError("Only HTTPS URLs are allowed")
    if not parsed.netloc or parsed.hostname is None:
        raise ValueError("URL host is required")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not allowed")
    if not allow_query and parsed.query:
        raise ValueError("URL query is not allowed")
    if not allow_fragment and parsed.fragment:
        raise ValueError("URL fragment is not allowed")

    query = parsed.query if allow_query else ""
    fragment = parsed.fragment if allow_fragment else ""
    return urlunsplit((scheme, parsed.netloc, parsed.path or "", query, fragment))


def normalize_rpc_url(rpc: str) -> str:
    """
    Validate and normalize an RPC base URL.

    RPC URLs must be HTTPS and cannot contain query/fragment components.
    Trailing slash is removed to avoid malformed URL joins.
    """
    normalized = normalize_https_url(rpc, allow_query=False, allow_fragment=False)
    parsed = urlsplit(normalized)
    path = (parsed.path or "").rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
