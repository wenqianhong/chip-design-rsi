import json
from types import SimpleNamespace
from chipbench import core,recovery

def test_recovery_cleans_only_recorded_dead_worker(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'STATE',tmp_path)
    monkeypatch.setattr(core.subprocess,'Popen',lambda *a,**kw:SimpleNamespace(pid=123456789))
    wid=core.reset()['workspace_id']; run=core.run(wid,'interrupted')
    def dead(pid,sig): raise ProcessLookupError()
    monkeypatch.setattr(recovery.os,'kill',dead)
    monkeypatch.setattr(core,'lima',lambda:'/test/limactl')
    calls=[]
    def execute(args,**kwargs):
        calls.append(args)
        if args[1]=='list':
            return SimpleNamespace(returncode=0,stdout=json.dumps({'name':'chipbench-'+run['run_id']})+'\n'+json.dumps({'name':'unrelated-vm'})+'\n')
        return SimpleNamespace(returncode=0,stdout='')
    monkeypatch.setattr(recovery.subprocess,'run',execute)
    assert recovery.recover()['recovered']==[run['run_id']]
    assert calls[-1][3]=='chipbench-'+run['run_id']
    assert all('unrelated-vm' not in args for args in calls)
    assert core.inspect(run['run_id'])['status']=='infra_error'
