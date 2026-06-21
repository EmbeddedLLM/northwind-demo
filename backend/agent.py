"""Shared runtime for Alex, the Northwind AI Analyst.

The four demo agents live in backend/agents/levelN-agent.py. This module owns
the LLM provider, SSE streaming, and the common agent loop. Tool and rendering
helpers live in backend.tools; HTTP concerns belong in main.py.
"""

import asyncio
import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import AsyncGenerator

import kosong
from kosong.chat_provider.kimi import Kimi
from kosong.message import Message, TextPart
from kosong.tooling.simple import SimpleToolset

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from .models import ChatHistoryMessage, RunRequest
    from .settings import (
        API_KEY,
        BASE_URL,
        MODEL,
    )
    from .tools.extract_and_render_reports import extract_and_render_reports
except ImportError:
    from backend.models import ChatHistoryMessage, RunRequest
    from backend.settings import (
        API_KEY,
        BASE_URL,
        MODEL,
    )
    from backend.tools.extract_and_render_reports import extract_and_render_reports


# ── Demo agent config loader ──────────────────────────────────────────────────


@lru_cache(maxsize=4)
def _load_agent_config(level: int) -> ModuleType:
    agent_path = Path(__file__).parent / "agents" / f"level{level}-agent.py"
    if not agent_path.exists():
        raise ValueError(f"level must be 1-4, got {level}")

    module_name = f"backend.agents.level{level}_agent"
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load agent config from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _agent_system_prompt(agent_config: ModuleType) -> str:
    return str(agent_config.SYSTEM_PROMPT)


def _agent_max_iter(agent_config: ModuleType) -> int:
    return int(agent_config.MAX_ITER)


def _agent_toolset(agent_config: ModuleType, emit) -> SimpleToolset:
    make_toolset = agent_config.make_toolset
    return make_toolset(emit)


# ── Provider factory ──────────────────────────────────────────────────────────


def _make_provider(agent_config: ModuleType) -> Kimi:
    max_tokens = int(getattr(agent_config, "MAX_TOKENS", 128000))
    temperature = float(getattr(agent_config, "TEMPERATURE", 1.0))
    top_p = float(getattr(agent_config, "TOP_P", 0.95))
    reasoning_effort = str(agent_config.REASONING_EFFORT)

    return Kimi(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
    ).with_generation_kwargs(
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        reasoning_effort=reasoning_effort,
    )


# ── Agent loop ────────────────────────────────────────────────────────────────


def _text_of(message: Message) -> str:
    return "\n".join(p.text for p in message.content if isinstance(p, TextPart)).strip()


def _message_from_history(item: ChatHistoryMessage) -> Message:
    return Message(role=item.role, content=item.content)


async def _agent_loop(
    provider: Kimi,
    system_prompt: str,
    toolset: SimpleToolset,
    question: str,
    chat_history: list[ChatHistoryMessage],
    max_iter: int,
    emit,
) -> str | None:
    history = [_message_from_history(item) for item in chat_history]
    history.append(Message(role="user", content=question))

    for iteration in range(max_iter):
        result = await kosong.step(
            chat_provider=provider,
            system_prompt=system_prompt,
            toolset=toolset,
            history=history,
        )
        history.append(result.message)

        if not result.tool_calls:
            text = _text_of(result.message)
            await emit({"type": "step", "iteration": iteration + 1,
                        "tools_called": [], "has_text": bool(text)})
            if text:
                text = await extract_and_render_reports(text, emit)
                if text:
                    await emit({"type": "answer", "content": text})
                return text or None
            # Empty response → nudge agent to continue
            history.append(
                Message(role="user", content="Please continue with the next step.")
            )
            continue

        # Await tool execution (tools emit events inside __call__)
        tool_results = await result.tool_results()

        called = {tc.function.name for tc in result.tool_calls}
        await emit({"type": "step", "iteration": iteration + 1, "tools_called": sorted(called)})

        for tr in tool_results:
            rv = tr.return_value
            out = (
                rv.output
                if isinstance(rv.output, str)
                else "\n".join(str(p) for p in rv.output)
            )
            history.append(
                Message(role="tool", content=out, tool_call_id=tr.tool_call_id)
            )

    await emit(
        {
            "type": "error",
            "message": f"Agent reached max iterations ({max_iter}) without completing.",
        }
    )
    return None

# ── SSE stream ────────────────────────────────────────────────────────────────


async def stream_agent(req: RunRequest) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def agent():
        try:
            agent_config = _load_agent_config(req.level)
            toolset = _agent_toolset(agent_config, emit)
            provider = _make_provider(agent_config)
            await _agent_loop(
                provider,
                _agent_system_prompt(agent_config),
                toolset,
                req.question,
                req.history,
                _agent_max_iter(agent_config),
                emit,
            )
        except Exception as exc:
            await emit({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(agent())

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=120.0)
        except asyncio.TimeoutError:
            yield 'data: {"type": "heartbeat"}\n\n'
            continue
        if event is None:
            break
        yield f"data: {json.dumps(event)}\n\n"

    yield 'data: {"type": "done"}\n\n'
    await task
