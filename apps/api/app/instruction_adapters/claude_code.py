from app.instruction_adapters.base import (
    ProviderInstructionAdapter,
    ProviderInstructionRequest,
)


class ClaudeCodeInstructionAdapter(ProviderInstructionAdapter):
    provider_id = "claude_code"

    def render(self, request: ProviderInstructionRequest) -> str:
        return (
            "Claude Code Provider Instruction\n"
            "Use the canonical context below as the source of truth. "
            "Favor a concise implementation plan before editing, and preserve "
            "all target, contract, handoff, validation, and guardrail facts.\n\n"
            f"{request.core_instruction}"
        )
