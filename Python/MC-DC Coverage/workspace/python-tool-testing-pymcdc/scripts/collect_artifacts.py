"""Collect pymcdc raw artifacts from the training subject."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pymcdc_metrics import export_decisions_json, run_pymcdc_analysis  # noqa: E402


def collect(
    *,
    source: pathlib.Path,
    unittest: pathlib.Path,
    output_dir: pathlib.Path,
    python_exe: str,
) -> None:
    subject_dir = source.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    subprocess.check_call(
        [python_exe, "-m", "pip", "install", "pymcdc>=0.2.5", "-q"],
    )
    run_pymcdc_analysis(
        source=source,
        unittest=unittest,
        subject_dir=subject_dir,
        python_exe=python_exe,
    )

    mdc_path = subject_dir / f"{source.name}.mdc"
    report = export_decisions_json(mdc_path)
    (output_dir / "pymcdc_report.json").write_text(
        __import__("json").dumps(report, indent=2),
        encoding="utf-8",
    )

    dest_mdc = output_dir / mdc_path.name
    dest_mdc.write_bytes(mdc_path.read_bytes())
    print(f"Collected pymcdc artifacts in {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=pathlib.Path,
        default=ROOT / "sample_subject" / "logic.py",
    )
    parser.add_argument(
        "--unittest",
        type=pathlib.Path,
        default=ROOT / "sample_subject" / "test_logic.py",
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=ROOT / "artifacts" / "training",
    )
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    collect(
        source=args.source,
        unittest=args.unittest,
        output_dir=args.output_dir,
        python_exe=args.python,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
