from dataclasses import dataclass
from typing import Any

from app.models import Agent, Task


@dataclass(frozen=True)
class ProviderInstructionRequest:
    task: Task
    agent: Agent
    adapter_type: str
    role: str
    context_pack: dict[str, Any]
    core_instruction: str


class ProviderInstructionAdapter:
    provider_id = "base"

    def render(self, request: ProviderInstructionRequest) -> str:
        return request.core_instruction
