# Northwind Demo — Agentic AI in 4 Levels

A progressive demo showing how an AI agent (Alex) grows in capability across 4 levels,
using the **Northwind Traders** dataset — a specialty food import/export company.

This repo has two apps:

- `backend/` = FastAPI agent server
- `alex-demo/` = Svelte frontend

## Quick Start

1. Install dependencies from the repo root:

```bash
uv sync --all-packages
```

2. Download the demo database if you do not already have it:

```bash
wget https://github.com/jpwhite3/northwind-SQLite3/raw/main/dist/northwind.db
```

3. Create your backend environment file:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set `BASE_URL`, `API_KEY`, and `MODEL` for your model provider.

4. Start the backend API in one terminal:

```bash
uv run --package backend python backend/main.py
```

5. Start the frontend in a second terminal:

```bash
cd alex-demo
npm install
npm run dev
```

6. Open the Svelte app at the URL printed by Vite, usually `http://localhost:5173`.

The frontend is already configured to proxy `/api/*` requests to the backend on `http://localhost:8000`.

If you only want the API, run steps 1 to 4 and skip the frontend.

---

## Optional: Telegram Bot

Alex also has a Telegram bot for a lighter, chat-first experience.
It is best for two things:

- chart generation
- simple PDF report generation

The bot shares the same backend agent, but it delivers charts as photos and
PDF reports as uploaded documents.

Run it from the repo root after setting `TELEGRAM_TOKEN` in `backend/.env`:

```bash
uv run --package backend python backend/telegram_bot.py
```

In Telegram, use:

- `/start` to see the current mode
- `/help` to get a demo prompt
- `/level2` for chart generation
- `/level3` for PDF report generation
- `/setup` to reset the Level 4 workspace if you want to use that flow

---

## Using The Demo

Open the Svelte app in your browser and use the level tabs across the top:

- Level 1 asks Alex to turn English questions into SQL
- Level 2 adds charts and file output
- Level 3 generates multi-step reports
- Level 4 uses the workspace filesystem and purchase-order files

Press `Ctrl+Enter` or `Cmd+Enter` in the prompt box to run a question.
The Level 4 setup button calls `POST /api/setup`, which wipes `workspace/`
and regenerates the purchase-order files from `northwind.db`.

---

## Dataset

**Northwind Traders** sells 77 products across 8 categories to 93 customers in 21 countries.

| Table | Description |
|---|---|
| Customers | 93 corporate buyers worldwide |
| Orders + Order Details | 830 orders, ~2,155 line items |
| Products | 77 products across 8 categories |
| Suppliers | 29 suppliers from 16 countries |
| Employees | 9 sales staff |
| Categories | Beverages, Condiments, Seafood, etc. |

See the full schema: [`northwind_er.md`](northwind_er.md) or [`northwind_er.dbml`](northwind_er.dbml)

---

## Level 1 — Natural Language to SQL

Alex answers plain-English business questions by generating and running SQL.
No SQL knowledge needed from the user.

**Demo prompts:**
```
Who are our top 5 customers by total revenue?
Which product category generates the most sales?
Which employee has closed the most orders?
How many orders were shipped to Germany?
What are the top 10 best-selling products?
Which suppliers provide the most products?
```

---

## Level 2 — Visualization & File Handling

Alex picks between SQL (fetch data) and Python (chart it).
Charts are rendered by the backend and saved to `backend/reports/chart_*.png`.

**Demo prompts:**
```
Show monthly revenue trend as a line chart
Create a bar chart of revenue by product category
Plot a pie chart of orders by country (top 10)
Chart the top 10 best-selling products by revenue
Compare employee performance with a bar chart
```

The backend serves them back through `/api/reports/...`.

---

## Level 3 — Workflow Orchestrator

Alex investigates a business anomaly through multi-step reasoning,
creates charts, and compiles everything into a PDF report.

**Demo prompt:**
```
Germany is our second-largest market. Investigate whether our revenue there
is growing or declining, which product categories are driving the change,
and which employees handle German accounts. Generate a report with charts.
```

**Other prompts:**
```
Seafood sales seem low. Investigate trends and compare against other categories, then generate a report.
Which employee is underperforming? Investigate and report.
```

Output: `backend/reports/report_<timestamp>_<title>.pdf` + chart PNGs.
In this repo, the rendered report files live in `backend/reports/` and are
served through `/api/reports/<filename>`.

---

## Level 4 — Environmental Agent (OS-Level File Operations)

Alex operates the filesystem: creates supplier folders, moves purchase order files,
zips each folder, and generates a procurement report.
**Folders appear live in the VS Code sidebar** — the demo "lightbulb moment".

### Step 1 — Seed the workspace

Use the Level 4 setup button in the web app before the filesystem demo.
That button calls `POST /api/setup`, which runs
[`backend/workspace.py::setup_workspace()`](backend/workspace.py) and does the
following:

- deletes the existing `workspace/` directory
- queries `northwind.db` for products at or below reorder level
- creates one purchase-order `.txt` file per restock item
- writes them to `workspace/purchase_orders/`

The filenames are generated from the supplier and product names, for example:
```
workspace/
  purchase_orders/
    Exotic_Liquids__PO002_Chang.txt
    Exotic_Liquids__PO003_Aniseed_Syrup.txt
    Formaggi_Fortini_s_r_l__PO031_Gorgonzola_Telino.txt
    ...
```

### Step 2 — Run the agent

**Demo prompt:**
```
Our procurement team needs to send restock orders today. Find all products
below reorder level, organise their PO files by supplier into folders,
zip each supplier folder, and generate a procurement summary report.
```

During the Level 4 run, the agent can:

- move purchase-order files into supplier folders with `execute_python`
- zip each folder with `run_shell`
- generate a PDF report with the `<report>...</report>` workflow

### What the audience sees in VS Code:

```
workspace/
  purchase_orders/          ← pre-seeded (18 PO files)
  Exotic_Liquids/
    Exotic_Liquids__PO002_Chang.txt
    Exotic_Liquids__PO003_Aniseed_Syrup.txt
  Exotic_Liquids.zip
  Formaggi_Fortini_s_r_l/
    ...
  Formaggi_Fortini_s_r_l.zip
  ...                       ← 15 supplier folders + 15 zips
  report_<timestamp>_Procurement_Summary_Report.pdf
```

---

## Tools per Level

| Tool | L1 | L2 | L3 | L4 |
|---|:---:|:---:|:---:|:---:|
| `execute_sql` — query Northwind DB | ✓ | ✓ | ✓ | ✓ |
| `execute_python` — pandas, matplotlib, shutil | | ✓ | ✓ | ✓ |
| `generate_report` — produce PDF report | | | ✓ | ✓ |
| `run_shell` — mkdir, mv, zip inside workspace/ | | | | ✓ |

---

## Re-running the Demo

Use the Level 4 setup button again if you want to reset the workspace before
running the filesystem demo a second time.

---

## Files

```
northwind_demo/
  backend/                  — FastAPI agent server
  alex-demo/                — Svelte frontend
  northwind.db              — SQLite database
  workspace/                — All agent outputs saved here
```
