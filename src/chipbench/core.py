from __future__ import annotations
import difflib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid

ROOT = Path(os.environ.get('CHIPBENCH_ROOT', Path(__file__).resolve().parents[2])).resolve()
STATE = Path(os.environ.get('CHIPBENCH_STATE', ROOT / '.chipbench')).resolve()
ALLOWED = ('ip_stride.cc', 'ip_stride.h')
TERMINAL = {'completed', 'compile_error', 'timeout', 'oom', 'invalid_result', 'infra_error', 'cancelled'}

def envelope(**values):
    return {'schema_version': '1', **values}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def db():
    STATE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE/'state.sqlite', timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, created REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, workspace TEXT, request TEXT UNIQUE, fingerprint TEXT, status TEXT, created REAL, pid INTEGER, record TEXT)')
    return conn

def task(task_id='prefetch-smoke'):
    if task_id not in ('prefetch-smoke', 'prefetch-dpc3'): raise ValueError('Unknown task')
    return json.loads((ROOT/'tasks'/task_id/'task.json').read_text())

def workspace_task(wid):
    meta=STATE/'workspace-tasks'/f'{wid}.json'
    return json.loads(meta.read_text()) if meta.exists() else task()


def lima():
    binary = ROOT/'.tools/lima/bin/limactl'
    return str(binary) if binary.is_file() else shutil.which('limactl')

def doctor():
    binary = lima()
    instances = []
    error = None
    if binary:
        try:
            proc = subprocess.run([binary, 'list', '--json'], capture_output=True, text=True, timeout=15)
            instances = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
            if proc.returncode: error = proc.stderr[-1000:]
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc: error = str(exc)
    base = next((x for x in instances if x['name']=='chipbench-base'), None)
    manifest = ROOT/'.chipbench-base.json'
    ready = bool(binary and base and base.get('status')=='Stopped' and manifest.exists() and platform.system()=='Darwin' and platform.machine()=='arm64' and shutil.disk_usage(ROOT).free>8*2**30)
    return envelope(status='ready' if ready else 'setup_required', host={'system':platform.system(), 'arch':platform.machine(), 'free_gib':round(shutil.disk_usage(ROOT).free/2**30,1)}, lima=binary, base_status=base.get('status') if base else 'missing', manifest=manifest.exists(), error=error, next_step=None if ready else 'Run scripts/setup-local.sh; base must be provisioned and stopped.')

def list_tasks():
    return envelope(status='ok', tasks=[task(), task('prefetch-dpc3')])

def reset(task_id='prefetch-smoke'):
    spec=task(task_id)
    wid = 'w-' + uuid.uuid4().hex[:16]
    path = STATE/'workspaces'/wid
    path.mkdir(parents=True)
    for name in ALLOWED: shutil.copyfile(ROOT/'tasks'/task_id/name, path/name)
    meta=STATE/'workspace-tasks'; meta.mkdir(parents=True,exist_ok=True)
    (meta/f'{wid}.json').write_text(json.dumps(spec))
    with db() as c: c.execute('INSERT INTO workspaces VALUES (?,?)',(wid,time.time()))
    return envelope(status='ready', workspace_id=wid, path=str(path), task=spec, files={n:(path/n).read_text() for n in ALLOWED})

def workspace(wid):
    if not re.fullmatch(r'w-[a-f0-9]{16}', wid): raise ValueError('Invalid workspace ID')
    with db() as c:
        if not c.execute('SELECT id FROM workspaces WHERE id=?',(wid,)).fetchone(): raise ValueError('Unknown workspace')
    return STATE/'workspaces'/wid

def snapshot(wid, files=None):
    path = workspace(wid)
    if files is not None:
        if set(files)!=set(ALLOWED): raise ValueError('Supply exactly ip_stride.cc and ip_stride.h')
        values=files
    else:
        if path.is_symlink() or any(p.is_symlink() or p.name not in ALLOWED or not p.is_file() for p in path.iterdir()):
            raise ValueError('Workspace contains a symlink or disallowed file')
        values={n:(path/n).read_text() for n in ALLOWED}
    if any(not isinstance(v,str) or len(v.encode())>128*1024 or '\x00' in v for v in values.values()):
        raise ValueError('Source must be UTF-8 text, at most 128 KiB per file, without NUL')
    return values

