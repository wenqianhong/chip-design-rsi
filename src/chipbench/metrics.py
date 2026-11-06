"""Strict parsing of pinned ChampSim output, not an agent's success claim."""
import html
import json
import math
from pathlib import Path


def parse_stats(raw, minimum=50000):
    phases = json.loads(raw) if isinstance(raw, str) else raw
    phase = [p for p in phases if p.get("name") == "Simulation"]
    if len(phase) != 1:
        raise ValueError("Expected exactly one Simulation phase")
    roi = phase[0]["roi"]
    core = roi["cores"]
    if len(core) != 1:
        raise ValueError("Expected a single simulated CPU")
    instructions, cycles = core[0]["instructions"], core[0]["cycles"]
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in (instructions, cycles)):
        raise ValueError("Non-finite or non-numeric counters")
    if instructions < minimum or cycles <= 0:
        raise ValueError("Incomplete simulation or invalid cycle count")
    result = {"instructions": instructions, "cycles": cycles, "ipc": instructions / cycles}
    cache = roi.get("cpu0_L2C", {})
    misses = sum(sum(v.get("miss", [])) for k, v in cache.items() if k in ("LOAD", "RFO") and isinstance(v, dict))
    result["l2_demand_mpki"] = misses * 1000 / instructions
    result["prefetch"] = {k: v for k, v in cache.items() if "prefetch" in k.lower() or k == "PREFETCH"}
    return result


def compare(baseline, candidate):
    if not baseline or set(baseline) != set(candidate):
        raise ValueError("Candidate and baseline must contain every same trace")
    ratios = {k: candidate[k]["ipc"] / baseline[k]["ipc"] for k in baseline}
    if not all(math.isfinite(v) and v > 0 for v in ratios.values()):
        raise ValueError("Invalid IPC ratio")
    gm = math.exp(sum(math.log(v) for v in ratios.values()) / len(ratios))
    return {"ipc_ratios": ratios, "geomean_ipc_ratio": gm,
            "threshold_met": gm >= 1.01 and min(ratios.values()) >= .95,
            "interpretation": "Synthetic smoke results only; no real workload performance claim."}


def report(path: Path, record):
    esc = lambda value: html.escape(str(value), quote=True)
    metrics = record.get('metrics') or {}
    ratio = metrics.get('geomean_ipc_ratio')
    summary = f"{(ratio - 1) * 100:+.2f}%" if ratio is not None else '—'
    rows = []
    for trace, value in metrics.get('ipc_ratios', {}).items():
        base = metrics['runs']['baseline'][trace]['ipc']
        candidate = metrics['runs']['candidate'][trace]['ipc']
        width = max(0, min(100, value * 50))
        rows.append(f'<tr><td>{esc(trace)}</td><td>{base:.6f}</td><td>{candidate:.6f}</td><td>{(value-1)*100:+.2f}%<div class="bar"><i style="width:{width:.2f}%"></i></div></td></tr>')
    raw = esc(json.dumps(record, ensure_ascii=False, indent=2))
    document = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chipbench 实验报告</title><style>
body{max-width:1000px;margin:35px auto;padding:0 20px 45px;background:#f5f5ef;color:#193b34;font:15px/1.7 system-ui}
header{background:#193b34;color:white;border-radius:20px;padding:28px}h1{font-size:32px;margin:8px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}.card,details{padding:20px;background:white;border:1px solid #dce2d9;border-radius:12px}.number{font-size:30px;font-weight:700}small{color:#63716b}.note{background:#eaf0df;padding:16px;border-left:3px solid #176b51}table{width:100%;border-collapse:collapse;background:white;font-size:13px}td,th{padding:14px;border-bottom:1px solid #dce2d9;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.bar{height:6px;background:#e9ede2;width:130px;position:relative}.bar:after{content:'';position:absolute;left:50%;height:10px;top:-2px;border-left:1px solid #b66b13}.bar i{display:block;background:#6f9d60;height:6px}.table{overflow:auto}details{margin-top:18px}summary{cursor:pointer}@media(max-width:620px){.cards{grid-template-columns:1fr}h1{font-size:26px}}
</style><header><small style="color:#d6f18b">CHIPBENCH · REAL SIMULATION</small><h1>预取器实验报告</h1><p>RUN_ID · STATUS</p></header>
<div class="cards"><div class="card"><small>IPC 几何平均变化</small><div class="number">SUMMARY</div></div><div class="card"><small>数据类型</small><div class="number">DATA_KIND</div></div><div class="card"><small>VM 清理</small><div class="number">CLEANUP</div></div></div>
<div class="note">INTERPRETATION 基线与候选各重复 3 次，橙线表示 IPC 比值 1.0；没有提升也会保留结果。</div>
<div class="table"><table><thead><tr><th>Trace</th><th>基线 IPC</th><th>候选 IPC</th><th>变化</th></tr></thead><tbody>ROWS</tbody></table></div>
<p>ERROR</p><details><summary>展开完整结果与证据路径</summary><pre>RAW</pre></details></html>"""
    for key, value in {'RUN_ID': esc(record.get('run_id','')), 'STATUS': esc(record.get('status','')),
                       'DATA_KIND': esc(record.get('data_kind','synthetic-smoke')), 'INTERPRETATION': esc(metrics.get('interpretation','Synthetic smoke only.')), 'SUMMARY': summary, 'CLEANUP': '已完成' if record.get('cleanup_ok') else '待检查',
                       'ROWS': ''.join(rows), 'ERROR': esc(record.get('error') or '实验状态与性能提升分别判断；请检查逐 trace 结果。'), 'RAW': raw}.items():
        document = document.replace(key,value)
    path.write_text(document)
