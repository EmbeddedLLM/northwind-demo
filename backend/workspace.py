import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from .settings import DB_PATH, REPORTS_DIR, WORKSPACE_DIR
except ImportError:
    from backend.settings import DB_PATH, REPORTS_DIR, WORKSPACE_DIR


def workspace_tree() -> str:
    if not WORKSPACE_DIR.exists():
        return "(workspace/ not found — run Setup first)"
    lines = ["workspace/"]
    for item in sorted(WORKSPACE_DIR.rglob("*")):
        rel = item.relative_to(WORKSPACE_DIR)
        if len(rel.parts) > 4:
            continue
        depth = len(rel.parts) - 1
        indent = "  " * depth
        icon = "D " if item.is_dir() else "F "
        size = f"  [{item.stat().st_size // 1024} KB]" if item.is_file() else ""
        lines.append(f"{indent}{icon}{item.name}{size}")
    return "\n".join(lines) if len(lines) > 1 else "(workspace/ is empty)"


def resolve_workspace_file(file_path: str) -> Path:
    target = (WORKSPACE_DIR / file_path).resolve()
    if not str(target).startswith(str(WORKSPACE_DIR.resolve())):
        raise PermissionError("Access denied")
    if not target.exists():
        raise FileNotFoundError("File not found")
    return target


def resolve_report_file(filename: str) -> Path:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError("Invalid filename")
    path = REPORTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError("Report not found")
    return path


def workspace_needs_setup() -> bool:
    po_dir = WORKSPACE_DIR / "purchase_orders"
    return not po_dir.exists() or not any(po_dir.glob("*.txt"))


def ensure_workspace_initialized() -> str:
    if workspace_needs_setup():
        return setup_workspace()

    count = len(list((WORKSPACE_DIR / "purchase_orders").glob("*.txt")))
    return f"Workspace already has {count} purchase order files."


def setup_workspace() -> str:
    po_dir = WORKSPACE_DIR / "purchase_orders"
    if WORKSPACE_DIR.exists():
        shutil.rmtree(str(WORKSPACE_DIR))
    po_dir.mkdir(parents=True)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT p.ProductID, p.ProductName, p.UnitsInStock, p.UnitsOnOrder,
               p.ReorderLevel, p.UnitPrice, p.QuantityPerUnit,
               s.CompanyName, s.ContactName, s.Phone, s.Country, c.CategoryName
        FROM Products p
        JOIN Suppliers s ON p.SupplierID = s.SupplierID
        JOIN Categories c ON p.CategoryID = c.CategoryID
        WHERE p.UnitsInStock <= p.ReorderLevel AND p.Discontinued = '0'
        ORDER BY s.CompanyName, p.ProductName
    """).fetchall()
    conn.close()

    def _clean(t: str) -> str:
        return "".join(c if c.isalnum() or c == "_" else "_" for c in str(t)).strip("_")

    for (
        pid,
        pname,
        in_stock,
        on_order,
        reorder_level,
        unit_price,
        qty_per_unit,
        supplier,
        contact,
        phone,
        country,
        category,
    ) in rows:
        qty = max(reorder_level * 2 - in_stock, 10)
        cost = round(qty * unit_price, 2)
        lines = [
            "=" * 52,
            "   NORTHWIND TRADERS — PURCHASE ORDER REQUEST",
            "=" * 52,
            f"   PO Date      : {datetime.now().strftime('%Y-%m-%d')}",
            f"   Product ID   : {pid}",
            f"   Product      : {pname}",
            f"   Category     : {category}",
            f"   Pack Size    : {qty_per_unit}",
            "-" * 52,
            "   STOCK STATUS",
            f"   Units in Stock  : {in_stock}",
            f"   Units on Order  : {on_order}",
            f"   Reorder Level   : {reorder_level}",
            "   *** BELOW REORDER LEVEL — ACTION REQUIRED ***",
            "-" * 52,
            "   SUPPLIER",
            f"   Company  : {supplier}",
            f"   Contact  : {contact}",
            f"   Phone    : {phone}",
            f"   Country  : {country}",
            "-" * 52,
            "   ORDER DETAILS",
            f"   Unit Price     : ${unit_price:.2f}",
            f"   Qty to Order   : {qty} units",
            f"   Estimated Cost : ${cost:.2f}",
            "=" * 52,
            "   Status : PENDING APPROVAL",
            "=" * 52,
        ]
        fname = (
            po_dir / f"{_clean(supplier)[:30]}__PO{pid:03d}_{_clean(pname)[:30]}.txt"
        )
        fname.write_text("\n".join(lines), encoding="utf-8")

    count = len(list(po_dir.glob("*.txt")))
    return f"Created {count} purchase order files."
