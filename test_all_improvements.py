#!/usr/bin/env python3
"""Comprehensive test suite for all improvements (Phase 1, 2, and 3)."""

from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app import (
    Config, format_xtz, format_relative_time, setup_logging
)
import logging
import os

def test_phase1_number_formatting():
    """Test Phase 1: Number formatting with thousands separators."""
    print("\n" + "=" * 70)
    print("PHASE 1: NUMBER FORMATTING")
    print("=" * 70)

    tests = [
        (Decimal("12345.678000"), "12,345.678"),
        (Decimal("1000.000000"), "1,000"),
        (Decimal("0.123456"), "0.123456"),
        (Decimal("999999.999999"), "999,999.999999"),
    ]

    all_passed = True
    for amount, expected in tests:
        result = format_xtz(amount)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_passed = False
        print(f"  {status} format_xtz({amount}) = '{result}' (expected: '{expected}')")

    return all_passed

def test_phase1_config():
    """Test Phase 1: Config constants."""
    print("\n" + "=" * 70)
    print("PHASE 1: CONFIG CONSTANTS")
    print("=" * 70)

    checks = [
        ("RPC_TIMEOUT", Config.RPC_TIMEOUT, float),
        ("HISTORY_DEFAULT_LIMIT", Config.HISTORY_DEFAULT_LIMIT, int),
        ("RECENT_DESTINATIONS_MAX", Config.RECENT_DESTINATIONS_MAX, int),
    ]

    all_passed = True
    for name, value, expected_type in checks:
        is_correct = isinstance(value, expected_type)
        status = "✅" if is_correct else "❌"
        if not is_correct:
            all_passed = False
        print(f"  {status} Config.{name} = {value} (type: {type(value).__name__})")

    return all_passed

def test_phase2_logging():
    """Test Phase 2: Logging system."""
    print("\n" + "=" * 70)
    print("PHASE 2: LOGGING SYSTEM")
    print("=" * 70)

    try:
        setup_logging()
        logging.info("Test log message from test suite")

        log_exists = os.path.exists(Config.LOG_FILE)
        print(f"  {'✅' if log_exists else '❌'} Log file created: {Config.LOG_FILE}")

        # Check log file size
        if log_exists:
            size = os.path.getsize(Config.LOG_FILE)
            print(f"  ✅ Log file size: {size} bytes")

        return log_exists
    except Exception as e:
        print(f"  ❌ Logging setup failed: {e}")
        return False

def test_phase2_relative_time():
    """Test Phase 2: Relative time formatting."""
    print("\n" + "=" * 70)
    print("PHASE 2: RELATIVE TIME FORMATTING")
    print("=" * 70)

    # Create test timestamps
    now = datetime.now(timezone.utc)

    tests = [
        (now - timedelta(seconds=30), "just now"),
        (now - timedelta(minutes=5), "5 min ago"),
        (now - timedelta(hours=2), "2 hr ago"),
        (now - timedelta(days=3), "3 days ago"),
    ]

    all_passed = True
    for dt, expected_pattern in tests:
        ts_iso = dt.isoformat()
        result = format_relative_time(ts_iso)
        # Check if result contains the expected pattern
        is_correct = expected_pattern in result or result == expected_pattern
        status = "✅" if is_correct else "❌"
        if not is_correct:
            all_passed = False
        print(f"  {status} {expected_pattern} → '{result}'")

    return all_passed

def test_phase2_balance_cache():
    """Test Phase 2: Balance cache constants."""
    print("\n" + "=" * 70)
    print("PHASE 2: BALANCE CACHE")
    print("=" * 70)

    has_cache = hasattr(Config, 'BALANCE_CACHE_SECONDS')
    cache_value = Config.BALANCE_CACHE_SECONDS if has_cache else None

    print(f"  {'✅' if has_cache else '❌'} Config.BALANCE_CACHE_SECONDS exists")
    if has_cache:
        print(f"  ✅ Cache duration: {cache_value} seconds")

    return has_cache

def test_phase3_auto_refresh():
    """Test Phase 3: Auto-refresh constants."""
    print("\n" + "=" * 70)
    print("PHASE 3: AUTO-REFRESH")
    print("=" * 70)

    has_auto_refresh = hasattr(Config, 'AUTO_REFRESH_INTERVAL_SECONDS')
    interval = Config.AUTO_REFRESH_INTERVAL_SECONDS if has_auto_refresh else None

    print(f"  {'✅' if has_auto_refresh else '❌'} Config.AUTO_REFRESH_INTERVAL_SECONDS exists")
    if has_auto_refresh:
        print(f"  ✅ Refresh interval: {interval} seconds")

    return has_auto_refresh

def test_feature_checklist():
    """Check all implemented features."""
    print("\n" + "=" * 70)
    print("FEATURE CHECKLIST")
    print("=" * 70)

    features = [
        ("Number formatting", "format_xtz"),
        ("Config constants", "Config"),
        ("Relative time", "format_relative_time"),
        ("Logging", "setup_logging"),
        ("Confirm modal", "ConfirmScreen"),
        ("Address detail modal", "AddressDetailScreen"),
    ]

    all_exist = True
    for name, symbol in features:
        exists = symbol in globals() or symbol in dir()
        status = "✅" if exists else "❌"
        if not exists:
            all_exist = False
        print(f"  {status} {name} ({symbol})")

    return all_exist

def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🧪 COMPREHENSIVE TEST SUITE - ALL IMPROVEMENTS")
    print("=" * 70)

    results = [
        ("Phase 1: Number Formatting", test_phase1_number_formatting()),
        ("Phase 1: Config Constants", test_phase1_config()),
        ("Phase 2: Logging System", test_phase2_logging()),
        ("Phase 2: Relative Time", test_phase2_relative_time()),
        ("Phase 2: Balance Cache", test_phase2_balance_cache()),
        ("Phase 3: Auto-Refresh", test_phase3_auto_refresh()),
        ("Feature Checklist", test_feature_checklist()),
    ]

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")

    all_passed = all(passed for _, passed in results)
    print(f"\n{'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("MANUAL TESTING CHECKLIST")
    print("=" * 70)
    print("""
  Phase 1:
    □ Number formatting displays correctly in balance, fees, history
    □ Config constants are being used throughout the app
    □ Copy address feedback shows green success message
    □ Elapsed time shows after 5 seconds in long operations

  Phase 2:
    □ Balance check validates before send
    □ Balance cache reduces RPC calls
    □ Relative time shows in transaction history
    □ Clipboard fallback shows address when copy fails

  Phase 3:
    □ Delete wallet removes wallet with confirmation
    □ Backup creates timestamped JSON file in data/backups/
    □ Show address modal displays full address
    □ Export history creates CSV in data/exports/
    □ Auto-refresh toggles on/off with Ctrl+R

  Keyboard shortcuts to test:
    - Delete: Delete selected wallet
    - b: Backup wallets
    - a: Show full address
    - e: Export history to CSV
    - Ctrl+R: Toggle auto-refresh
""")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())
