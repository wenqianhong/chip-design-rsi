#!/usr/bin/env python3
"""Provision, run and collect independent v0.2 checks; never invoke a model."""
import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMA = str(ROOT / '.tools/lima/bin/limactl')
VM = 'chipbench-modules'
OUT = ROOT / '.chipbench/modules'
SOURCES = ROOT / 'environments/modules'
RUNNERS = {
    'logic': ['run_logic.py'],
    'drc': ['drc_fixtures.py', 'run_drc.py'],
    'mapping': ['run_mapping.py'],
    'physical': ['physical.tcl', 'run_physical.py'],
    'layout': ['stream_layout.py', 'run_layout.py'],
    'timeout': ['check_timeout.py'],
}


def call(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def shell(*args, **kwargs):
    return call([LIMA, 'shell', '--workdir=/tmp', VM, *args], **kwargs)


def guest_root():
    home = shell('printenv', 'HOME', capture_output=True, text=True).stdout.strip()
    if not home.startswith('/') or '\n' in home:
        raise ValueError('Invalid guest home')
    return home + '/chipbench-modules'


def copy(name, destination):
    call([LIMA, 'copy', str(SOURCES / name), VM + ':' + destination])


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('command', choices=['setup', 'status', *RUNNERS, 'collect', 'stop'])
args = parser.parse_args()
OUT.mkdir(parents=True, exist_ok=True)
if args.command == 'status':
    call([LIMA, 'list', '--json', VM])
    for path in sorted((OUT / 'results').glob('*-results.json')):
        print(path.name)
        print(path.read_text())
elif args.command == 'stop':
    call([LIMA, 'stop', VM])
elif args.command == 'setup':
    instances = call([LIMA, 'list', '--json'], capture_output=True, text=True)
    exists = any(json.loads(line)['name'] == VM for line in instances.stdout.splitlines() if line.strip())
    if exists:
        call([LIMA, 'start', VM, '--tty=false'])
    else:
        call([LIMA, 'start', '--name=' + VM, '--tty=false', str(SOURCES / 'lima.yaml')])
    guest = guest_root()
    shell('mkdir', '-p', guest + '/fixtures', guest + '/results')
    copy('provision.sh', guest + '/provision.sh')
    proxy = os.environ.get('CHIPBENCH_BUILD_PROXY', '')
    env = ['http_proxy=' + proxy, 'https_proxy=' + proxy] if proxy else []
    shell('env', *env, 'bash', guest + '/provision.sh')
elif args.command in RUNNERS:
    call([LIMA, 'start', VM, '--tty=false'])
    guest = guest_root()
    shell('mkdir', '-p', guest + '/fixtures', guest + '/results')
    copy('process.py', guest + '/process.py')
    if args.command in ('logic', 'mapping'):
        for name in ('counter.sv', 'counter_tb.sv'):
            copy(name, guest + '/fixtures/' + name)
    for name in RUNNERS[args.command]:
        copy(name, guest + '/' + name)
    shell('python3', guest + '/' + RUNNERS[args.command][-1])
else:
    guest = guest_root()
    call([LIMA, 'copy', '-r', VM + ':' + guest + '/results', str(OUT)])
    print(OUT / 'results')
