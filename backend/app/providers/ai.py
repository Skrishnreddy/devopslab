"""AI provider interface for the AI Teacher (docs/ai-teacher.md).

Ollama is the default runtime; any local runtime (or, opt-in, an external API)
implements the same interface. Rules for every implementation:
- it never executes commands; it only returns text and command *proposals*;
- input is redacted before it reaches a model;
- external providers receive context only with per-request consent.

Phase 1 implements health() so the dashboard can show whether Ollama is
reachable. Chat, model listing and pulls arrive in Phase 9.
"""
import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from typing import Literal, Protocol

from pydantic import BaseModel

from ..core.config import settings
from .health import ComponentHealth

ModelRole = Literal["coder", "teacher", "fallback"]


class ModelInfo(BaseModel):
    name: str
    size_bytes: int
    family: str | None = None
    quantization: str | None = None


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AIProvider(Protocol):
    name: str
    local: bool

    async def health(self) -> ComponentHealth: ...
    async def list_models(self) -> list[ModelInfo]: ...
    def chat(self, messages: list[ChatMessage], model: str) -> AsyncIterator[str]: ...


def _get_json(url: str, timeout: float) -> dict:
    # Only ever called with settings.ollama_url, which config restricts to loopback.
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
        return json.loads(r.read().decode())


class OllamaProvider:
    name = "ollama"
    local = True

    async def health(self) -> ComponentHealth:
        base = settings.ollama_url
        try:
            version, tags = await asyncio.gather(
                asyncio.to_thread(_get_json, f"{base}/api/version", 2.0),
                asyncio.to_thread(_get_json, f"{base}/api/tags", 2.0),
            )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            return ComponentHealth(
                id="ollama", name="Ollama (AI Teacher)", status="warning", optional=True,
                message=f"Not reachable at {base} ({e.__class__.__name__}). Optional until Phase 9.",
                remediation="Install with `brew install ollama`, then run `ollama serve`",
            )
        models = tags.get("models", [])
        return ComponentHealth(
            id="ollama", name="Ollama (AI Teacher)", status="ok", optional=True,
            version=version.get("version"),
            message=f"{len(models)} model{'s' if len(models) != 1 else ''} installed" if models
                    else "Running, no models installed yet",
            details={"models": len(models)},
        )

    async def list_models(self) -> list[ModelInfo]:  # Phase 9
        raise NotImplementedError("Model listing arrives in Phase 9")

    def chat(self, messages: list[ChatMessage], model: str) -> AsyncIterator[str]:  # Phase 9
        raise NotImplementedError("AI Teacher chat arrives in Phase 9")
