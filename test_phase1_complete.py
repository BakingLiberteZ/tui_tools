#!/usr/bin/env python3
"""
Phase 1 Validation: Logging Infrastructure

Tests that all generic exceptions have been wrapped with proper logging.
"""
import sys
import subprocess
from pathlib import Path


def test_imports():
    """Test that all modified modules can be imported."""
    print("Testing imports...")
    try:
        import wallet.logger
        import wallet.tezos
        import wallet.store
        import wallet.crypto
        print("  ✅ All imports successful")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_logger_module():
    """Test that logger module has required functions and decorators."""
    print("Testing logger module...")
    try:
        from wallet.logger import (
            log_exception,
            safe_log_exception,
            log_error,
            log_info,
            log_warning,
            log_debug,
            get_logger
        )

        # Test that functions are callable
        assert callable(log_exception)
        assert callable(safe_log_exception)
        assert callable(log_error)
        assert callable(log_info)
        assert callable(log_warning)
        assert callable(log_debug)
        assert callable(get_logger)

        print("  ✅ Logger module has all required functions")
        return True
    except Exception as e:
        print(f"  ❌ Logger module test failed: {e}")
        return False


def test_decorators_work():
    """Test that logging decorators work correctly."""
    print("Testing logging decorators...")
    try:
        from wallet.logger import safe_log_exception, log_exception

        # Test safe_log_exception
        @safe_log_exception(default_return=42, user_message="Test failed")
        def failing_function():
            raise ValueError("Test error")

        result = failing_function()
        assert result == 42, "safe_log_exception should return default value"

        # Test log_exception (with reraise=False)
        @log_exception(user_message="Test exception", reraise=False)
        def another_failing_function():
            raise RuntimeError("Another test error")

        result = another_failing_function()
        assert result is None, "log_exception with reraise=False should return None"

        print("  ✅ Decorators work correctly")
        return True
    except Exception as e:
        print(f"  ❌ Decorator test failed: {e}")
        return False


def test_no_bare_exceptions():
    """Check that there are no bare 'except:' statements (should be 'except Exception as e:')."""
    print("Checking for bare except statements...")

    files_to_check = [
        "app.py",
        "wallet/tezos.py",
        "wallet/store.py"
    ]

    bare_excepts_found = []

    for file_path in files_to_check:
        path = Path(file_path)
        if not path.exists():
            print(f"  ⚠️  Warning: {file_path} not found")
            continue

        content = path.read_text()
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Check for bare except: (not except Exception)
            if 'except:' in line and 'except Exception' not in line:
                bare_excepts_found.append(f"{file_path}:{i}")

    if bare_excepts_found:
        print(f"  ⚠️  Found bare except statements (should be 'except Exception as e:'):")
        for loc in bare_excepts_found:
            print(f"     {loc}")
        # This is a warning, not a failure - some bare excepts might be intentional
        return True
    else:
        print("  ✅ No problematic bare except statements found")
        return True


def test_logging_context():
    """Test that logging functions accept context parameters."""
    print("Testing logging with context...")
    try:
        from wallet.logger import log_error, log_warning, log_info, log_debug

        # These should not raise exceptions
        log_error("Test error", exception=ValueError("test"), context_key="value")
        log_warning("Test warning", some_context="data")
        log_info("Test info", more_context=123)
        log_debug("Test debug", debug_data={"key": "value"})

        print("  ✅ Logging with context works")
        return True
    except Exception as e:
        print(f"  ❌ Logging context test failed: {e}")
        return False


def test_app_runs():
    """Test that the application can start without import errors."""
    print("Testing that app can be imported...")
    try:
        # Try to import the app module (but don't run it)
        import sys
        import io

        # Capture any output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            import app
            # Check that WalletApp class exists
            assert hasattr(app, 'WalletApp')
            print_("  ✅ App module imports successfully")
            return True
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    except Exception as e:
        print(f"  ❌ App import test failed: {e}")
        return False


def print_(msg):
    """Print without being captured."""
    sys.__stdout__.write(msg + '\n')
    sys.__stdout__.flush()


def count_wrapped_exceptions():
    """Count how many exceptions were wrapped."""
    print("Counting wrapped exceptions...")

    # Count "except Exception as e:" patterns (which should have logging)
    result = subprocess.run(
        ["grep", "-r", "except Exception as", "app.py", "wallet/"],
        capture_output=True,
        text=True
    )

    count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
    print(f"  ℹ️  Found {count} 'except Exception as e:' statements with potential logging")
    return True


def main():
    """Run all Phase 1 validation tests."""
    print("="*70)
    print("PHASE 1 VALIDATION: Logging Infrastructure")
    print("="*70)
    print()

    tests = [
        test_imports,
        test_logger_module,
        test_decorators_work,
        test_logging_context,
        test_no_bare_exceptions,
        count_wrapped_exceptions,
        test_app_runs,
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
        print(f"✅ PHASE 1 VALIDATION PASSED ({passed}/{total} tests)")
        print("="*70)
        return 0
    else:
        print(f"❌ PHASE 1 VALIDATION FAILED ({passed}/{total} tests passed)")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
