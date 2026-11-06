#!/usr/bin/env python3
"""Runs as an unprivileged user inside a new network namespace in the VM."""
import json
import os
from pathlib import Path
import resource
import shutil
import socket
import subprocess
import sys
import time

resource.setrlimit(resource.RLIMIT_FSIZE, (128*1024*1024,128*1024*1024))
resource.setrlimit(resource.RLIMIT_NOFILE, (256,256))
resource.setrlimit(resource.RLIMIT_NPROC, (256,256))
root=Path('/tmp/chipbench-job')
payload=json.loads((root/'input.json').read_text())
out={'status':'running','metrics':{},'error':None,'network_isolated':False}
started=time.monotonic()

def call(args, timeout, cwd):
    remaining=3300-(time.monotonic()-started)
    if remaining<=0: raise subprocess.TimeoutExpired(args,3300)
    print('RUN:', ' '.join(args), flush=True)
    subprocess.run(args,check=True,timeout=min(timeout,remaining),cwd=cwd,stdin=subprocess.DEVNULL)

def simulations(binary,label,names,repeats):
    rows={}
    for name in names:
        rows[name]=[]
        for repeat in range(repeats):
            result=root/f'{label}-{name}-{repeat}.json'
            call([str(binary),'--warmup-instructions',str(payload['task']['warmup_instructions']),'--simulation-instructions',str(payload['task']['simulation_instructions']),'--json',str(result),f'/opt/chipbench/traces/{name}.champsimtrace.xz'],600,root)
            if result.stat().st_size>1024*1024: raise ValueError('Oversized simulation JSON')
            rows[name].append(json.loads(result.read_text()))
    out['metrics'][label]=rows

try:
    # Namespace must contain no external interfaces; no candidate code has run yet.
    interfaces=[name for _,name in socket.if_nameindex()]
    if interfaces!=['lo']: raise ValueError(f'Unexpected network interfaces: {interfaces}')
    try:
        socket.create_connection(('1.1.1.1',443),timeout=2)
        raise ValueError('Unexpected outbound connectivity')
    except OSError:
        out['network_isolated']=True
    call(['cp','-a','/opt/chipbench/ChampSim',str(root/'ChampSim')],120,root)
    work=root/'ChampSim'
    # Files were owned by root in the image; cp creates worker-owned copies.
    names=payload['task']['traces'][payload['kind']]
    repeats=payload['task'].get('repeats',3)
    simulations(work/'bin/no_prefetch','no_prefetch',names,1)
    simulations(work/'bin/baseline','baseline',names,repeats)
    for name,content in payload['files'].items():
        if name not in ('ip_stride.cc','ip_stride.h'): raise ValueError('Disallowed candidate file')
        (work/'prefetcher/ip_stride'/name).write_text(content)
    out['status']='compiling'
    call(['./config.sh','chipbench-config.json'],60,work)
    call(['make','-j2'],300,work)
    out['status']='simulating'
    simulations(work/'bin/baseline','candidate',names,repeats)
    out['status']='completed'
except subprocess.TimeoutExpired as exc:
    out.update(status='timeout',error=str(exc))
except subprocess.CalledProcessError as exc:
    out.update(status='compile_error' if out['status']=='compiling' else 'invalid_result',error=str(exc))
except Exception as exc:
    out.update(status='invalid_result',error=str(exc))
finally:
    out['peak_child_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    out['elapsed_seconds']=round(time.monotonic()-started,3)
    (root/'result.json').write_text(json.dumps(out,allow_nan=False))
