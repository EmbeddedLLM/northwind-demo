"""Kosong agent runtime for Alex, the Northwind AI Analyst.

This module owns the LLM provider, tools, prompts, report rendering, and
workspace business logic. HTTP concerns belong in main.py.
"""

import asyncio
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import textwrap
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from typing import AsyncGenerator

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

import kosong
from kosong.chat_provider.kimi import Kimi
from kosong.message import Message, TextPart
from kosong.tooling import CallableTool2, ToolError, ToolOk, ToolReturnValue
from kosong.tooling.simple import SimpleToolset

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from .models import RunRequest
    from .settings import (
        ALLOWED_SHELL,
        API_KEY,
        BASE_URL,
        DB_PATH,
        MODEL,
        REPORTS_DIR,
        WORKSPACE_DIR,
    )
except ImportError:
    from backend.models import RunRequest
    from backend.settings import (
        ALLOWED_SHELL,
        API_KEY,
        BASE_URL,
        DB_PATH,
        MODEL,
        REPORTS_DIR,
        WORKSPACE_DIR,
    )

_jinja_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=False
)
_report_tmpl = _jinja_env.get_template("report.html.j2")

_executor = ThreadPoolExecutor(max_workers=4)


# ── Sync tool implementations ─────────────────────────────────────────────────


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


async def _render_document(html: str, fmt: str, wait_selector: str | None) -> str:
    from playwright.async_api import async_playwright  # noqa: PLC0415

    ext = "pdf" if fmt == "pdf" else "png"
    name = f"report_{uuid.uuid4().hex[:12]}.{ext}"
    out = REPORTS_DIR / name

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        await page.set_content(html, wait_until="networkidle")
        if wait_selector:
            await page.wait_for_selector(wait_selector, timeout=15_000)
        if fmt == "pdf":
            await page.pdf(
                path=str(out),
                format="A4",
                print_background=True,
                margin={
                    "top": "15mm",
                    "bottom": "15mm",
                    "left": "15mm",
                    "right": "15mm",
                },
            )
        else:
            await page.screenshot(path=str(out), full_page=True)
        await browser.close()

    return name


# ── Tool param models ─────────────────────────────────────────────────────────


class SqlParams(BaseModel):
    query: str


class PythonParams(BaseModel):
    code: str


class ShellParams(BaseModel):
    command: str


# ── kosong CallableTool2 classes ──────────────────────────────────────────────


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
        result = await loop.run_in_executor(_executor, _execute_sql, p.query)
        await self._emit(
            {"type": "sql_result", "result": result, "success": "ERROR" not in result}
        )
        return ToolOk(output=result)


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
        result = await loop.run_in_executor(_executor, _execute_python, p.code)
        success = "ERROR" not in result
        await self._emit(
            {"type": "python_result", "result": result[:500], "success": success}
        )
        return (
            ToolOk(output=result)
            if success
            else ToolError(message=result, brief="Python error")
        )


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
        result = await loop.run_in_executor(_executor, _run_shell, p.command)
        success = "ERROR" not in result
        await self._emit({"type": "shell_result", "result": result, "success": success})
        return (
            ToolOk(output=result)
            if success
            else ToolError(message=result, brief="Shell error")
        )


# ── Toolset factory ───────────────────────────────────────────────────────────


def _make_toolset(level: int, emit) -> SimpleToolset:
    ts = SimpleToolset()
    ts += SqlTool(emit)
    if level == 4:
        ts += PythonTool(emit)
        ts += ShellTool(emit)
    return ts


# ── Provider factory ──────────────────────────────────────────────────────────


def _make_provider(level: int) -> Kimi:
    _reasoning = {1: "low", 2: "low", 3: "medium", 4: "medium"}
    _max_tok = {1: 128000, 2: 128000, 3: 128000, 4: 128000}
    _temp = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}
    _top_p = {1: 0.01, 2: 0.01, 3: 0.01, 4: 0.01}

    return Kimi(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
    ).with_generation_kwargs(
        max_tokens=_max_tok[level],
        temperature=_temp[level],
        top_p=_top_p[level],
        reasoning_effort=_reasoning[level],
    )


# ── DB schemas ────────────────────────────────────────────────────────────────

_SCHEMA_L1 = """
Customers       (CustomerID[text], CompanyName, ContactName, ContactTitle,
                 Address, City, Region, PostalCode, Country, Phone, Fax)
Employees       (EmployeeID, LastName, FirstName, Title, BirthDate, HireDate,
                 City, Country, ReportsTo)
Orders          (OrderID, CustomerID, EmployeeID, OrderDate, RequiredDate,
                 ShippedDate, ShipVia, Freight, ShipName, ShipCity,
                 ShipRegion, ShipCountry)
"Order Details" (OrderID, ProductID, UnitPrice, Quantity, Discount)
Products        (ProductID, ProductName, SupplierID, CategoryID,
                 QuantityPerUnit, UnitPrice, UnitsInStock, UnitsOnOrder,
                 ReorderLevel, Discontinued)
Categories      (CategoryID, CategoryName, Description)
Suppliers       (SupplierID, CompanyName, ContactName, ContactTitle, City, Country, Phone)
Shippers        (ShipperID, CompanyName, Phone)

Revenue formula: SUM(od.UnitPrice * od.Quantity * (1 - od.Discount))
IMPORTANT: Always quote "Order Details" (table name has a space).
Date format: 'YYYY-MM-DD HH:MM:SS'. Use strftime('%Y', OrderDate) to extract year.
"""

