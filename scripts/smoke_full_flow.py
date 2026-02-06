#!/usr/bin/env python3
"""Smoke runner for full operation flow regression coverage.

This script runs the integration/regression tests that validate:
- Source wallet stays anchored during operation flow
- Pending shimmer/history updates stay scoped to source wallet
- New operations do not erase previous history rows
- Send overrides / send flow compatibility remains stable
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TEST_TARGETS = [
    "tests/test_stake_flow_integration.py",
    "tests/test_ui_pending_history_scope.py",
    "tests/test_history_selection_guards.py",
    "tests/test_send_overrides.py",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "pytest", "-q", "-vv", *TEST_TARGETS]
    print("[smoke] running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(root))
    if result.returncode == 0:
        print("[smoke] PASS")
    else:
        print("[smoke] FAIL")
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
