from app.instruction_adapters.base import ProviderInstructionAdapter
from app.instruction_adapters.claude_code import ClaudeCodeInstructionAdapter
from app.instruction_adapters.codex import CodexInstructionAdapter
from app.instruction_adapters.scripted_mock import ScriptedMockInstructionAdapter


def adapter_for_provider(adapter_type: str) -> ProviderInstructionAdapter:
    if adapter_type == "claude_code":
        return ClaudeCodeInstructionAdapter()
    if adapter_type == "scripted_mock":
        return ScriptedMockInstructionAdapter()
    return CodexInstructionAdapter()
