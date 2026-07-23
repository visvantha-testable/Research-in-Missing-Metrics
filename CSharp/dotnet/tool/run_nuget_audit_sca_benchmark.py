"""Execute NuGet Audit SCA pipeline outside Jupyter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_nuget_audit_sca_benchmark_impl import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