_SCHEMA_L2 = """
Customers       (CustomerID[text], CompanyName, ContactName, Country)
Employees       (EmployeeID, FirstName, LastName, Title)
Orders          (OrderID, CustomerID, EmployeeID, OrderDate, ShipCountry)
"Order Details" (OrderID, ProductID, UnitPrice, Quantity, Discount)
Products        (ProductID, ProductName, SupplierID, CategoryID, UnitPrice,
                 UnitsInStock, ReorderLevel, Discontinued)
Categories      (CategoryID, CategoryName)
Suppliers       (SupplierID, CompanyName, Country)

Revenue = SUM(od.UnitPrice * od.Quantity * (1 - od.Discount))
Quote "Order Details" always. Date: strftime('%Y-%m', OrderDate)
"""

_SCHEMA_L3 = """
Customers       (CustomerID[text], CompanyName, ContactName, Country)
Employees       (EmployeeID, FirstName, LastName, Title, ReportsTo)
Orders          (OrderID, CustomerID, EmployeeID, OrderDate, ShipCountry, Freight)
"Order Details" (OrderID, ProductID, UnitPrice, Quantity, Discount)
Products        (ProductID, ProductName, CategoryID, UnitPrice,
                 UnitsInStock, ReorderLevel, Discontinued)
Categories      (CategoryID, CategoryName)
Suppliers       (SupplierID, CompanyName, Country)

Revenue = SUM(od.UnitPrice * od.Quantity * (1 - od.Discount))
Quote "Order Details" always. Date: strftime('%Y', OrderDate)
"""

_SCHEMA_L4 = """
Products   (ProductID, ProductName, SupplierID, CategoryID, UnitPrice,
            UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued)
Suppliers  (SupplierID, CompanyName, ContactName, Phone, Country)
Categories (CategoryID, CategoryName)

Restock condition: UnitsInStock <= ReorderLevel AND Discontinued = '0'
"""


# ── System prompts ────────────────────────────────────────────────────────────

_PROMPTS: dict[int, str] = {
    1: f"""You are Alex, a business analyst for Northwind Traders.
You have the execute_sql tool.

Database schema:
{_SCHEMA_L1}

- Always call execute_sql before answering.
- Write clean SQLite SQL. Quote "Order Details" always.
- Give a clear plain-English answer after getting results.
- If a query errors, fix and retry.""",
    2: f"""You are Alex, a data analyst for Northwind Traders.
You have execute_sql.

Database schema:
{_SCHEMA_L2}

Chart workflow:
  Step 1: execute_sql — fetch the aggregated data needed for the chart.
  Step 2: In your final answer, embed a Chart.js chart using this exact pattern:

<chart>
const config = {{
  type: 'bar',  // or 'line', 'pie', 'doughnut', etc.
  data: {{
    labels: [...],
    datasets: [{{ label: '...', data: [...], backgroundColor: [...] }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'top' }}, title: {{ display: true, text: '...' }} }}
  }}
}};
</chart>

Use dark-friendly colours: rgba(59,130,246,0.85) blue, rgba(16,185,129,0.85) green,
rgba(245,158,11,0.85) amber, rgba(239,68,68,0.85) red, rgba(168,85,247,0.85) purple.
After the chart block, write a short markdown explanation of what it shows.""",
    3: f"""You are Alex, a senior analyst at Northwind Traders.
You have execute_sql.

Database schema:
{_SCHEMA_L3}

When the user asks for a report, investigation, or analysis with charts:
  Step 1: execute_sql — overall trend (revenue by year).
  Step 2: execute_sql — drill down by category AND by employee.
  Step 3: execute_sql — root cause / supporting data.
  Step 4: Write your full HTML report body between <report> and </report> tags.
          Tailwind CSS and Chart.js are pre-loaded — BODY content only,
          no <html>, <head>, or <body> tags. Include KPI cards, charts (<canvas>), tables.
          Charts: new Chart(document.getElementById('chartN'), {{options:{{animation:false}}}}).
  Step 5: After </report>, write a concise markdown summary of 2-3 key findings.
          The PDF download will appear automatically above your summary.

For simple data questions that don't need a report, just answer directly.
Self-correct on SQL ERROR.""",
    4: f"""You are Alex, a senior analyst at Northwind Traders.
You have execute_sql, execute_python, and run_shell.

Database schema:
{_SCHEMA_L4}

PO files pre-seeded at purchase_orders/ inside workspace/.
Filename format: <SupplierName>__PO<ProductID>_<ProductName>.txt

When the user asks to organise PO files or generate a procurement report:
  Step 1: execute_sql — find all products needing restock with supplier names.
  Step 2: run_shell   — ls purchase_orders/ to confirm files exist.
  Step 3: execute_python — shutil.move() each PO file into per-supplier subfolder:
          ws = Path(WORKSPACE_DIR); po_dir = ws / 'purchase_orders'
          Split filename.split('__')[0] → supplier folder.
          (ws / supplier_name).mkdir(exist_ok=True)
  Step 4: run_shell   — zip each supplier folder: zip -r <Name>.zip <Name>/
  Step 5: run_shell   — ls to show final structure.
  Step 6: Write your HTML procurement report body between <report> and </report> tags.
          Tailwind CSS and Chart.js are pre-loaded — BODY content only, no outer HTML tags.
  Step 7: After </report>, write a concise summary: what was done, how many products/suppliers.

Shell: paths relative to workspace/. No '..'. Allowed: {sorted(ALLOWED_SHELL)}""",
}

