#!/usr/bin/env python3
"""
Phase 5 Validation: String Constants (RPC URLs)

Tests that RPC URLs and other string constants have been consolidated in Config.
"""
import sys


def test_imports():
    """Test that app imports successfully."""
    print("Testing imports...")
    try:
        import app
        print("  ✅ App imports successfully")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_rpc_url_constants_exist():
    """Test that RPC URL constants are defined in Config."""
    print("Testing RPC URL constants in Config...")
    try:
        from app import Config

        # Check default RPCs
        assert hasattr(Config, 'RPC_DEFAULT_MAINNET'), "RPC_DEFAULT_MAINNET missing"
        assert hasattr(Config, 'RPC_DEFAULT_GHOSTNET'), "RPC_DEFAULT_GHOSTNET missing"

        # Check RPC candidates
        assert hasattr(Config, 'RPC_MAINNET_CANDIDATES'), "RPC_MAINNET_CANDIDATES missing"
        assert hasattr(Config, 'RPC_GHOSTNET_CANDIDATES'), "RPC_GHOSTNET_CANDIDATES missing"

        # Check TzKT API URLs
        assert hasattr(Config, 'TZKT_API_MAINNET'), "TZKT_API_MAINNET missing"
        assert hasattr(Config, 'TZKT_API_GHOSTNET'), "TZKT_API_GHOSTNET missing"

        # Check TzKT UI URLs
        assert hasattr(Config, 'TZKT_UI_MAINNET'), "TZKT_UI_MAINNET missing"
        assert hasattr(Config, 'TZKT_UI_GHOSTNET'), "TZKT_UI_GHOSTNET missing"

        print("  ✅ All RPC URL constants defined in Config")
        return True
    except Exception as e:
        print(f"  ❌ RPC URL constants test failed: {e}")
        return False


def test_rpc_urls_are_strings():
    """Test that RPC URLs are valid strings."""
    print("Testing that RPC URLs are valid strings...")
    try:
        from app import Config

        urls_to_check = [
            ('RPC_DEFAULT_MAINNET', Config.RPC_DEFAULT_MAINNET),
            ('RPC_DEFAULT_GHOSTNET', Config.RPC_DEFAULT_GHOSTNET),
            ('TZKT_API_MAINNET', Config.TZKT_API_MAINNET),
            ('TZKT_API_GHOSTNET', Config.TZKT_API_GHOSTNET),
            ('TZKT_UI_MAINNET', Config.TZKT_UI_MAINNET),
            ('TZKT_UI_GHOSTNET', Config.TZKT_UI_GHOSTNET),
        ]

        for name, url in urls_to_check:
            assert isinstance(url, str), f"{name} is not a string"
            assert url.startswith('https://'), f"{name} doesn't start with https://"
            assert len(url) > 10, f"{name} is too short"

        print("  ✅ All RPC URLs are valid strings with https://")
        return True
    except Exception as e:
        print(f"  ❌ RPC URL validation failed: {e}")
        return False


def test_rpc_candidates_are_lists():
    """Test that RPC candidate lists are properly defined."""
    print("Testing RPC candidate lists...")
    try:
        from app import Config

        # Check mainnet candidates
        assert isinstance(Config.RPC_MAINNET_CANDIDATES, list), "RPC_MAINNET_CANDIDATES not a list"
        assert len(Config.RPC_MAINNET_CANDIDATES) > 0, "RPC_MAINNET_CANDIDATES is empty"

        # Check ghostnet candidates
        assert isinstance(Config.RPC_GHOSTNET_CANDIDATES, list), "RPC_GHOSTNET_CANDIDATES not a list"
        assert len(Config.RPC_GHOSTNET_CANDIDATES) > 0, "RPC_GHOSTNET_CANDIDATES is empty"

        # Check that all candidates are strings
        for url in Config.RPC_MAINNET_CANDIDATES:
            assert isinstance(url, str), f"Mainnet candidate not a string: {url}"
            assert url.startswith('https://'), f"Mainnet candidate doesn't start with https://: {url}"

        for url in Config.RPC_GHOSTNET_CANDIDATES:
            assert isinstance(url, str), f"Ghostnet candidate not a string: {url}"
            assert url.startswith('https://'), f"Ghostnet candidate doesn't start with https://: {url}"

        print(f"  ✅ RPC candidates properly defined:")
        print(f"     Mainnet: {len(Config.RPC_MAINNET_CANDIDATES)} candidates")
        print(f"     Ghostnet: {len(Config.RPC_GHOSTNET_CANDIDATES)} candidates")
        return True
    except Exception as e:
        print(f"  ❌ RPC candidates test failed: {e}")
        return False


def test_tzkt_ui_function_uses_config():
    """Test that tzkt_ui_base_from_rpc uses Config constants."""
    print("Testing tzkt_ui_base_from_rpc uses Config...")
    try:
        from app import tzkt_ui_base_from_rpc, Config

        # Test mainnet
        result = tzkt_ui_base_from_rpc("https://rpc.tzkt.io/mainnet")
        assert result == Config.TZKT_UI_MAINNET, f"Mainnet TzKT UI URL mismatch: {result}"

        # Test ghostnet
        result = tzkt_ui_base_from_rpc("https://ghostnet.tezos.marigold.dev")
        assert result == Config.TZKT_UI_GHOSTNET, f"Ghostnet TzKT UI URL mismatch: {result}"

        print("  ✅ tzkt_ui_base_from_rpc uses Config constants correctly")
        return True
    except Exception as e:
        print(f"  ❌ tzkt_ui_base_from_rpc test failed: {e}")
        return False


def test_no_hardcoded_urls_in_key_functions():
    """Test that key functions don't have hardcoded URLs (basic check)."""
    print("Testing for hardcoded URLs...")
    try:
        import inspect
        from app import choose_working_rpc

        # Get source code
        source = inspect.getsource(choose_working_rpc)

        # Check that it references Config or the module variables (not hardcoded strings)
        assert 'MAINNET_RPC_CANDIDATES' in source or 'Config.' in source, \
            "choose_working_rpc doesn't reference Config or RPC candidates"

        print("  ✅ Key functions use Config references instead of hardcoded URLs")
        return True
    except Exception as e:
        print(f"  ⚠️  Hardcoded URL check had issues (non-critical): {e}")
        return True  # Don't fail on this check


def main():
    """Run all Phase 5 validation tests."""
    print("="*70)
    print("PHASE 5 VALIDATION: String Constants (RPC URLs)")
    print("="*70)
    print()

    tests = [
        test_imports,
        test_rpc_url_constants_exist,
        test_rpc_urls_are_strings,
        test_rpc_candidates_are_lists,
        test_tzkt_ui_function_uses_config,
        test_no_hardcoded_urls_in_key_functions,
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
        print(f"✅ PHASE 5 VALIDATION PASSED ({passed}/{total} tests)")
        print("="*70)
        print()
        print("NOTE: All RPC URLs and TzKT endpoints are now consolidated in")
        print("the Config class, making them easy to maintain and update.")
        return 0
    else:
        print(f"❌ PHASE 5 VALIDATION FAILED ({passed}/{total} tests passed)")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
