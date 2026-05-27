from app.instruction_adapters.base import (
    ProviderInstructionAdapter,
    ProviderInstructionRequest,
)


class CodexInstructionAdapter(ProviderInstructionAdapter):
    provider_id = "codex"

    def render(self, request: ProviderInstructionRequest) -> str:
        return (
            "Codex Provider Instruction\n"
            "Use the canonical context below as the source of truth. "
            "Keep changes patch-oriented and preserve all target, contract, "
            "handoff, validation, and guardrail facts.\n\n"
            f"{request.core_instruction}"
        )
