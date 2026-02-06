"""Reusable input and text rendering helpers for the Textual UI."""

from __future__ import annotations


_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def filter_amount_input(value: str, *, max_decimals: int = 6) -> str:
    """Keep only a valid positive decimal shape for XTZ amount fields."""
    if value is None:
        return ""
    raw = str(value)
    if raw == "":
        return ""
    out_chars: list[str] = []
    dot_seen = False
    for ch in raw:
        if ch.isdigit():
            out_chars.append(ch)
        elif ch == "." and not dot_seen:
            out_chars.append(ch)
            dot_seen = True
    filtered = "".join(out_chars)
    if not filtered:
        return ""
    if filtered.startswith("."):
        filtered = "0" + filtered
    if "." in filtered:
        left, right = filtered.split(".", 1)
        filtered = left + "." + right[:max_decimals]
    return filtered


def filter_base58_input(value: str) -> str:
    if value is None:
        return ""
    raw = str(value)
    return "".join(ch for ch in raw if ch in _BASE58_ALPHABET)


def filter_digits_input(value: str) -> str:
    if value is None:
        return ""
    raw = str(value)
    return "".join(ch for ch in raw if ch.isdigit())


def shimmer_text(text: str, offset: int, span: int = 2, *, pingpong: bool = False) -> str:
    if not text:
        return text
    n = len(text)
    if pingpong and n > 1:
        period = 2 * (n - 1)
        pos = offset % period
        if pos >= n:
            pos = period - pos
        start = pos
    else:
        start = offset % n
    end = start + max(1, span)
    parts: list[str] = []
    for i, ch in enumerate(text):
        if pingpong:
            in_span = start <= i < min(end, n)
        else:
            in_span = (start <= i < end) or (end > n and i < (end - n))
        if in_span:
            parts.append(f"[reverse]{ch}[/reverse]")
        else:
            parts.append(ch)
    return "".join(parts)


def filter_mnemonic_input(value: str) -> str:
    if value is None:
        return ""
    raw = str(value).lower()
    return "".join(ch for ch in raw if ch.isalpha() or ch.isspace())


def filter_derivation_path(value: str) -> str:
    if value is None:
        return ""
    raw = str(value)
    allowed = set("mM/0123456789'")
    filtered = "".join(ch for ch in raw if ch in allowed)
    return filtered.replace("M", "m")
