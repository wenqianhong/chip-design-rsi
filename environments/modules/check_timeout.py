"""A child must not survive its timed-out parent and write a late result."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from process import run

with tempfile.TemporaryDirectory() as tmp:
    marker = Path(tmp) / "late-result"
    child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).write_text('escaped')"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(10)"
    timed_out = False
    try:
        run([sys.executable, "-c", parent], timeout=0.2)
    except subprocess.TimeoutExpired:
        timed_out = True
    time.sleep(1.2)
    result = dict(name="timeout-process-group", status="passed" if timed_out and not marker.exists() else "failed",
                  timeout_detected=timed_out, child_wrote_late_result=marker.exists())
    out = Path(__file__).resolve().parent / "results"
    out.mkdir(exist_ok=True)
    (out / "timeout-results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "passed" else 1)
