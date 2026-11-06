"""Detached local runner. Serializes VM access and guarantees best-effort teardown."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from . import core
from .metrics import parse_stats, compare, report

class Cancelled(Exception): pass
class CommandError(Exception): pass

def main(rid):
    folder=core.STATE/'runs'/rid
    name='chipbench-'+rid
    binary=core.lima()
    log=folder/'execution.log'
    timeout_seconds=json.loads((folder/'input.json').read_text()).get('timeout_seconds',3600)
    deadline=time.monotonic()+timeout_seconds
    def cancelled():
        if (folder/'cancel').exists(): raise Cancelled('Cancelled by user')
        if time.monotonic()>deadline: raise TimeoutError('Total run budget exceeded')
    def command(args,timeout=180, cleanup=False, capture=False):
        if not cleanup: cancelled()
        with log.open('ab') as output:
            output.write(('\n$ '+' '.join(map(str,args))+'\n').encode()); output.flush()
            # Stream to disk with a size cap; never buffer unbounded guest output.
            target=(folder/'capture.tmp').open('wb') if capture else output
            proc=subprocess.Popen(list(map(str,args)),stdin=subprocess.DEVNULL,stdout=target,stderr=output,start_new_session=True)
            end=time.monotonic()+timeout
            try:
                while proc.poll() is None:
                    if not cleanup: cancelled()
                    if time.monotonic()>end: raise TimeoutError('Command deadline exceeded')
                    if not cleanup and log.stat().st_size>8*1024*1024: raise CommandError('Log size limit exceeded')
                    if capture and (folder/'capture.tmp').stat().st_size>8*1024*1024: raise CommandError('Result size limit exceeded')
                    time.sleep(.2)
                if capture and (folder/'capture.tmp').stat().st_size>8*1024*1024: raise CommandError('Result size limit exceeded')
                if proc.returncode: raise CommandError(f'Command exited {proc.returncode}; see execution.log')
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try: proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL); proc.wait()
                if capture: target.close()
        return (folder/'capture.tmp').read_text() if capture else None
    def shell(*args,timeout=180,capture=False):
        return command([binary,'shell','--workdir=/tmp',name,*args],timeout,capture=capture)
    locked=False; created=False; state='infra_error'; error=None; metrics=None
    lock=(core.STATE/'runner.lock').open('w')
    try:
        if not binary: raise CommandError('Lima is not installed')
        while not locked:
            cancelled()
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); locked=True
            except BlockingIOError: time.sleep(.5)
        readiness=core.doctor()
        if readiness['status']!='ready': raise CommandError(readiness['next_step'])
        manifest=json.loads((core.ROOT/'.chipbench-base.json').read_text())
        manifest['guest_runner_sha256']=core.digest((core.ROOT/'environments/guest_run.py').read_bytes())
        core.update(rid,status='building',environment=manifest,vm=name)
        # Mark before creation so partially-created instances are also cleaned up.
        created=True
        command([binary,'clone','chipbench-base',name,'--tty=false'],180)
        command([binary,'start',name,'--tty=false'],180)
        shell('sudo','mkdir','-p','/tmp/chipbench-job')
        command([binary,'copy',folder/'input.json',f'{name}:/tmp/input.json'])
        command([binary,'copy',core.ROOT/'environments/guest_run.py',f'{name}:/tmp/guest_run.py'])
        shell('sudo','mv','/tmp/input.json','/tmp/chipbench-job/input.json')
        shell('sudo','chown','-R','chipworker:chipworker','/tmp/chipbench-job')
        core.update(rid,status='running')
        shell('sudo','unshare','--net','--','runuser','-u','chipworker','--','python3','/tmp/guest_run.py',timeout=3400)
        raw=shell('sudo','cat','/tmp/chipbench-job/result.json',capture=True)
        (folder/'raw-result.json').write_text(raw)
        result=json.loads(raw)
        if result['status']!='completed':
            state=result['status'] if result['status'] in core.TERMINAL else 'invalid_result'
            raise ValueError(result.get('error','Guest failed'))
        if result.get('network_isolated') is not True: raise ValueError('Network isolation check missing')
        core.update(rid,status='evaluating')
        values={}; stability={}
        payload=json.loads((folder/'input.json').read_text())
        expected=set(payload['task']['traces'][payload['kind']])
        for label in ('baseline','candidate','no_prefetch'):
            if set(result['metrics'][label])!=expected: raise ValueError('Missing or unexpected trace')
            values[label]={}; stability[label]={}
            for trace,repeats in result['metrics'][label].items():
                if len(repeats)!=(1 if label=='no_prefetch' else payload['task'].get('repeats',3)): raise ValueError('Wrong repetition count')
                parsed=[parse_stats(x,payload['task']['simulation_instructions']) for x in repeats]
                ipcs=[x['ipc'] for x in parsed]; mean=sum(ipcs)/len(ipcs)
                spread=(max(ipcs)-min(ipcs))/mean
                if spread>.001: raise ValueError('Unstable IPC across repetitions')
                values[label][trace]={**parsed[0],'ipc':mean,'repeated_ipc':ipcs}
                stability[label][trace]=spread
        metrics={**compare(values['baseline'],values['candidate']),'runs':values,'relative_spread':stability,'network_isolated':True,'guest_elapsed_seconds':result['elapsed_seconds'],'peak_child_rss_kib':result.get('peak_child_rss_kib')}
        metrics['interpretation']=payload['task']['evaluation']
        state='completed'
    except Cancelled as exc: state='cancelled'; error=str(exc)
    except TimeoutError as exc: state='timeout'; error=str(exc)
    except ValueError as exc:
        if state=='infra_error': state='invalid_result'
        error=str(exc)
    except Exception as exc: error=str(exc)
    finally:
        cleanup_error=None
        if created:
            try: command([binary,'delete','--force',name,'--tty=false'],90,cleanup=True)
            except Exception as exc: cleanup_error=str(exc)
        if cleanup_error:
            state='infra_error'; error=f'{error or "Run finished"}; cleanup failed: {cleanup_error}'
        record=core.update(rid,status=state,error=error,metrics=metrics,finished_at=time.time(),cleanup_ok=not cleanup_error,
            artifacts={'input':str(folder/'input.json'),'patch':str(folder/'candidate.patch'),'raw_result':str(folder/'raw-result.json') if (folder/'raw-result.json').exists() else None,'log':str(log),'report':str(folder/'report.html')})
        (folder/'result.json').write_text(json.dumps(record,indent=2))
        report(folder/'report.html',record)
        lock.close()

if __name__=='__main__': main(sys.argv[1])
