#!/usr/bin/env python3
"""Publish compact evidence without trace data or private Codex transcripts."""
import hashlib,html,json,re,shutil
from pathlib import Path
from chipbench import core
root=core.ROOT;source=root/'.chipbench/codex-dpc3';out=root/'docs/benchmark';out.mkdir(exist_ok=True)
rows=[];evidence=[];usage=[]
selection=json.loads((source/'selection.json').read_text())
for n in range(1,4):
 r=json.loads((source/f'run-{n}.json').read_text());m=r.get('metrics') or {};ratios=m.get('ipc_ratios',{})
 pct=lambda v:'—' if v is None else f'{(v-1)*100:+.2f}%'
 cells=''.join(f'<td>{pct(ratios.get(t))}</td>' for t in ['429.mcf-184B','433.milc-127B','462.libquantum-1343B'])
 selected=' · 选中' if r['run_id']==selection['run_id'] else ''
 rows.append(f'<tr><td>第 {n} 次{selected}</td>{cells}<td><b>{pct(m.get("geomean_ipc_ratio"))}</b></td><td>{html.escape(r["status"])}</td></tr>')
 runfolder=core.STATE/'runs'/r['run_id']
 shutil.copyfile(runfolder/'candidate.patch',out/f'candidate-{n}.patch')
 evidence.append({k:r.get(k) for k in ['run_id','status','source_sha256','kind','created_at','finished_at','data_kind','metrics','error','environment','cleanup_ok']})
 for line in (source/f'events-{n}.jsonl').read_text().splitlines():
  event=json.loads(line)
  if event.get('type')=='turn.completed':usage.append({'attempt':n,**event.get('usage',{})})
 # Save the actual model-authored candidate, not the controller's rewrite.
 candidate=json.loads((source/f'candidate-{n}.json').read_text())
 dest=root/'experiments/dpc3-codex'/f'candidate-{n}';dest.mkdir(parents=True,exist_ok=True)
 for name,content in candidate.items():(dest/name).write_text(content)
 shutil.copyfile(root/'tasks/prefetch-dpc3/CHAMPSIM-LICENSE',dest/'CHAMPSIM-LICENSE')
 (dest/'rationale.txt').write_text((source/f'candidate-{n}.txt').read_text())
r=json.loads((source/'validation.json').read_text());m=r.get('metrics') or {};gm=m.get('geomean_ipc_ratio')
evidence.append({k:r.get(k) for k in ['run_id','status','source_sha256','parent','kind','created_at','finished_at','data_kind','metrics','error','environment','cleanup_ok']})
for item in evidence:
 payload=json.loads((core.STATE/'runs'/item['run_id']/'input.json').read_text())
 item['files_sha256']=hashlib.sha256(json.dumps(payload['files'],sort_keys=True).encode()).hexdigest()
selected=next(x for x in evidence if x['run_id']==selection['run_id'])
assert selected['files_sha256']==evidence[-1]['files_sha256'], 'Validation source differs from selected candidate'
result={'selection':selection,'runs':evidence,'codex_usage':usage,'hash_note':'source_sha256 is legacy full input fingerprint; files_sha256 hashes only the frozen two source files.'}
(out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
section='<section id="results"><h2>实测结果 · 3 次开发 + 1 次冻结验证</h2><p>第 1 次：保留重复访问间的规律，对稳定访问增加预取距离。第 2 次：增加重复预取过滤，未带来额外 IPC 收益。第 3 次：规律变化时取消旧预取，开发均值反而略降。因此选择第 1 个候选。</p><div style="overflow:auto"><table><tr><th>候选</th><th>mcf</th><th>milc</th><th>libquantum</th><th>几何平均</th><th>状态</th></tr>'+''.join(rows)+'</table></div>'
section+=f'<h3>冻结后验证：lbm {pct(gm)}</h3><p>验证状态：{html.escape(r["status"])}；达到 +1% 且无超过 5% 回退的门槛：{"是" if m.get("threshold_met") else "否"}。候选选择仅使用开发集结果；验证后没有再修改。</p>'
section+='<div class="grid"><div class="card"><small>开发集最佳</small><div class="big">+7.11%</div></div><div class="card"><small>冻结验证 · lbm</small><div class="big">'+pct(gm)+'</div></div><div class="card"><small>保留候选</small><div class="big">第 1 次</div>第 2 次打平，第 3 次略低</div></div>'
section+='<p>这些数字是相对原版 ip_stride 的模拟 IPC 变化。一次短窗口结果只说明这次测量，不证明通用优化；所有结果都保留。</p>'
section+='<p><a href="benchmark/results.json">完整指标、版本、校验与模型用量</a> · '+ ' · '.join(f'<a href="benchmark/candidate-{n}.patch">候选 {n} 补丁</a>' for n in range(1,4))+'</p></section>'
p=root/'docs/benchmark.html';s=p.read_text();s=re.sub(r'<section id="results">.*?</section>',lambda _:section,s,flags=re.S);p.write_text(s)
print(json.dumps({'development':[{ 'run_id':x['run_id'],'metrics':x.get('metrics')} for x in evidence[:3]],'validation':m,'usage':usage},ensure_ascii=False))