def run(wid, request_id, files=None, kind='development', parent=None, timeout_seconds=3600):
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600: raise ValueError('timeout_seconds must be an integer from 1 to 3600')
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',request_id): raise ValueError('request_id must be 1-100 safe characters')
    if kind not in ('development','validation'): raise ValueError('Invalid run kind')
    content=snapshot(wid,files)
    spec=workspace_task(wid)
    payload={'workspace_id':wid,'files':content,'kind':kind,'parent':parent,'task':spec,'timeout_seconds':timeout_seconds}
    fingerprint=digest(json.dumps(payload,sort_keys=True).encode())
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT id,fingerprint FROM runs WHERE request=?',(request_id,)).fetchone()
        if existing:
            if existing['fingerprint']!=fingerprint: raise ValueError('request_id already used for different input')
            return inspect(existing['id'])
        count=c.execute("SELECT COUNT(*) FROM runs WHERE workspace=? AND json_extract(record,'$.kind')=?",(wid,kind)).fetchone()[0]
        if count >= (spec['max_submissions'] if kind=='development' else 1): raise ValueError('Submission budget exhausted; reset for a new experiment')
        rid='r-'+uuid.uuid4().hex[:16]
        folder=STATE/'runs'/rid; folder.mkdir(parents=True)
        record=envelope(run_id=rid,workspace_id=wid,status='queued',kind=kind,parent=parent,source_sha256=fingerprint,created_at=time.time(),data_kind=spec['data_kind'],metrics=None,error=None,artifacts={})
        (folder/'input.json').write_text(json.dumps(payload))
        patch=''.join(''.join(difflib.unified_diff((ROOT/'tasks'/spec['id']/n).read_text().splitlines(keepends=True),content[n].splitlines(keepends=True),fromfile='a/prefetcher/ip_stride/'+n,tofile='b/prefetcher/ip_stride/'+n)) for n in ALLOWED)
        (folder/'candidate.patch').write_text(patch)
        c.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)',(rid,wid,request_id,fingerprint,'queued',time.time(),None,json.dumps(record)))
    env=os.environ.copy(); env.update(CHIPBENCH_ROOT=str(ROOT),CHIPBENCH_STATE=str(STATE))
    try:
        with (folder/'worker.log').open('wb') as log:
            process=subprocess.Popen([sys.executable,'-m','chipbench.worker',rid],cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
        with db() as c: c.execute('UPDATE runs SET pid=? WHERE id=?',(process.pid,rid))
    except OSError as exc:
        update(rid,status='infra_error',error=str(exc))
    return inspect(rid)

def inspect(rid, offset=0, limit=12000):
    if not re.fullmatch(r'r-[a-f0-9]{16}',rid): raise ValueError('Invalid run ID')
    if offset<0 or limit<0 or limit>64000: raise ValueError('Invalid log window')
    with db() as c: row=c.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
    if not row: raise ValueError('Unknown run')
    record=json.loads(row['record']); record['status']=row['status']
    log=STATE/'runs'/rid/'execution.log'
    if log.exists():
        with log.open('rb') as stream:
            stream.seek(offset); data=stream.read(limit)
        record['log']={'offset':offset,'next_offset':offset+len(data),'text':data.decode(errors='replace')}
    return record

def update(rid, **fields):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT record FROM runs WHERE id=?',(rid,)).fetchone()
        record=json.loads(row['record']); record.update(fields)
        c.execute('UPDATE runs SET status=?,record=? WHERE id=?',(record['status'],json.dumps(record),rid))
    return record

def cancel(rid):
    current=inspect(rid)
    if current['status'] in TERMINAL: return current
    (STATE/'runs'/rid/'cancel').touch()
    return envelope(run_id=rid,status='cancelling',message='Worker will stop and delete only its own VM.')

def evaluate(rid,request_id):
    previous=inspect(rid)
    if previous['status']!='completed' or previous['kind']!='development':
        raise ValueError('Evaluate a completed development run')
    payload=json.loads((STATE/'runs'/rid/'input.json').read_text())
    return run(previous['workspace_id'],request_id,payload['files'],'validation',rid)
