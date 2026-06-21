"""Level 2 demo agent: SQL analyst with chart output.

Capability shown: same database tool as Level 1, but the prompt teaches the
agent to turn query results into a Chart.js block for the web UI.
Enabled tools: execute_sql.
"""

import sys
from pathlib import Path

from kosong.tooling.simple import SimpleToolset

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.tools.execute_sql import SqlTool

LEVEL = 2
MAX_ITER = 10
MAX_TOKENS = 128000
TEMPERATURE = 1.0
TOP_P = 0.95
REASONING_EFFORT = "low"
ENABLED_TOOLS = ("execute_sql",)

SCHEMA = """
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

SYSTEM_PROMPT = f"""You are Alex, a data analyst for Northwind Traders.
You have execute_sql.

Database schema:
{SCHEMA}

Chart workflow:
  Step 1: execute_sql - fetch the aggregated data needed for the chart.
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
After the chart block, write a short markdown explanation of what it shows."""


def make_toolset(emit) -> SimpleToolset:
    ts = SimpleToolset()
    ts += SqlTool(emit)
    return ts
