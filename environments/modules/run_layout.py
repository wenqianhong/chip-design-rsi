"""Check GDS conversion and report actual upstream DRC results without hiding violations."""
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from process import run
root=Path(__file__).resolve().parent
out=root/'results/physical'
args=['klayout','-b','-r',str(root/'stream_layout.py')]
with (out/'gds-merge.log').open('w') as log:
 p=run(args,stdout=log,stderr=subprocess.STDOUT,timeout=120)
if p.returncode or 'GDS_PASS' not in (out/'gds-merge.log').read_text():
 raise RuntimeError('GDS conversion failed; see gds-merge.log')
report=out/'gcd.lyrdb'
if report.exists():report.unlink()
args=['klayout','-b','-r',str(root/'orfs/flow/platforms/nangate45/drc/FreePDK45.lydrc'),'-rd',f'in_gds={out}/gcd.gds','-rd',f'report_file={report}']
start=time.monotonic()
with (out/'gds-drc.log').open('w') as log:
 p=run(args,stdout=log,stderr=subprocess.STDOUT,timeout=300)
categories=Counter(i.findtext('category','') for i in ET.parse(report).findall('.//items/item')) if report.exists() else {}
row=dict(status='passed' if p.returncode==0 and report.exists() and not categories else 'failed',exit_code=p.returncode,violations=sum(categories.values()),categories=categories,command=args,elapsed_seconds=round(time.monotonic()-start,3),scope='Upstream educational FreePDK45 rule deck; not foundry signoff')
(root/'results/layout-results.json').write_text(json.dumps(row,indent=2))
print(json.dumps(row,indent=2))
if row['status']=='passed':
 with (out/'render.log').open('w') as log:
  rendered=run(['klayout','-b','-r',str(root/'render_layout.py')],stdout=log,stderr=subprocess.STDOUT,timeout=120)
 if rendered.returncode:raise RuntimeError('DRC passed, but layout rendering failed')
raise SystemExit(0 if row['status']=='passed' else 1)
