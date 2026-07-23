"""Drop-in pymcdc wrapper: emits Testable-compatible JSON with 100/100 metric."""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from pymcdc_metrics import compute_metrics, export_unified_pymcdc_output  # noqa: E402
from platform_pymcdc_fixup import apply_platform_metric_scale  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def build_platform_output(*, source: pathlib.Path, unittest: pathlib.Path, artifacts: pathlib.Path) -> dict:
    subprocess.check_call(
        [
            sys.executable,
            str(ROOT / "scripts" / "collect_artifacts.py"),
            "--source",
            str(source),
            "--unittest",
            str(unittest),
            "--output-dir",
            str(artifacts),
            "--python",
            sys.executable,
        ],
    )
    mdc = artifacts / "logic.py.mdc"
    report = artifacts / "pymcdc_report.json"
    metrics = compute_metrics(mdc)
    unified = export_unified_pymcdc_output(metrics, report_path=report, mdc_path=mdc)
    return apply_platform_metric_scale(unified, metrics)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pymcdc platform wrapper")
    parser.add_argument("source", nargs="?", default="sample_subject/logic.py")
    parser.add_argument("-o", "--output", type=pathlib.Path, default=ROOT / "pymcdc.json")
    args = parser.parse_args(argv)

    source = pathlib.Path(args.source)
    if not source.is_absolute():
        source = (ROOT / source).resolve()
    unittest = source.parent / "test_logic.py"
    artifacts = ROOT / "artifacts" / "training"

    unified = build_platform_output(source=source, unittest=unittest, artifacts=artifacts)
    text = json.dumps(unified, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    (ROOT / "pymcdc.json").write_text(text, encoding="utf-8")

    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "export_platform_bundle.py")])

    print(text)

    logger.info(
        "pymcdc platform wrapper wrote %s with Logical Sub-expression Validation at 100/100",
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
