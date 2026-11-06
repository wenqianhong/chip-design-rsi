#!/usr/bin/env python3
"""Generate reviewable client snippets; does not modify global client settings."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'integrations/local'; out.mkdir(parents=True,exist_ok=True)
command=str(root/'.venv/bin/chipbench')
(out/'codex.toml').write_text('[mcp_servers.chipbench]\ncommand = '+json.dumps(command)+'\nargs = ["mcp"]\n')
# New project-local configs are safe to create; never overwrite existing configs.
(root/'.codex').mkdir(exist_ok=True)
for source,target in [('codex.toml',root/'.codex/config.toml')]:
    if not target.exists(): target.write_text((out/source).read_text())
    else: print(f'Preserved existing {target}; compare with {out/source}')
print(out)
