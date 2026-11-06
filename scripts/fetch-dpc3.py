#!/usr/bin/env python3
"""Cache exact first trace records using a bounded HTTP range, never redistribute data."""
import concurrent.futures,hashlib,json,lzma,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=json.loads((ROOT/'tasks/prefetch-dpc3/task.json').read_text())
out=ROOT/'.tools/dpc3';out.mkdir(exist_ok=True)
def fetch(name):
    url=spec['source']+name+'.champsimtrace.xz'
    request=urllib.request.Request(url,headers={'Range':'bytes=0-67108863'})
    size=spec['prefix_records']*64
    dec=lzma.LZMADecompressor();data=bytearray();download=hashlib.sha256();received=0
    with urllib.request.urlopen(request,timeout=120) as response:
        headers=dict(response.headers)
        while len(data)<size:
            block=response.read(1024*1024)
            if not block: raise RuntimeError('Trace prefix too short')
            received+=len(block);download.update(block)
            data.extend(dec.decompress(block,max_length=size-len(data)))
            while not dec.needs_input and len(data)<size:
                data.extend(dec.decompress(b'',max_length=size-len(data)))
    dest=out/(name+'.champsimtrace.xz')
    dest.write_bytes(lzma.compress(data,preset=1))
    row={'name':name,'url':url,'source_headers':headers,'downloaded_bytes':received,'downloaded_prefix_sha256':download.hexdigest(),'record_count':len(data)//64,'raw_prefix_sha256':hashlib.sha256(data).hexdigest(),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'cached_bytes':dest.stat().st_size}
    print(json.dumps(row),flush=True)
    return row
names=sum(spec['traces'].values(),[])
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(fetch,names))
pinned=ROOT/'tasks/prefetch-dpc3/data-manifest.json'
if pinned.exists():
    expected={r['name']:r['raw_prefix_sha256'] for r in json.loads(pinned.read_text())['traces']}
    for row in rows:
        if row['raw_prefix_sha256']!=expected.get(row['name']):raise RuntimeError('Upstream trace changed: '+row['name'])
(out/'manifest.json').write_text(json.dumps({'task':spec,'traces':rows},indent=2))
