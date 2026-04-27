import uuid
from pathlib import Path
import sys

from jinja2 import Environment, FileSystemLoader

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from .settings import REPORTS_DIR
except ImportError:
    from backend.settings import REPORTS_DIR

_jinja_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
)
_chart_tmpl = _jinja_env.get_template("chart.html.j2")


async def render_chart_png(chart_code: str) -> Path:
    from playwright.async_api import async_playwright  # noqa: PLC0415

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"chart_{uuid.uuid4().hex[:12]}.png"
    html = _chart_tmpl.render(chart_code=chart_code)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(
                viewport={"width": 1024, "height": 680},
                device_scale_factor=2,
            )
            await page.set_content(html, wait_until="networkidle")
            await page.wait_for_function("window.__chartReady === true", timeout=15_000)
            chart_error = await page.evaluate("window.__chartError || null")
            if chart_error:
                raise RuntimeError(chart_error)
            card = page.locator("#chart-card")
            await card.screenshot(path=str(out))
        finally:
            await browser.close()

    return out
