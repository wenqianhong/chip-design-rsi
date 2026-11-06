"""Standalone upstream GCD physical smoke test, not a CPU integration test."""
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from process import run

root = Path(__file__).resolve().parent
out = root / "results/physical"
if out.exists():
    # Preserve the previous attempt, but never accept its stale artifacts.
    out.rename(root / "results" / ("physical-previous-" + str(time.time_ns())))
out.mkdir(parents=True, exist_ok=True)
source = root / "orfs/tools/OpenROAD"
exe = root / "tools/bin/openroad"
args = [str(exe), "-exit", "-no_init", "-threads", "4", "-metrics", str(out / "metrics.json"), str(root / "physical.tcl")]
start = time.monotonic()
with (out / "flow.log").open("w") as log:
    proc = run(args, cwd=source / "test", env={**os.environ, "RESULTS_DIR":str(out)},
                          stdout=log, stderr=subprocess.STDOUT, timeout=900)
text = (out / "flow.log").read_text(errors="replace")
values = dict(re.findall(r"^MODULE_(\w+)\s+(\S+)", text, re.M))
checks = {
    "process":proc.returncode == 0,
    "fully_routed":values.get("ROUTED") in ("1", "true"),
    "routing_drc":values.get("DRC") == "0",
    "antenna":values.get("ANTENNA") == "0",
    "constraints":values.get("CONSTRAINTS") == "1",
    "relaxed_setup":float(values.get("RELAXED_SETUP", "nan")) >= 0,
    "tight_setup_detected":float(values.get("TIGHT_SETUP", "nan")) < 0,
}
artifacts = {p.name:{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in out.iterdir() if p.is_file()}
checks["routed_def"] = any("route" in n and n.endswith(".def") and v["bytes"] > 0 for n,v in artifacts.items())
checks["extracted_spef"] = any(n.endswith(".spef") and v["bytes"] > 0 for n,v in artifacts.items())
for stage in ["global_place", "cts", "dpl", "route", "fill"]:
    checks[stage+"_checkpoint"] = any(stage in n and n.endswith(".db") and v["bytes"] > 0 for n,v in artifacts.items())
row = dict(status="passed" if all(checks.values()) else "failed", checks=checks, values=values,
           exit_code=proc.returncode, command=args, elapsed_seconds=round(time.monotonic()-start,3), artifacts=artifacts)
(root / "results/physical-results.json").write_text(json.dumps(row, indent=2))
print(json.dumps(row, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
