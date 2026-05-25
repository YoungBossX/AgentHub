from app.instruction_adapters.base import (
    ProviderInstructionAdapter,
    ProviderInstructionRequest,
)


class ScriptedMockInstructionAdapter(ProviderInstructionAdapter):
    provider_id = "scripted_mock"

    def render(self, request: ProviderInstructionRequest) -> str:
        return request.core_instruction
