#!/usr/bin/env python3
"""Install verified cached prefixes into the stopped base under the runner lock."""
import fcntl,hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lima=str(root/'.tools/lima/bin/limactl')
data=root/'.tools/dpc3'
manifest=json.loads((data/'manifest.json').read_text())
def run(*args):subprocess.run([lima,*map(str,args)],check=True)
with (root/'.chipbench/runner.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 try:
  run('start','chipbench-base','--tty=false')
  for row in manifest['traces']:
   p=data/(row['name']+'.champsimtrace.xz')
   assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
   run('copy',p,'chipbench-base:/tmp/'+p.name)
   run('shell','--workdir=/tmp','chipbench-base','sudo','install','-m','444','/tmp/'+p.name,'/opt/chipbench/traces/'+p.name)
 finally:run('stop','chipbench-base','--tty=false')
 p=root/'.chipbench-base.json';base=json.loads(p.read_text());base['dpc3']=manifest;p.write_text(json.dumps(base,indent=2))
(root/'tasks/prefetch-dpc3/data-manifest.json').write_text(json.dumps(manifest,indent=2))
