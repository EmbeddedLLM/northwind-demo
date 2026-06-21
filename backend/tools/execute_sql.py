import asyncio
import sqlite3

from pydantic import BaseModel

from kosong.tooling import CallableTool2, ToolOk, ToolReturnValue

try:
    from ..settings import DB_PATH
    from .common import executor
except ImportError:
    from backend.settings import DB_PATH
    from backend.tools.common import executor


class SqlParams(BaseModel):
    query: str


def _execute_sql(query: str) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.close()
    except Exception as e:
        return f"SQL ERROR: {e}"
    if not rows:
        return "Query returned no results."
    cw = [
        max(len(str(c)), max(len(str(r[i])) for r in rows)) for i, c in enumerate(cols)
    ]
    sep = "+-" + "-+-".join("-" * w for w in cw) + "-+"
    header = "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, cw)) + " |"
    body = [
        "| " + " | ".join(str(v).ljust(w) for v, w in zip(row, cw)) + " |"
        for row in rows
    ]
    return "\n".join(
        [sep, header, sep]
        + body
        + [sep, f"({len(rows)} row{'s' if len(rows) != 1 else ''})"]
    )


class SqlTool(CallableTool2[SqlParams]):
    name = "execute_sql"
    description = (
        "Execute a SQLite SELECT query against Northwind. Returns table or SQL ERROR."
    )
    params = SqlParams

    def __init__(self, emit):
        super().__init__()
        self._emit = emit

    async def __call__(self, p: SqlParams) -> ToolReturnValue:
        await self._emit({"type": "sql_call", "query": p.query})
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, _execute_sql, p.query)
        await self._emit(
            {"type": "sql_result", "result": result, "success": "ERROR" not in result}
        )
        return ToolOk(output=result)
