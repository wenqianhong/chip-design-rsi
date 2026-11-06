"""Map the counter to Nangate45 cells, then run the same behavior checks."""
import json,subprocess,time
from pathlib import Path
from process import run
root=Path(__file__).resolve().parent
out=root/'results'
platform=root/'orfs/tools/OpenROAD/test/Nangate45'
lib=platform/'Nangate45_typ.lib'
net=out/'counter_mapped.v'
script=f'read_verilog {root}/fixtures/counter.sv; synth -top counter; dfflibmap -liberty {lib}; abc -liberty {lib}; clean; read_liberty -lib {lib}; check -assert; stat -liberty {lib}; write_verilog -noattr {net}'
commands=[('cell-models',['yosys','-p',f'read_liberty -ignore_miss_func {lib}; write_verilog -noattr {out}/nangate_models.v'],None),('cell-mapping',['yosys','-p',script],'Found and reported 0 problems'),('mapped-compile',['iverilog','-g2012','-o',str(out/'mapped.vvp'),str(net),str(out/'nangate_models.v'),str(root/'fixtures/counter_tb.sv')],None),('mapped-simulation',['vvp',str(out/'mapped.vvp')],'COUNTER_PASS checks=3')]
rows=[]
for name,args,marker in commands:
 start=time.monotonic()
 with (out/(name+'.log')).open('w') as f:
  p=run(args,stdout=f,stderr=subprocess.STDOUT,timeout=120)
 text=(out/(name+'.log')).read_text()
 ok=p.returncode==0 and (marker is None or marker in text)
 if name=='cell-mapping':ok=ok and net.exists() and 'DFF_X1' in net.read_text()
 rows.append(dict(name=name,status='passed' if ok else 'failed',command=args,exit_code=p.returncode,elapsed_seconds=round(time.monotonic()-start,3)))
 if not ok:break
(out/'mapping-results.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
raise SystemExit(0 if len(rows)==4 and all(r['status']=='passed' for r in rows) else 1)
