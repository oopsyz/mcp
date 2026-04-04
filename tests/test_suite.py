from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    ROOT / "tests" / "conformance_test.py",
    ROOT / "tests" / "edge_test.py",
    ROOT / "tests" / "test_cli_api.py",
    ROOT / "tests" / "test_registry.py",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_standalone_scripts(script: Path):
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, (
        f"{script.name} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
