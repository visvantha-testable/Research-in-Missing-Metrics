"""Sample execution to generate raw Pylint output artifacts."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
SAMPLE_REPO = METRIC_ROOT / "workspace" / "sample_nesting_repo"
OUTPUT_PATH = METRIC_ROOT / "outputs"
PY = sys.executable


def setup_sample_repo() -> Path:
    SAMPLE_REPO.mkdir(parents=True, exist_ok=True)
    (SAMPLE_REPO / "deep_nesting.py").write_text(
        """def deeply_nested(value):
    if value > 0:
        if value > 1:
            if value > 2:
                if value > 3:
                    if value > 4:
                        if value > 5:
                            return value
    return 0
""",
        encoding="utf-8",
    )
    (SAMPLE_REPO / "clean.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    return SAMPLE_REPO


def run_pylint(repo_path: Path, output_format: str | None = None) -> tuple[str, str, int]:
    command = [PY, "-m", "pylint", str(repo_path)]
    if output_format:
        command.extend(["--output-format", output_format])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def main() -> None:
    repo_path = setup_sample_repo()
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    raw_stdout, raw_stderr, _ = run_pylint(repo_path)
    raw_text = raw_stdout
    if raw_stderr:
        if raw_text and not raw_text.endswith("\n"):
            raw_text += "\n"
        raw_text += raw_stderr

    json_stdout, json_stderr, _ = run_pylint(repo_path, output_format="json")
    records = json.loads(json_stdout) if json_stdout.strip() else []

    import pandas as pd

    python_files = sorted(repo_path.rglob("*.py"))
    pd.DataFrame(
        [{"absolute_path": str(p), "relative_path": str(p.relative_to(repo_path))} for p in python_files]
    ).to_csv(OUTPUT_PATH / "python_files.csv", index=False)

    (OUTPUT_PATH / "pylint_raw_output.txt").write_text(raw_text, encoding="utf-8")
    (OUTPUT_PATH / "pylint_output.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    results_df = pd.DataFrame(
        [
            {
                "file": r.get("path") or r.get("module", ""),
                "line": r.get("line", ""),
                "column": r.get("column", ""),
                "type": r.get("type", ""),
                "symbol": r.get("symbol", ""),
                "message": r.get("message", ""),
                "message-id": r.get("message-id", ""),
                "confidence": r.get("confidence", ""),
            }
            for r in records
        ]
    )
    results_df.to_csv(OUTPUT_PATH / "pylint_results.csv", index=False)

    nesting = results_df[results_df["message-id"].isin(["R1702", "R0101"])]
    nesting_out = pd.DataFrame(
        [
            {
                "file": row["file"],
                "line": row["line"],
                "warning": row["symbol"],
                "message": row["message"],
                "detected_nesting_depth": _depth(row["message"]),
            }
            for _, row in nesting.iterrows()
        ]
    )
    nesting_out.to_csv(OUTPUT_PATH / "nesting_depth_findings.csv", index=False)
    (OUTPUT_PATH / "error_log.txt").write_text("", encoding="utf-8")

    print(f"Sample repo: {repo_path}")
    print(f"Raw output chars: {len(raw_text)}")
    print(f"Findings: {len(results_df)}")
    print(f"Nesting findings: {len(nesting_out)}")
    print(f"Deliverables written to: {OUTPUT_PATH}")
    print("\n--- RAW PYLINT OUTPUT ---\n")
    print(raw_text)


def _depth(message: str):
    import re

    match = re.search(r"Too many nested blocks\s*\((\d+)\s*/\s*(\d+)\)", message, re.I)
    return int(match.group(1)) if match else None


if __name__ == "__main__":
    main()
