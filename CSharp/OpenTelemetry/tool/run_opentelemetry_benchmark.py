"""Execute OpenTelemetry extraction pipeline outside Jupyter."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_opentelemetry_benchmark_impl import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
