"""Ratchet pyright: fail if error count > baseline file. Usage (in backend/): uv run python ../scripts/pyright_ratchet.py pyright-baseline.txt"""

import json
import subprocess
import sys
from pathlib import Path

baseline = int(Path(sys.argv[1]).read_text().strip())
out = subprocess.run(
    [sys.executable, "-m", "pyright", "--outputjson"],
    capture_output=True,
    text=True,
    encoding="utf-8",
).stdout
errors = json.loads(out)["summary"]["errorCount"]
print(f"pyright errors: {errors} (baseline {baseline})")
if errors > baseline:
    sys.exit(
        f"FAIL: {errors - baseline} new pyright error(s). Fix them; do not raise the baseline."
    )
if errors < baseline:
    print(f"Baseline can go down: write {errors} to {sys.argv[1]}.")
