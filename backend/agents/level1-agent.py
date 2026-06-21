"""Level 1 demo agent: SQL analyst.

Capability shown: the agent can inspect the Northwind database with one tool.
Enabled tools: execute_sql.
"""

import sys
from pathlib import Path

from kosong.tooling.simple import SimpleToolset

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.tools.execute_sql import SqlTool

LEVEL = 1
MAX_ITER = 8
MAX_TOKENS = 128000
TEMPERATURE = 1.0
TOP_P = 0.95
REASONING_EFFORT = "low"
ENABLED_TOOLS = ("execute_sql",)

SCHEMA = """
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

SYSTEM_PROMPT = f"""You are Alex, a business analyst for Northwind Traders.
You have the execute_sql tool.

Database schema:
{SCHEMA}

- Always call execute_sql before answering.
- Write clean SQLite SQL. Quote "Order Details" always.
- Give a clear plain-English answer after getting results.
- If a query errors, fix and retry."""


def make_toolset(emit) -> SimpleToolset:
    ts = SimpleToolset()
    ts += SqlTool(emit)
    return ts
