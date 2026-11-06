"""Independently verify the upstream FreePDK45 DRC deck detects a width error."""
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from process import run

root = Path(__file__).resolve().parent
out = root / "results"
out.mkdir(exist_ok=True)
deck = root / "orfs/flow/platforms/nangate45/drc/FreePDK45.lydrc"
subprocess.run(["klayout", "-b", "-r", str(root / "drc_fixtures.py")], check=True)
rows = []
for name in ["metal_good", "metal_bad"]:
    report = out / (name + ".lyrdb")
    args = ["klayout", "-b", "-r", str(deck), "-rd", f"in_gds={out / (name + '.gds')}",
            "-rd", f"report_file={report}"]
    started = time.monotonic()
    with (out / (name + ".log")).open("w") as log:
        proc = run(args, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    categories = []
    if report.exists():
        categories = [i.findtext("category", "") for i in ET.parse(report).findall(".//items/item")]
    passed = proc.returncode == 0 and report.exists() and (
        not categories if name == "metal_good" else any("METAL1.1" in c for c in categories))
    rows.append(dict(name=name, status="passed" if passed else "failed", exit_code=proc.returncode,
                     violations=len(categories), categories=categories, command=args,
                     elapsed_seconds=round(time.monotonic()-started, 3)))
(out / "drc-results.json").write_text(json.dumps(rows, indent=2))
print(json.dumps(rows, indent=2))
raise SystemExit(0 if all(r["status"] == "passed" for r in rows) else 1)
