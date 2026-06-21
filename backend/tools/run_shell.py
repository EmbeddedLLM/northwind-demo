import asyncio
import subprocess

from pydantic import BaseModel

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnValue

try:
    from ..settings import ALLOWED_SHELL, WORKSPACE_DIR
    from .common import executor
except ImportError:
    from backend.settings import ALLOWED_SHELL, WORKSPACE_DIR
    from backend.tools.common import executor


class ShellParams(BaseModel):
    command: str


def _run_shell(command: str) -> str:
    cmd_name = command.strip().split()[0]
    if cmd_name not in ALLOWED_SHELL:
        return f"SHELL ERROR: '{cmd_name}' not permitted."
    if ".." in command:
        return "SHELL ERROR: '..' path traversal not allowed."
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (r.stdout + r.stderr).strip()
        return out or "(command completed, no output)"
    except Exception as e:
        return f"SHELL ERROR: {e}"


class ShellTool(CallableTool2[ShellParams]):
    name = "run_shell"
    description = (
        f"Run a shell command in workspace/ (cwd=workspace/). "
        f"Allowed: {sorted(ALLOWED_SHELL)}. Relative paths only. No '..'."
    )
    params = ShellParams

    def __init__(self, emit):
        super().__init__()
        self._emit = emit

    async def __call__(self, p: ShellParams) -> ToolReturnValue:
        await self._emit({"type": "shell_call", "command": p.command})
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, _run_shell, p.command)
        success = "ERROR" not in result
        await self._emit({"type": "shell_result", "result": result, "success": success})
        return (
            ToolOk(output=result)
            if success
            else ToolError(message=result, brief="Shell error")
        )
