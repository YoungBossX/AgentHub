from app.instruction_adapters.base import (
    ProviderInstructionAdapter,
    ProviderInstructionRequest,
)


class CodexInstructionAdapter(ProviderInstructionAdapter):
    provider_id = "codex"

    def render(self, request: ProviderInstructionRequest) -> str:
        return request.core_instruction
