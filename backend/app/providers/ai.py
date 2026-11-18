"""AI provider interface (planned, after Phase 6).

Rules every implementation must follow:
- never executes commands; it only returns text for the learner;
- external providers receive data only when the request carries consent=True;
- secrets (tokens, kubeconfig, passwords) are redacted before sending.
"""
from typing import Protocol

from pydantic import BaseModel


class AIRequest(BaseModel):
    task: str  # explain_error | explain_output | suggest_next_step | explain_yaml | hint
    content: str
    context: dict[str, str] = {}
    consent: bool = False


class AIProvider(Protocol):
    name: str
    external: bool

    async def complete(self, req: AIRequest) -> str: ...
