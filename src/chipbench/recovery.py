"""Recover only project jobs whose detached workers no longer exist."""
import json
import os
import subprocess
from . import core
from .metrics import report

def recover():
    recovered=[]
    with core.db() as conn: rows=conn.execute('SELECT id,pid,status FROM runs').fetchall()
    for row in rows:
        if row['status'] in core.TERMINAL: continue
        # A missing PID immediately after submission is not evidence of a dead worker.
        if row['pid'] is None: continue
        try: os.kill(row['pid'],0)
        except ProcessLookupError: pass
        except PermissionError: continue
        else: continue
        name='chipbench-'+row['id']
        binary=core.lima()
        if not binary: continue
        process=subprocess.run([binary,'list','--json'],capture_output=True,text=True,timeout=15)
        if process.returncode: continue
        names={json.loads(x)['name'] for x in process.stdout.splitlines() if x.strip()}
        if name in names:
            cleaned=subprocess.run([binary,'delete','--force',name,'--tty=false'],capture_output=True,text=True,timeout=90)
            if cleaned.returncode: continue
        record=core.update(row['id'],status='infra_error',error='Worker interrupted; stale VM cleaned by recover',cleanup_ok=True)
        folder=core.STATE/'runs'/row['id']
        (folder/'result.json').write_text(json.dumps(record,indent=2))
        report(folder/'report.html',record)
        recovered.append(row['id'])
    return core.envelope(status='ok',recovered=recovered)
