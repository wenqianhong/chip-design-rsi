"""Bounded Linux module commands: kill the process group on timeout."""
import os
import signal
import subprocess


def run(args, *, timeout, **kwargs):
    with subprocess.Popen(args, start_new_session=True, **kwargs) as proc:
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            raise
        return subprocess.CompletedProcess(args, proc.returncode)
