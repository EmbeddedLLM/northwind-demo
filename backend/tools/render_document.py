import uuid

try:
    from ..settings import REPORTS_DIR
except ImportError:
    from backend.settings import REPORTS_DIR


async def render_document(html: str, fmt: str, wait_selector: str | None) -> str:
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
