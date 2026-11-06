import asyncio
import os
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def test_real_stdio_protocol(tmp_path):
    async def run():
        env={**os.environ,'CHIPBENCH_STATE':str(tmp_path),'PYTHONPATH':str(Path('src').resolve())}
        params=StdioServerParameters(command=sys.executable,args=['-m','chipbench.cli','mcp'],env=env)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools()
                assert {x.name for x in tools.tools}=={'chip_doctor','chip_list_tasks','chip_reset','chip_run','chip_inspect','chip_cancel','chip_evaluate'}
                result=await session.call_tool('chip_reset',{})
                assert not result.isError
                assert result.structuredContent['workspace_id'].startswith('w-')
    asyncio.run(run())
