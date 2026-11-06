#!/usr/bin/env python3
"""Keep provisioning mutually exclusive with running experiments."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
state=Path(os.environ.get('CHIPBENCH_STATE',root/'.chipbench'))
state.mkdir(parents=True,exist_ok=True)
with (state/'runner.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    env={**os.environ,'CHIPBENCH_SETUP_LOCKED':'1'}
    sys.exit(subprocess.call(['bash',str(root/'scripts/setup-local.sh')],env=env))
