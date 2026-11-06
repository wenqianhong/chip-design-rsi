import json
from pathlib import Path
import pytest
from chipbench import core
from chipbench.metrics import parse_stats,compare,report

@pytest.fixture
def state(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'STATE',tmp_path)
    return tmp_path

def stats(instructions=50000,cycles=10000):
    return [{'name':'Simulation','roi':{'cores':[{'instructions':instructions,'cycles':cycles}],'cpu0_L2C':{'LOAD':{'miss':[20]},'RFO':{'miss':[5]}}}}]

def test_metrics_complete_and_missing():
    assert parse_stats(stats())['ipc']==5
    assert parse_stats(stats())['l2_demand_mpki']==.5
    for x in [stats(1),stats(cycles=0),stats(cycles=float('nan')),[]]:
        with pytest.raises((ValueError,KeyError)): parse_stats(x)
    with pytest.raises(ValueError): compare({'a':{'ipc':1}}, {})

def test_sources_and_traversal(state):
    ws=core.reset(); wid=ws['workspace_id']
    assert set(core.snapshot(wid))==set(core.ALLOWED)
    with pytest.raises(ValueError): core.snapshot('../foo')
    with pytest.raises(ValueError): core.snapshot(wid,{'../../x':'code'})
    path=Path(ws['path']); (path/'outside').symlink_to('/etc/passwd')
    with pytest.raises(ValueError): core.snapshot(wid)

def test_submission_idempotency_and_budget(state,monkeypatch):
    class Process: pid=123
    monkeypatch.setattr(core.subprocess,'Popen',lambda *a,**kw:Process())
    wid=core.reset()['workspace_id']
    first=core.run(wid,'one'); again=core.run(wid,'one')
    assert first['run_id']==again['run_id']
    files=core.snapshot(wid); files['ip_stride.cc']+='\n// new\n'
    with pytest.raises(ValueError): core.run(wid,'one',files)
    for i in range(2): core.run(wid,f'next-{i}')
    with pytest.raises(ValueError): core.run(wid,'over-budget')
    assert core.cancel(first['run_id'])['status']=='cancelling'
    assert (state/'runs'/first['run_id']/'cancel').exists()

def test_evaluation_freezes_source(state,monkeypatch):
    class Process: pid=123
    monkeypatch.setattr(core.subprocess,'Popen',lambda *a,**kw:Process())
    ws=core.reset(); first=core.run(ws['workspace_id'],'first')
    core.update(first['run_id'],status='completed')
    (Path(ws['path'])/'ip_stride.cc').write_text('changed after submit')
    final=core.evaluate(first['run_id'],'final')
    saved=json.loads((state/'runs'/final['run_id']/'input.json').read_text())
    assert saved['files']['ip_stride.cc']!='changed after submit'

def test_report_escapes_code(tmp_path):
    report(tmp_path/'r.html',{'error':'<script>alert(1)</script>'})
    assert '<script>' not in (tmp_path/'r.html').read_text()

def test_deadline_validation(state):
    wid=core.reset()['workspace_id']
    for value in [0,3601,True,'3']:
        with pytest.raises(ValueError): core.run(wid,'bad-time',timeout_seconds=value)

def test_real_task_is_frozen_and_distinct(state,monkeypatch):
    class Process: pid=123
    monkeypatch.setattr(core.subprocess,'Popen',lambda *a,**kw:Process())
    ws=core.reset('prefetch-dpc3')
    result=core.run(ws['workspace_id'],'real')
    saved=json.loads((state/'runs'/result['run_id']/'input.json').read_text())
    assert result['data_kind']=='dpc3-spec-prefix'
    assert saved['task']['simulation_instructions']==2000000
    assert set(saved['task']['traces']['development']).isdisjoint(saved['task']['traces']['validation'])
    assert core.reset()['task']['data_kind']=='synthetic-smoke'
    with pytest.raises(ValueError):core.reset('../escape')
