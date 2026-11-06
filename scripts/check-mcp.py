#!/usr/bin/env python3
"""Verify the shipped MCP server without making a model/API call."""
import asyncio
import json
from pathlib import Path
import sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    root=Path(__file__).resolve().parents[1]
    params=StdioServerParameters(command=str(root/'.venv/bin/chipbench'),args=['mcp'])
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            print(json.dumps({'tools':[x.name for x in tools.tools]}))
            result=await session.call_tool('chip_doctor',{})
            print(json.dumps(result.structuredContent))
            if '--compile-error' in sys.argv:
                ws=(await session.call_tool('chip_reset',{})).structuredContent
                files=ws['files']; files['ip_stride.cc']='this is intentionally invalid C++\n'
                run=await session.call_tool('chip_run',{'workspace_id':ws['workspace_id'],'request_id':'mcp-compile-error-'+ws['workspace_id'],'files':files})
                print(json.dumps(run.structuredContent))
                (root/'.tools/mcp-error-run.json').write_text(json.dumps(run.structuredContent))

asyncio.run(main())
