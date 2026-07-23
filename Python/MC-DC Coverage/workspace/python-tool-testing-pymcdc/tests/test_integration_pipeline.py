from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_trigger_pipeline_produces_passing_json():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "pymcdc_trigger.py"), "--skip-verify"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    payload = json.loads((ROOT / "pymcdc.json").read_text(encoding="utf-8"))
    assert payload["metrics_covered"] == 1
    assert payload["metrics"][0]["score"] == 100

    verify = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_pymcdc_json.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0
    assert "PASS" in verify.stdout
