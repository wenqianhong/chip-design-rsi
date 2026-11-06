import argparse
import json
import sys
from . import core

def main():
    parser=argparse.ArgumentParser(description='Chipbench: local VM experiments for agents')
    parser.add_argument('--json',action='store_true',help='Stable JSON (also the default)')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('doctor','tasks','mcp','recover'): sub.add_parser(name)
    reset=sub.add_parser('reset'); reset.add_argument('task_id',nargs='?',default='prefetch-smoke')
    run=sub.add_parser('run'); run.add_argument('workspace_id'); run.add_argument('--request-id',required=True)
    run.add_argument('--timeout-seconds',type=int,default=3600)
    run.add_argument('--files-json',help='UTF-8 JSON map of the two candidate source files')
    inspect=sub.add_parser('inspect'); inspect.add_argument('run_id'); inspect.add_argument('--offset',type=int,default=0); inspect.add_argument('--limit',type=int,default=12000)
    cancel=sub.add_parser('cancel'); cancel.add_argument('run_id')
    evaluate=sub.add_parser('evaluate'); evaluate.add_argument('run_id'); evaluate.add_argument('--request-id',required=True)
    args=parser.parse_args()
    try:
        if args.command=='mcp':
            from .server import serve
            serve(); return
        if args.command=='recover':
            from .recovery import recover
            result=recover()
        elif args.command=='doctor': result=core.doctor()
        elif args.command=='tasks': result=core.list_tasks()
        elif args.command=='reset': result=core.reset(args.task_id)
        elif args.command=='run':
            files=None
            if args.files_json:
                from pathlib import Path
                path=Path(args.files_json)
                if path.stat().st_size>300*1024: raise ValueError('Input file too large')
                files=json.loads(path.read_text())
            result=core.run(args.workspace_id,args.request_id,files,timeout_seconds=args.timeout_seconds)
        elif args.command=='inspect': result=core.inspect(args.run_id,args.offset,args.limit)
        elif args.command=='cancel': result=core.cancel(args.run_id)
        else: result=core.evaluate(args.run_id,args.request_id)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps(core.envelope(status='error',error=str(exc)),ensure_ascii=False))
        sys.exit(2)

if __name__=='__main__': main()