_MAX_ITER = {1: 8, 2: 10, 3: 20, 4: 40}


# ── Agent loop ────────────────────────────────────────────────────────────────


def _text_of(message: Message) -> str:
    return "\n".join(p.text for p in message.content if isinstance(p, TextPart)).strip()


_REPORT_TAG_RE = re.compile(r"<report>([\s\S]*?)</report>", re.IGNORECASE)


async def _extract_and_render_reports(text: str, emit) -> str:
    """Find every <report>…</report> block, wrap in Jinja2 template, render to PDF,
    emit report_saved events, and return the text with the raw blocks stripped out."""
    matches = list(_REPORT_TAG_RE.finditer(text))
    if not matches:
        return text

    for match in matches:
        body_html = match.group(1).strip()
        await emit({"type": "report_call", "title": "Generating PDF report…"})
        try:
            full_html = _report_tmpl.render(content=body_html)
            wait_sel  = "canvas" if "<canvas" in body_html else None
            filename  = await _render_document(full_html, "pdf", wait_sel)
            url = f"/api/reports/{filename}"
            await emit({"type": "report_saved", "filename": filename, "url": url})
        except Exception as exc:
            await emit({"type": "error", "message": f"PDF render failed: {exc}"})

    return _REPORT_TAG_RE.sub("", text).strip()


async def _agent_loop(
    provider: Kimi,
    system_prompt: str,
    toolset: SimpleToolset,
    question: str,
    max_iter: int,
    emit,
) -> str | None:
    history = [Message(role="user", content=question)]

    for iteration in range(max_iter):
        result = await kosong.step(
            chat_provider=provider,
            system_prompt=system_prompt,
            toolset=toolset,
            history=history,
        )
        history.append(result.message)

        if not result.tool_calls:
            text = _text_of(result.message)
            await emit({"type": "step", "iteration": iteration + 1,
                        "tools_called": [], "has_text": bool(text)})
            if text:
                text = await _extract_and_render_reports(text, emit)
                if text:
                    await emit({"type": "answer", "content": text})
                return text or None
            # Empty response → nudge agent to continue
            history.append(
                Message(role="user", content="Please continue with the next step.")
            )
            continue

        # Await tool execution (tools emit events inside __call__)
        tool_results = await result.tool_results()

        called = {tc.function.name for tc in result.tool_calls}
        await emit({"type": "step", "iteration": iteration + 1, "tools_called": sorted(called)})

        for tr in tool_results:
            rv = tr.return_value
            out = (
                rv.output
                if isinstance(rv.output, str)
                else "\n".join(str(p) for p in rv.output)
            )
            history.append(
                Message(role="tool", content=out, tool_call_id=tr.tool_call_id)
            )

    await emit(
        {
            "type": "error",
            "message": f"Agent reached max iterations ({max_iter}) without completing.",
        }
    )
    return None

# ── SSE stream ────────────────────────────────────────────────────────────────


async def stream_agent(req: RunRequest) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def agent():
        try:
            toolset = _make_toolset(req.level, emit)
            provider = _make_provider(req.level)
            await _agent_loop(
                provider,
                _PROMPTS[req.level],
                toolset,
                req.question,
                _MAX_ITER[req.level],
                emit,
            )
        except Exception as exc:
            await emit({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(agent())

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=120.0)
        except asyncio.TimeoutError:
            yield 'data: {"type": "heartbeat"}\n\n'
            continue
        if event is None:
            break
        yield f"data: {json.dumps(event)}\n\n"

    yield 'data: {"type": "done"}\n\n'
    await task
