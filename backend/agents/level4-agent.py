"""Level 4 demo agent: database, Python, and filesystem tools.

Capability shown: adding Python execution and shell access lets the agent
inspect data, organize files, create ZIPs, and produce a procurement report.
Enabled tools: execute_sql, execute_python, run_shell.
"""

import sys
from pathlib import Path

from kosong.tooling.simple import SimpleToolset

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.settings import ALLOWED_SHELL
from backend.tools.execute_python import PythonTool
from backend.tools.execute_sql import SqlTool
from backend.tools.run_shell import ShellTool

LEVEL = 4
MAX_ITER = 40
MAX_TOKENS = 128000
TEMPERATURE = 1.0
TOP_P = 0.95
REASONING_EFFORT = "medium"
ENABLED_TOOLS = ("execute_sql", "execute_python", "run_shell")

SCHEMA = """
Products   (ProductID, ProductName, SupplierID, CategoryID, UnitPrice,
            UnitsInStock, UnitsOnOrder, ReorderLevel, Discontinued)
Suppliers  (SupplierID, CompanyName, ContactName, Phone, Country)
Categories (CategoryID, CategoryName)

Restock condition: UnitsInStock <= ReorderLevel AND Discontinued = '0'
"""

SYSTEM_PROMPT = f"""You are Alex, a senior analyst at Northwind Traders.
You have execute_sql, execute_python, and run_shell.

Database schema:
{SCHEMA}

PO files pre-seeded at purchase_orders/ inside workspace/.
Filename format: <SupplierName>__PO<ProductID>_<ProductName>.txt

When the user asks to organise PO files or generate a procurement report:
  Step 1: execute_sql - find all products needing restock with supplier names.
  Step 2: run_shell   - ls purchase_orders/ to confirm files exist.
  Step 3: execute_python - shutil.move() each PO file into per-supplier subfolder:
          ws = Path(WORKSPACE_DIR); po_dir = ws / 'purchase_orders'
          Split filename.split('__')[0] -> supplier folder.
          (ws / supplier_name).mkdir(exist_ok=True)
  Step 4: run_shell   - zip each supplier folder: zip -r <Name>.zip <Name>/
  Step 5: run_shell   - ls to show final structure.
  Step 6: Write your HTML procurement report body between <report> and </report> tags.
          Tailwind CSS and Chart.js are pre-loaded - BODY content only, no outer HTML tags.
  Step 7: After </report>, write a concise summary: what was done, how many products/suppliers.

Shell: paths relative to workspace/. No '..'. Allowed: {sorted(ALLOWED_SHELL)}"""


def make_toolset(emit) -> SimpleToolset:
    ts = SimpleToolset()
    ts += SqlTool(emit)
    ts += PythonTool(emit)
    ts += ShellTool(emit)
    return ts
