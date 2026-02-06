import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke_pilot
def test_smoke_textual_pilot_script() -> None:
    if os.environ.get("RUN_SMOKE_PILOT") != "1":
        pytest.skip("Set RUN_SMOKE_PILOT=1 to run interactive Textual Pilot smoke.")

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "smoke_textual_pilot.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        timeout=80,
    )
    if result.returncode != 0:
        raise AssertionError(f"smoke_textual_pilot failed with code {result.returncode}")
