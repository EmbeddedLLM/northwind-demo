import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

try:
    from .render_document import render_document
except ImportError:
    from backend.tools.render_document import render_document

_jinja_env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"),
    autoescape=False,
)
_report_tmpl = _jinja_env.get_template("report.html.j2")
_REPORT_TAG_RE = re.compile(r"<report>([\s\S]*?)</report>", re.IGNORECASE)


async def extract_and_render_reports(text: str, emit) -> str:
    """Render <report> blocks to PDF and remove raw report HTML from the answer."""
    matches = list(_REPORT_TAG_RE.finditer(text))
    if not matches:
        return text

    for match in matches:
        body_html = match.group(1).strip()
        await emit({"type": "report_call", "title": "Generating PDF report..."})
        try:
            full_html = _report_tmpl.render(content=body_html)
            wait_selector = "canvas" if "<canvas" in body_html else None
            filename = await render_document(full_html, "pdf", wait_selector)
            url = f"/api/reports/{filename}"
            await emit({"type": "report_saved", "filename": filename, "url": url})
        except Exception as exc:
            await emit({"type": "error", "message": f"PDF render failed: {exc}"})

    return _REPORT_TAG_RE.sub("", text).strip()
