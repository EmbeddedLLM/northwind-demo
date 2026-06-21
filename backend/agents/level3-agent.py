"""Level 3 demo agent: SQL analyst that writes full reports.

Capability shown: the agent still only has database access, but the prompt
guides a multi-step investigation and HTML report generation.
Enabled tools: execute_sql.
"""

import sys
from pathlib import Path

from kosong.tooling.simple import SimpleToolset

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.tools.execute_sql import SqlTool

LEVEL = 3
MAX_ITER = 20
MAX_TOKENS = 128000
TEMPERATURE = 1.0
TOP_P = 0.95
REASONING_EFFORT = "medium"
ENABLED_TOOLS = ("execute_sql",)

SCHEMA = """
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

SYSTEM_PROMPT = f"""You are Alex, a senior analyst at Northwind Traders.
You have execute_sql.

Database schema:
{SCHEMA}

When the user asks for a report, investigation, or analysis with charts:
  Step 1: execute_sql - overall trend (revenue by year).
  Step 2: execute_sql - drill down by category AND by employee.
  Step 3: execute_sql - root cause / supporting data.
  Step 4: Write your full HTML report body between <report> and </report> tags.
          Tailwind CSS and Chart.js are pre-loaded - BODY content only,
          no <html>, <head>, or <body> tags. Include KPI cards, charts (<canvas>), tables.
          Charts: new Chart(document.getElementById('chartN'), {{options:{{animation:false}}}}).
  Step 5: After </report>, write a concise markdown summary of 2-3 key findings.
          The PDF download will appear automatically above your summary.

For simple data questions that don't need a report, just answer directly.
Self-correct on SQL ERROR."""


def make_toolset(emit) -> SimpleToolset:
    ts = SimpleToolset()
    ts += SqlTool(emit)
    return ts
