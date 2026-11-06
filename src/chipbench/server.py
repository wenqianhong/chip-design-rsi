from typing import Any
from mcp.server.fastmcp import FastMCP
from . import core

mcp=FastMCP('chipbench',instructions='Run chip_doctor first. Reset a task, edit only the two allowed files, submit with a unique request_id, then poll chip_inspect. Runs use isolated Lima VMs. Read task data_kind and evaluation scope. Smoke is synthetic; DPC3 uses fixed short real-trace prefixes.')

@mcp.tool(structured_output=True)
def chip_doctor() -> dict[str, Any]:
    """Check local Lima, prepared VM and free space. Does not install anything."""
    return core.doctor()

@mcp.tool(structured_output=True)
def chip_list_tasks() -> dict[str, Any]:
    """Discover tasks, edit boundaries and budgets."""
    return core.list_tasks()

@mcp.tool(structured_output=True)
def chip_reset(task_id: str='prefetch-smoke') -> dict[str, Any]:
    """Create a clean workspace and return its source files and description."""
    return core.reset(task_id)

@mcp.tool(structured_output=True)
def chip_run(workspace_id: str, request_id: str, files: dict[str,str] | None=None, timeout_seconds: int=3600) -> dict[str, Any]:
    """Submit a candidate; returns run_id immediately. Pass both source files, or edit the returned local workspace. Reuse request_id only for identical retries. Maximum three development submissions."""
    return core.run(workspace_id,request_id,files,timeout_seconds=timeout_seconds)

@mcp.tool(structured_output=True)
def chip_inspect(run_id: str, offset: int=0, limit: int=12000) -> dict[str, Any]:
    """Read status, metrics, report location and a bounded log window. Poll running jobs."""
    return core.inspect(run_id,offset,limit)

@mcp.tool(structured_output=True)
def chip_cancel(run_id: str) -> dict[str, Any]:
    """Request cancellation and VM cleanup; poll until terminal. Idempotent."""
    return core.cancel(run_id)

@mcp.tool(structured_output=True)
def chip_evaluate(run_id: str, request_id: str) -> dict[str, Any]:
    """Freeze a completed development candidate and run the task-specific validation traces. This is a public held-out workload, not a secret benchmark. One final evaluation per workspace."""
    return core.evaluate(run_id,request_id)

def serve(): mcp.run(transport='stdio')
