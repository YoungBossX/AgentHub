from app.instruction_adapters.base import (
    ProviderInstructionAdapter,
    ProviderInstructionRequest,
)


class ClaudeCodeInstructionAdapter(ProviderInstructionAdapter):
    provider_id = "claude_code"

    def render(self, request: ProviderInstructionRequest) -> str:
        return request.core_instruction
