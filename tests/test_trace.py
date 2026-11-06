import importlib.util
import lzma
from pathlib import Path

def test_synthetic_trace_format(tmp_path):
    spec=importlib.util.spec_from_file_location('traces',Path('scripts/generate_traces.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    manifest=module.generate(tmp_path)
    assert len(manifest)==6
    data=lzma.open(tmp_path/'stream.champsimtrace.xz','rb').read()
    assert len(data)==80000*64
    first=module.record.unpack(data[:64])
    assert first[0]==0x400000 and first[-4]==0x1000000
