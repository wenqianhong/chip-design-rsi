#!/usr/bin/env python3
"""Continue the recorded experiment: at most three Codex candidates, one frozen validation."""
import json,os,subprocess,time
from pathlib import Path
from chipbench import core
root=core.ROOT;folder=root/'.chipbench/codex-dpc3'
if (folder/'controller-started').exists(): raise SystemExit('Controller already started; inspect saved runs before recovery, never restart the budget blindly.')
(folder/'controller-started').touch()
ws=json.loads((folder/'workspace.json').read_text());wid=ws['workspace_id']
def wait(rid):
 while True:
  r=core.inspect(rid,limit=0)
  if r['status'] in core.TERMINAL:return r
  time.sleep(5)
def compact(r):
 return {k:r.get(k) for k in ['run_id','status','error','metrics']}
results=[]
for attempt in range(1,4):
 if attempt>1:
  prompt=(folder/'prompt-1.txt').read_text().replace('candidate 1 of at most 3',f'candidate {attempt} of at most 3').replace('No measurements yet.', 'Use the measured feedback below.')
  prompt+='\nMeasured previous attempts follow. Your current files are the last candidate. Review regressions and propose a better general strategy. You may revert changes that did not help. Edit only the two files; do not run measurements yourself. Baseline original sources are at '+str(root/'tasks/prefetch-dpc3')+'.\n'+json.dumps([compact(r) for r in results])
  (folder/f'prompt-{attempt}.txt').write_text(prompt)
  env=os.environ.copy()
  for k in ('OPENAI_API_KEY','CODEX_API_KEY'):env.pop(k,None)
  cmd=['codex','exec','-C',ws['path'],'--sandbox','workspace-write','--ephemeral','--json','-o',str(folder/f'candidate-{attempt}.txt'),'-']
  with (folder/f'events-{attempt}.jsonl').open('w') as log,(folder/f'stderr-{attempt}.log').open('w') as err:
   proc=subprocess.run(cmd,input=prompt,text=True,stdout=log,stderr=err,env=env,timeout=600)
  if proc.returncode:raise RuntimeError(f'Codex CLI attempt {attempt} failed: {proc.returncode}')
  files=core.snapshot(wid)
  (folder/f'candidate-{attempt}.json').write_text(json.dumps(files,indent=2))
  r=core.run(wid,f'dpc3-codex-attempt-{attempt}')
  (folder/f'run-{attempt}.json').write_text(json.dumps(r,indent=2))
 else:r=json.loads((folder/'run-1.json').read_text())
 print('Evaluating',attempt,r['run_id'],flush=True)
 r=wait(r['run_id']);results.append(r)
 (folder/f'run-{attempt}.json').write_text(json.dumps(r,indent=2))
 print(json.dumps({'attempt':attempt,'status':r['status'],'error':r.get('error'),'ratios':(r.get('metrics') or {}).get('ipc_ratios'),'gm':(r.get('metrics') or {}).get('geomean_ipc_ratio')}),flush=True)
valid=[r for r in results if r['status']=='completed']
if not valid:raise RuntimeError('No valid candidate; no validation submitted')
# Freeze selection using only development results. Prefer candidates within regression guardrail.
eligible=[r for r in valid if min(r['metrics']['ipc_ratios'].values())>=.95]
best=max(eligible or valid,key=lambda r:r['metrics']['geomean_ipc_ratio'])
(folder/'selection.json').write_text(json.dumps({'run_id':best['run_id'],'rule':'Maximum development geometric mean among candidates with no >5% regression, if any; otherwise maximum valid mean. No validation feedback used.'},indent=2))
r=core.evaluate(best['run_id'],'dpc3-codex-final');print('Final validation',r['run_id'],flush=True)
r=wait(r['run_id']);(folder/'validation.json').write_text(json.dumps(r,indent=2))
print(json.dumps({'validation':r['status'],'metrics':r.get('metrics'),'error':r.get('error')}),flush=True)
