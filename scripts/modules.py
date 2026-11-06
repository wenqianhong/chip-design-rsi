#!/usr/bin/env python3
"""Run/collect independent v0.2 module checks. No model invocation."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIMA=str(ROOT/'.tools/lima/bin/limactl');VM='chipbench-modules'
GUEST='/home/wenqianhong.guest/chipbench-modules'
OUT=ROOT/'.chipbench/modules'
def call(args,**kwargs):return subprocess.run(args,check=True,**kwargs)
def shell(*args):return call([LIMA,'shell','--workdir=/tmp',VM,*args])
p=argparse.ArgumentParser();p.add_argument('command',choices=['status','logic','drc','mapping','physical','timeout','collect']);a=p.parse_args()
OUT.mkdir(parents=True,exist_ok=True)
if a.command=='status':
 call([LIMA,'list','--json',VM])
 for name in ['logic-results.json','physical-results.json','drc-results.json','mapping-results.json','timeout-results.json']:
  path=OUT/'results'/name
  if path.exists():print(path.read_text())
elif a.command in ['logic','drc','mapping','physical','timeout']:
 call([LIMA,'start',VM,'--tty=false'])
 call([LIMA,'copy',str(ROOT/'environments/modules/process.py'),VM+':'+GUEST+'/process.py'])
 if a.command!='logic':
  names={'drc':['drc_fixtures.py','run_drc.py'],'mapping':['run_mapping.py'],'physical':['physical.tcl','run_physical.py'],'timeout':['check_timeout.py']}[a.command]
  for name in names:
   call([LIMA,'copy',str(ROOT/'environments/modules'/name),VM+':'+GUEST+'/'+name])
  shell('python3',GUEST+'/'+names[-1])
  raise SystemExit(0)
 for name in ['counter.sv','counter_tb.sv']:
  call([LIMA,'copy',str(ROOT/'environments/modules'/name),VM+':'+GUEST+'/fixtures/'+name])
 call([LIMA,'copy',str(ROOT/'environments/modules/run_logic.py'),VM+':'+GUEST+'/run_logic.py'])
 shell('python3',GUEST+'/run_logic.py')
else:
 call([LIMA,'copy','-r',VM+':'+GUEST+'/results',str(OUT)])
 print(OUT/'results')
