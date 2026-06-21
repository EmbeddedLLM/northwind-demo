import asyncio
import io
import os
import shutil
import sqlite3
import textwrap
import traceback
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pydantic import BaseModel

from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnValue

try:
    from ..settings import DB_PATH, WORKSPACE_DIR
    from .common import executor
except ImportError:
    from backend.settings import DB_PATH, WORKSPACE_DIR
    from backend.tools.common import executor


class PythonParams(BaseModel):
    code: str


def _execute_python(code: str) -> str:
    ns = {
        "sqlite3": sqlite3,
        "pd": pd,
        "plt": plt,
        "shutil": shutil,
        "os": os,
        "Path": Path,
        "DB_PATH": str(DB_PATH),
        "WORKSPACE_DIR": str(WORKSPACE_DIR),
    }
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            exec(textwrap.dedent(code), ns)  # noqa: S102
        out = buf.getvalue().strip()
        return out or "Code executed successfully (no output)."
    except Exception:
        return f"PYTHON ERROR:\n{traceback.format_exc()}"


class PythonTool(CallableTool2[PythonParams]):
    name = "execute_python"
    description = (
        "Execute Python. Pre-loaded: sqlite3, pd, plt, shutil, os, Path, "
        "DB_PATH (str), WORKSPACE_DIR (str). Save charts to WORKSPACE_DIR. "
        "Always call plt.close() after savefig()."
    )
    params = PythonParams

    def __init__(self, emit):
        super().__init__()
        self._emit = emit

    async def __call__(self, p: PythonParams) -> ToolReturnValue:
        await self._emit({"type": "python_call", "code": p.code})
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, _execute_python, p.code)
        success = "ERROR" not in result
        await self._emit(
            {"type": "python_result", "result": result[:500], "success": success}
        )
        return (
            ToolOk(output=result)
            if success
            else ToolError(message=result, brief="Python error")
        )
