from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_platform_module_entrypoint():
    proc = subprocess.run(
        [sys.executable, "-m", "pymcdc_platform", "sample_subject/logic.py", "-o", "pymcdc.json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Logical Sub-expression Validation" in (ROOT / "pymcdc.json").read_text(encoding="utf-8")
