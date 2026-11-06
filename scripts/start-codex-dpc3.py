import json,os,subprocess
from pathlib import Path
from chipbench import core
root=core.ROOT
folder=root/'.chipbench/codex-dpc3'
if (folder/'workspace.json').exists(): raise SystemExit('Experiment already exists; do not reset the three-attempt budget.')
ws=core.reset('prefetch-dpc3')
folder.mkdir(exist_ok=True)
(folder/'workspace.json').write_text(json.dumps(ws,indent=2))
prompt='''You are optimizing the L2 ip_stride prefetcher for the user's chipbench experiment. This is candidate 1 of at most 3. Edit ONLY ip_stride.cc and ip_stride.h in your current working directory. Do not submit runs, reset workspaces, or call any MCP tool. The external controller compiles and measures your candidate, then may give feedback for a next candidate. No delegation or other model calls.
Use the existing interfaces. You may read the upstream headers at '''+str(root/'.tools/ChampSim/inc')+''' if needed. Keep tracker sets=256 and ways=4; keep total bounded state reasonably near baseline (no giant tables); no trace-specific rules, filesystem/network accesses, output spoofing, or changes to simulator/config/test harness. Design a plausible general prefetch improvement, not tuning on workload names. Current baseline detects repeated IP stride, lookahead degree 3, 0.5 MSHR fill threshold. Think about missed opportunities and pollution, implement one coherent improvement that can compile. Favor small reliable changes.
Evaluation: fixed single-core ChampSim 410cee62, 1M warmup+2M measured instructions, 3 deterministic repeats. Develop on DPC3 SPEC traces mcf, milc, libquantum; unseen final workload once. Objective geometric mean IPC ratio >=1.01, no workload regression >5%. No measurements yet. Do not claim an improvement without results. End with concise design rationale and what changed.
'''
(folder/'prompt-1.txt').write_text(prompt)
env=os.environ.copy()
for k in ('OPENAI_API_KEY','CODEX_API_KEY'):env.pop(k,None)
cmd=['codex','exec','-C',ws['path'],'--sandbox','workspace-write','--ephemeral','--json','-o',str(folder/'candidate-1.txt'),'-']
with (folder/'events-1.jsonl').open('w') as log,(folder/'stderr-1.log').open('w') as err:
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=err,env=env,text=True)
 p.stdin.write(prompt);p.stdin.close()
 (folder/'pid-1').write_text(str(p.pid));print(ws['workspace_id'],p.pid,flush=True)
 code=p.wait();print('CLI exit',code,flush=True)
 if code: raise SystemExit(code)
files=core.snapshot(ws['workspace_id'])
(folder/'candidate-1.json').write_text(json.dumps(files,indent=2))
r=core.run(ws['workspace_id'],'dpc3-codex-attempt-1')
(folder/'run-1.json').write_text(json.dumps(r,indent=2))
print(r['run_id'],flush=True)
