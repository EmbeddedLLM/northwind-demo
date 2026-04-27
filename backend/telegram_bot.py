"""
Telegram bot - Alex, Northwind AI Analyst
=========================================

This is the phone-friendly adapter for the Svelte/FastAPI demo.

It uses the backend agent loop directly in this Python process. In other words,
Telegram does not call the served HTTP API. Both entrypoints share the same
backend implementation:

  Web UI     -> POST /api/run -> agent.stream_agent(...)
  Telegram   -> polling bot   -> agent.stream_agent(...)

Setup:
  1. In Telegram, open @BotFather -> /newbot -> copy the token.
  2. Add TELEGRAM_TOKEN=<token-from-botfather> to backend/.env
     or export TELEGRAM_TOKEN=<token-from-botfather>
  3. uv run --package backend python backend/telegram_bot.py

Useful commands:
  /start       greeting and current mode
  /help        demo prompts
  /level1      SQL analyst
  /level2      data visualiser
  /level3      report orchestrator
  /level4      computer/filesystem agent
  /setup       reset Level 4 purchase-order workspace
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BACKEND_DIR = Path(__file__).parent
if __package__ in (None, ""):
    sys.path.insert(0, str(BACKEND_DIR.parent))
load_dotenv(BACKEND_DIR / ".env")

try:
    from .agent import stream_agent  # noqa: E402
    from .chart_renderer import render_chart_png  # noqa: E402
    from .models import RunRequest  # noqa: E402
    from .settings import REPORTS_DIR  # noqa: E402
    from .workspace import setup_workspace  # noqa: E402
except ImportError:
    from backend.agent import stream_agent  # noqa: E402
    from backend.chart_renderer import render_chart_png  # noqa: E402
    from backend.models import RunRequest  # noqa: E402
    from backend.settings import REPORTS_DIR  # noqa: E402
    from backend.workspace import setup_workspace  # noqa: E402

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

DEFAULT_LEVEL = int(os.environ.get("TELEGRAM_DEFAULT_LEVEL", "2"))
LEVEL_LABELS = {
    1: "Level 1 - SQL Analyst",
    2: "Level 2 - Data Visualiser",
    3: "Level 3 - Report Orchestrator",
    4: "Level 4 - Computer Agent",
}

DEMO_PROMPTS = {
    1: "Who are our top 5 customers by total revenue?",
    2: "Which product category generates the most sales? Show me a chart.",
    3: (
        "Germany is our second-largest market. Investigate whether revenue there "
        "is growing or declining, which categories are driving the change, and "
        "generate a report."
    ),
    4: (
        "Our procurement team needs to send restock orders today. Find all products "
        "below reorder level, organise their PO files by supplier, zip each supplier "
        "folder, and generate a procurement summary report."
    ),
}

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("alex-telegram")
CHART_BLOCK_RE = re.compile(r"<chart\b[^>]*>([\s\S]*?)</chart\s*>", re.IGNORECASE)
UNCLOSED_CHART_RE = re.compile(r"<chart\b[^>]*>[\s\S]*$", re.IGNORECASE)


@dataclass
class TelegramAgentResult:
    messages: list[str] = field(default_factory=list)
    chart_paths: list[Path] = field(default_factory=list)
    report_paths: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    chart_errors: list[str] = field(default_factory=list)


def _chat_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    context.chat_data.setdefault("level", DEFAULT_LEVEL)
    return context.chat_data


def _mode_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    state = _chat_state(context)
    return LEVEL_LABELS[state["level"]]


def _strip_chart_blocks(text: str) -> str:
    text = CHART_BLOCK_RE.sub("", text)
    return UNCLOSED_CHART_RE.sub("", text)


def _extract_chart_blocks(text: str) -> tuple[str, list[str], list[str]]:
    charts = [match.group(1).strip() for match in CHART_BLOCK_RE.finditer(text)]
    text_without_charts = CHART_BLOCK_RE.sub("", text)
    errors: list[str] = []
    if UNCLOSED_CHART_RE.search(text_without_charts):
        text_without_charts = UNCLOSED_CHART_RE.sub("", text_without_charts)
        errors.append("The model opened a <chart> block but did not close it with </chart>.")
    return text_without_charts.strip(), charts, errors


def _clean_text(text: str) -> str:
    text = _strip_chart_blocks(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalise_link_url(url: str) -> str | None:
    url = html.unescape(url).strip()
    if url.startswith("/"):
        return f"{PUBLIC_BASE_URL}{url}" if PUBLIC_BASE_URL else None
    if url.startswith(("http://", "https://")):
        return url
    return None


def _telegram_html(text: str) -> str:
    code_blocks: list[str] = []
    inline_codes: list[str] = []

    def stash_code_block(match: re.Match[str]) -> str:
        code = match.group(2).strip("\n")
        code_blocks.append(f"<pre>{html.escape(code)}</pre>")
        return f"@@CODE_BLOCK_{len(code_blocks) - 1}@@"

    def stash_inline_code(match: re.Match[str]) -> str:
        code = match.group(1)
        inline_codes.append(f"<code>{html.escape(code)}</code>")
        return f"@@INLINE_CODE_{len(inline_codes) - 1}@@"

    text = re.sub(r"```(\w+)?\n([\s\S]*?)```", stash_code_block, text)
    text = re.sub(r"`([^`\n]+)`", stash_inline_code, text)
    text = html.escape(text)

    def render_link(match: re.Match[str]) -> str:
        label = match.group(1)
        url = _normalise_link_url(match.group(2))
        if not url:
            return label
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", render_link, text)
    text = re.sub(r"(?m)^#{1,6}\s+(.+)$", r"<b>\1</b>", text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_\n]+)__", r"<b>\1</b>", text)
    text = re.sub(r"(?m)^[-*]\s+", "• ", text)

    for i, block in enumerate(code_blocks):
        text = text.replace(f"@@CODE_BLOCK_{i}@@", block)
    for i, code in enumerate(inline_codes):
        text = text.replace(f"@@INLINE_CODE_{i}@@", code)

    return text


def _split_telegram_text(text: str, limit: int = 3400) -> list[str]:
    chunks: list[str] = []
    current = ""
    for part in re.split(r"(\n\n+)", text):
        if len(current) + len(part) <= limit:
            current += part
            continue
        if current.strip():
            chunks.append(current.strip())
        current = part
        while len(current) > limit:
            chunks.append(current[:limit].strip())
            current = current[limit:]
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:limit]]


async def _reply_long(update: Update, text: str) -> None:
    if not update.message:
        return
    text = _clean_text(text) or "(No text response.)"
    for chunk in _split_telegram_text(text):
        try:
            await update.message.reply_text(
                _telegram_html(chunk),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except BadRequest:
            log.exception("Telegram rejected formatted message; sending plain text")
            await update.message.reply_text(chunk)



async def _collect_agent_response(
    level: int,
    question: str,
) -> TelegramAgentResult:
    req = RunRequest(level=level, question=question)
    result = TelegramAgentResult()

    async for line in stream_agent(req):
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload:
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")
        if event_type == "answer":
            text, chart_codes, chart_errors = _extract_chart_blocks(str(event.get("content", "")))
            if text:
                result.messages.append(text)
            result.chart_errors.extend(chart_errors)
            if chart_codes and level != 2:
                result.chart_errors.append(
                    f"<chart> blocks are only supported for Telegram Level 2, not Level {level}."
                )
                continue
            for chart_code in chart_codes:
                try:
                    result.chart_paths.append(await render_chart_png(chart_code))
                except Exception as exc:
                    log.exception("Chart render failed")
                    result.chart_errors.append(f"Chart render failed: {exc}")
        elif event_type == "report_saved":
            filename = str(event.get("filename", ""))
            if filename:
                result.report_paths.append(REPORTS_DIR / filename)
                if PUBLIC_BASE_URL:
                    result.messages.append(f"Report: {PUBLIC_BASE_URL}/api/reports/{filename}")
        elif event_type == "error":
            result.errors.append(str(event.get("message", "Unknown error")))

    return result


def _chart_retry_question(level: int, question: str, chart_errors: list[str]) -> str:
    if level == 2:
        instruction = (
            "Please retry the answer. If you include a chart, output exactly one complete "
            "<chart>...</chart> block containing valid JavaScript that defines "
            "`const config = {...};`. The block must include the closing </chart> tag. "
            "After the chart block, include a brief plain markdown explanation. "
            "Do not include partial chart markup."
        )
    else:
        instruction = (
            f"Please retry the answer for Level {level} without using <chart> blocks. "
            "For Level 3 or Level 4 reports, use the expected <report>...</report> format. "
            "For simple answers, reply in plain markdown."
        )

    return (
        f"{question}\n\n"
        "Your previous answer could not be delivered to Telegram because chart handling failed.\n"
        "Chart error(s):\n"
        + "\n".join(f"- {err}" for err in chart_errors)
        + f"\n\n{instruction}"
    )


async def _run_agent_for_telegram(
    level: int,
    question: str,
) -> TelegramAgentResult:
    result = await _collect_agent_response(level, question)
    if not result.chart_errors:
        return result

    log.info("Retrying agent after chart failure: %s", "; ".join(result.chart_errors))
    retry = await _collect_agent_response(
        level,
        _chart_retry_question(level, question, result.chart_errors),
    )
    if not retry.chart_errors:
        return retry

    retry.errors.extend(f"Chart failed after retry: {err}" for err in retry.chart_errors)
    return retry


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi, I'm Alex, the Northwind agent.\n\n"
        f"Current mode: {_mode_text(context)}\n\n"
        "Ask a business question, or switch levels with /level1, /level2, /level3, or /level4."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _chat_state(context)
    prompt = DEMO_PROMPTS[state["level"]]
    await update.message.reply_text(
        f"Current mode: {_mode_text(context)}\n\n"
        f"Try:\n{prompt}\n\n"
        "Commands: /level1 /level2 /level3 /level4 /setup"
    )


async def cmd_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    level = int(update.message.text.replace("/level", "").split("@", 1)[0])
    context.chat_data["level"] = level
    await update.message.reply_text(
        f"Switched to {LEVEL_LABELS[level]}.\n\nTry:\n{DEMO_PROMPTS[level]}"
    )


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Resetting the Level 4 purchase-order workspace...")
    loop = asyncio.get_running_loop()
    try:
        msg = await loop.run_in_executor(None, setup_workspace)
    except Exception as exc:
        log.exception("Workspace setup failed")
        await update.message.reply_text(f"Setup failed: {exc}")
        return
    await update.message.reply_text(msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    state = _chat_state(context)
    question = update.message.text.strip()
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )
    await update.message.reply_text(f"Thinking with {_mode_text(context)}...")

    try:
        result = await _run_agent_for_telegram(
            state["level"],
            question,
        )
    except Exception as exc:
        log.exception("Agent run failed")
        await update.message.reply_text(f"Sorry, Alex hit an error:\n{exc}")
        return

    for text in result.messages:
        await _reply_long(update, text)

    for path in result.chart_paths:
        if path.exists():
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_PHOTO,
            )
            with path.open("rb") as chart:
                await update.message.reply_photo(
                    photo=chart,
                    caption="Chart",
                )

    for path in result.report_paths:
        if path.exists():
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_DOCUMENT,
            )
            with path.open("rb") as report:
                await update.message.reply_document(
                    document=report,
                    filename=path.name,
                    caption="PDF report",
                )

    if result.errors:
        await _reply_long(update, "Errors:\n" + "\n".join(f"- {err}" for err in result.errors))
    if not result.messages and not result.chart_paths and not result.report_paths and not result.errors:
        await update.message.reply_text("The agent finished, but did not produce a final message.")


def main() -> None:
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(
            "ERROR: Set TELEGRAM_TOKEN first.\n"
            "Run: export TELEGRAM_TOKEN=<token-from-botfather>"
        )
        raise SystemExit(1)
    if DEFAULT_LEVEL not in LEVEL_LABELS:
        print("ERROR: TELEGRAM_DEFAULT_LEVEL must be 1, 2, 3, or 4.")
        raise SystemExit(1)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("setup", cmd_setup))
    for level in LEVEL_LABELS:
        app.add_handler(CommandHandler(f"level{level}", cmd_level))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Alex Telegram bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
