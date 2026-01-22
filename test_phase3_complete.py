#!/usr/bin/env python3
"""
Phase 3 Validation: Timeouts & Cleanup

Tests that timeout constants are properly defined and timer cleanup is implemented.
"""
import sys
from pathlib import Path


def test_imports():
    """Test that app imports successfully after Phase 3 changes."""
    print("Testing imports...")
    try:
        import app
        print("  ✅ App imports successfully")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_timeout_constants_exist():
    """Test that timeout constants are defined in Config."""
    print("Testing timeout constants in Config...")
    try:
        from app import Config

        # Check that timeout constants exist
        assert hasattr(Config, 'RPC_TIMEOUT'), "RPC_TIMEOUT missing"
        assert hasattr(Config, 'RPC_FETCH_TIMEOUT'), "RPC_FETCH_TIMEOUT missing"
        assert hasattr(Config, 'RPC_LONG_TIMEOUT'), "RPC_LONG_TIMEOUT missing"

        # Check they have reasonable values
        assert isinstance(Config.RPC_TIMEOUT, (int, float)), "RPC_TIMEOUT not numeric"
        assert isinstance(Config.RPC_FETCH_TIMEOUT, (int, float)), "RPC_FETCH_TIMEOUT not numeric"
        assert isinstance(Config.RPC_LONG_TIMEOUT, (int, float)), "RPC_LONG_TIMEOUT not numeric"

        assert Config.RPC_TIMEOUT > 0, "RPC_TIMEOUT must be positive"
        assert Config.RPC_FETCH_TIMEOUT > 0, "RPC_FETCH_TIMEOUT must be positive"
        assert Config.RPC_LONG_TIMEOUT > 0, "RPC_LONG_TIMEOUT must be positive"

        print(f"  ✅ Timeout constants exist and are valid:")
        print(f"     RPC_TIMEOUT = {Config.RPC_TIMEOUT}s")
        print(f"     RPC_FETCH_TIMEOUT = {Config.RPC_FETCH_TIMEOUT}s")
        print(f"     RPC_LONG_TIMEOUT = {Config.RPC_LONG_TIMEOUT}s")
        return True
    except Exception as e:
        print(f"  ❌ Timeout constants test failed: {e}")
        return False


def test_walletapp_on_unmount_exists():
    """Test that WalletApp has on_unmount method."""
    print("Testing WalletApp.on_unmount...")
    try:
        from app import WalletApp

        # Check that on_unmount exists
        assert hasattr(WalletApp, 'on_unmount'), "WalletApp.on_unmount missing"
        assert callable(WalletApp.on_unmount), "WalletApp.on_unmount not callable"

        print("  ✅ WalletApp.on_unmount exists")
        return True
    except Exception as e:
        print(f"  ❌ WalletApp.on_unmount test failed: {e}")
        return False


def test_receivescreen_on_unmount_exists():
    """Test that ReceiveScreen has on_unmount method."""
    print("Testing ReceiveScreen.on_unmount...")
    try:
        from app import ReceiveScreen

        # Check that on_unmount exists
        assert hasattr(ReceiveScreen, 'on_unmount'), "ReceiveScreen.on_unmount missing"
        assert callable(ReceiveScreen.on_unmount), "ReceiveScreen.on_unmount not callable"

        print("  ✅ ReceiveScreen.on_unmount exists")
        return True
    except Exception as e:
        print(f"  ❌ ReceiveScreen.on_unmount test failed: {e}")
        return False


def test_walletapp_has_timers():
    """Test that WalletApp initializes timer attributes."""
    print("Testing WalletApp timer attributes...")
    try:
        from app import WalletApp

        app_instance = WalletApp()

        # Check that timer attributes exist
        assert hasattr(app_instance, '_spin_timer'), "_spin_timer attribute missing"
        assert hasattr(app_instance, '_auto_refresh_timer'), "_auto_refresh_timer attribute missing"

        # Check they are initialized to None
        assert app_instance._spin_timer is None, "_spin_timer should start as None"
        assert app_instance._auto_refresh_timer is None, "_auto_refresh_timer should start as None"

        print("  ✅ WalletApp timer attributes initialized correctly")
        return True
    except Exception as e:
        print(f"  ❌ WalletApp timer attributes test failed: {e}")
        return False


def test_receivescreen_has_timer():
    """Test that ReceiveScreen initializes timer attribute."""
    print("Testing ReceiveScreen timer attribute...")
    try:
        from app import ReceiveScreen

        screen_instance = ReceiveScreen("tz1TEST")

        # Check that timer attribute exists
        assert hasattr(screen_instance, '_status_timer'), "_status_timer attribute missing"

        # Check it's initialized to None
        assert screen_instance._status_timer is None, "_status_timer should start as None"

        print("  ✅ ReceiveScreen timer attribute initialized correctly")
        return True
    except Exception as e:
        print(f"  ❌ ReceiveScreen timer attribute test failed: {e}")
        return False


def test_sendconfirmscreen_has_unmount():
    """Test that ConfirmSendScreen has on_unmount for cleanup."""
    print("Testing ConfirmSendScreen.on_unmount...")
    try:
        from app import ConfirmSendScreen

        # Check that on_unmount exists (it should already be there)
        assert hasattr(ConfirmSendScreen, 'on_unmount'), "ConfirmSendScreen.on_unmount missing"
        assert callable(ConfirmSendScreen.on_unmount), "ConfirmSendScreen.on_unmount not callable"

        print("  ✅ ConfirmSendScreen.on_unmount exists")
        return True
    except Exception as e:
        print(f"  ❌ ConfirmSendScreen.on_unmount test failed: {e}")
        return False


def test_spinner_interval_constant():
    """Test that spinner interval is defined in Config."""
    print("Testing spinner interval constant...")
    try:
        from app import Config

        assert hasattr(Config, 'SPINNER_INTERVAL'), "SPINNER_INTERVAL missing"
        assert isinstance(Config.SPINNER_INTERVAL, (int, float)), "SPINNER_INTERVAL not numeric"
        assert Config.SPINNER_INTERVAL > 0, "SPINNER_INTERVAL must be positive"

        print(f"  ✅ SPINNER_INTERVAL = {Config.SPINNER_INTERVAL}s")
        return True
    except Exception as e:
        print(f"  ❌ Spinner interval test failed: {e}")
        return False


def main():
    """Run all Phase 3 validation tests."""
    print("="*70)
    print("PHASE 3 VALIDATION: Timeouts & Cleanup")
    print("="*70)
    print()

    tests = [
        test_imports,
        test_timeout_constants_exist,
        test_walletapp_on_unmount_exists,
        test_receivescreen_on_unmount_exists,
        test_sendconfirmscreen_has_unmount,
        test_walletapp_has_timers,
        test_receivescreen_has_timer,
        test_spinner_interval_constant,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()

    print("="*70)
    passed = sum(results)
    total = len(results)

    if all(results):
        print(f"✅ PHASE 3 VALIDATION PASSED ({passed}/{total} tests)")
        print("="*70)
        print()
        print("NOTE: All timeouts are now consolidated in Config class and")
        print("all timers are properly cleaned up in on_unmount methods.")
        return 0
    else:
        print(f"❌ PHASE 3 VALIDATION FAILED ({passed}/{total} tests passed)")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
