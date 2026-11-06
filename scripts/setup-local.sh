#!/bin/bash
# Run from a trusted checkout. Installs tooling under this repository, not system-wide.
set -euo pipefail
cd "$(dirname "$0")/.."
TASK_ROOT="$PWD"
PYTHON="${CHIPBENCH_PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,10), "Use Python 3.10+ via CHIPBENCH_PYTHON"'
if [ ! -x .venv/bin/python ]; then "$PYTHON" -m venv .venv; fi
if [ "${CHIPBENCH_SETUP_LOCKED:-}" != 1 ]; then
  exec .venv/bin/python scripts/with-runner-lock.py
fi
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
if [ ! -x .tools/lima/bin/limactl ]; then
  mkdir -p .tools/downloads .tools/lima
  curl -fL --retry 3 https://github.com/lima-vm/lima/releases/download/v2.3.0/lima-2.3.0-Darwin-arm64.tar.gz -o .tools/downloads/lima-2.3.0-Darwin-arm64.tar.gz
  .venv/bin/python - <<'PY'
import hashlib,tarfile
from pathlib import Path
p=Path('.tools/downloads/lima-2.3.0-Darwin-arm64.tar.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='b7af444bd8f91d3c307477e562f2cf3bd7595d62b9429185e4fa841563578cfc','Lima checksum mismatch'
with tarfile.open(p) as t:
    target=Path('.tools/lima').resolve()
    for member in t.getmembers():
        if not (target/member.name).resolve().is_relative_to(target): raise ValueError('Invalid archive path')
    t.extractall(target)
PY
fi
LIMA="$TASK_ROOT/.tools/lima/bin/limactl"
# Only manage the dedicated project base. Do not touch other Lima instances.
if "$LIMA" list --json | .venv/bin/python -c 'import sys,json; sys.exit(0 if any(json.loads(x)["name"]=="chipbench-base" for x in sys.stdin if x.strip()) else 1)'; then
  "$LIMA" start chipbench-base --tty=false
else
  "$LIMA" start --name=chipbench-base --tty=false environments/lima.yaml
fi
"$LIMA" shell --workdir=/tmp chipbench-base env "CHIPBENCH_BUILD_PROXY=${CHIPBENCH_BUILD_PROXY:-}" bash -s < environments/provision.sh
mkdir -p .tools/traces
.venv/bin/python scripts/generate_traces.py .tools/traces
"$LIMA" copy -r .tools/traces chipbench-base:/tmp/chipbench-traces
"$LIMA" shell --workdir=/tmp chipbench-base sudo cp -a /tmp/chipbench-traces/. /opt/chipbench/traces/
"$LIMA" shell --workdir=/tmp chipbench-base sudo chmod -R a+rX /opt/chipbench/traces
"$LIMA" shell --workdir=/tmp chipbench-base sudo unshare --net -- runuser -u chipworker -- python3 -c 'import socket; assert [n for _,n in socket.if_nameindex()]==["lo"]; print("ISOLATION_OK")'
"$LIMA" shell --workdir=/tmp chipbench-base cat /opt/chipbench/packages.txt > .tools/guest-packages.txt
"$LIMA" stop chipbench-base
.venv/bin/python - <<'PY'
import hashlib,json
from pathlib import Path
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
Path('.chipbench-base.json').write_text(json.dumps({'lima':'2.3.0','backend':'vz','arch':'aarch64','champsim_commit':'410cee62d9c429c043ea611325ce00e6c303be2a','image_sha256':'50e24e1fb79e89116e939d90aa7738f7af48c442fa1bc2510131e0b39c50348e','packages_sha256':h('.tools/guest-packages.txt'),'provision_sha256':h('environments/provision.sh'),'traces':json.loads(Path('.tools/traces/manifest.json').read_text())},indent=2))
PY
.venv/bin/chipbench doctor
