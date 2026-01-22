#!/usr/bin/env python3
"""
Master Validation Script - All Phases

Executes all phase validation tests in sequence to ensure
the entire refactoring is working correctly.
"""
import sys
import subprocess


def run_test(phase_num: int, description: str) -> bool:
    """Run a single phase test."""
    test_file = f"test_phase{phase_num}_complete.py"

    print(f"\n{'='*70}")
    print(f"TESTING PHASE {phase_num}: {description}")
    print('='*70)

    try:
        result = subprocess.run(
            ["python3", test_file],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Print output
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode != 0:
            print(f"\n❌ Phase {phase_num} validation failed")
            return False

        print(f"\n✅ Phase {phase_num} validation passed")
        return True

    except subprocess.TimeoutExpired:
        print(f"\n❌ Phase {phase_num} test timed out")
        return False
    except FileNotFoundError:
        print(f"\n❌ Test file not found: {test_file}")
        return False
    except Exception as e:
        print(f"\n❌ Phase {phase_num} test crashed: {e}")
        return False


def main():
    """Run all phase validation tests."""
    print("="*70)
    print("MASTER VALIDATION: ALL PHASES")
    print("="*70)
    print("\nRunning comprehensive validation of all refactoring phases...")
    print()

    phases = [
        (1, "Logging Infrastructure"),
        (2, "Thread Safety"),
        (3, "Timeouts & Cleanup"),
        (4, "Type Hints"),
        (5, "String Constants"),
    ]

    results = []
    for phase_num, description in phases:
        result = run_test(phase_num, description)
        results.append((phase_num, description, result))

    # Print summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    passed = sum(1 for _, _, r in results if r)
    total = len(results)

    for phase_num, description, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  Phase {phase_num} ({description:30}): {status}")

    print("="*70)

    if passed == total:
        print(f"\n🎉 ALL PHASES VALIDATED SUCCESSFULLY ({passed}/{total})")
        print("\n✨ Refactoring complete! The codebase is now:")
        print("   • More maintainable with structured logging")
        print("   • Thread-safe with proper locking mechanisms")
        print("   • Cleaner with consolidated timeouts and constants")
        print("   • Better typed for improved IDE support")
        print("   • Resource-managed with proper timer cleanup")
        print("\n✅ Ready for production deployment after manual testing!")
        print("="*70)
        return 0
    else:
        print(f"\n⚠️  VALIDATION ISSUES DETECTED ({passed}/{total} passed)")
        print("\nFailed phases need attention before deployment.")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
