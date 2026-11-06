#!/usr/bin/env python3
"""Original deterministic synthetic traces matching ChampSim input_instr (64 bytes).
Not SPEC, not measured program traces, not suitable for research performance claims.
"""
import hashlib
import json
import lzma
from pathlib import Path
import random
import struct
import sys

record = struct.Struct('<QBB2B4B2Q4Q')
assert record.size == 64

def generate(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for index, (name, stride) in enumerate([('stream', 1), ('stride4', 4), ('mixed', 0), ('validation2', 2), ('validation8', 8), ('validation_random', 0)]):
        rng = random.Random(700 + index)
        path = out / (name + '.champsimtrace.xz')
        with lzma.open(path, 'wb') as f:
            for i in range(80000):
                address = 0x1000000 + (i * stride if stride else rng.randrange(65536)) * 64
                f.write(record.pack(0x400000 + (i % 16)*4, 0, 0, 1+i%4, 0, 0, 0, 0, 0, 0, 0, address, 0, 0, 0))
        manifest[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'records': 80000, 'kind': 'synthetic'}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest

if __name__ == '__main__': generate(sys.argv[1])
