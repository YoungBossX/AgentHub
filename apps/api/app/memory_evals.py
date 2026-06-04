from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.memory_retrieval import RetrievedMemory


@dataclass(frozen=True)
class MemoryEvalSummary:
    preference_recall_rate: float
    cross_agent_consistency_rate: float
    memory_precision_at_5: float
    stale_memory_injection_count: int
    prompt_injection_write_block_rate: float
    snapshot_consistency_rate: float

    def to_payload(self) -> dict[str, float | int]:
        return {
            "preferenceRecallRate": self.preference_recall_rate,
            "crossAgentConsistencyRate": self.cross_agent_consistency_rate,
            "memoryPrecisionAt5": self.memory_precision_at_5,
            "staleMemoryInjectionCount": self.stale_memory_injection_count,
            "promptInjectionWriteBlockRate": self.prompt_injection_write_block_rate,
            "snapshotConsistencyRate": self.snapshot_consistency_rate,
        }


def preference_recall_rate(
    expected_memory_ids: set[str],
    retrieved_memory_ids: Iterable[str],
) -> float:
    if not expected_memory_ids:
        return 1.0
    retrieved = set(retrieved_memory_ids)
    return len(expected_memory_ids & retrieved) / len(expected_memory_ids)


def cross_agent_consistency_rate(snapshot_ids_by_agent: dict[str, str | None]) -> float:
    if not snapshot_ids_by_agent:
        return 1.0
    expected = next(iter(snapshot_ids_by_agent.values()))
    if expected is None:
        return 0.0
    consistent = sum(
        1
        for snapshot_id in snapshot_ids_by_agent.values()
        if snapshot_id == expected
    )
    return consistent / len(snapshot_ids_by_agent)


def memory_precision_at_5(
    results: list[RetrievedMemory],
    relevant_memory_ids: set[str],
) -> float:
    top_five = results[:5]
    if not top_five:
        return 0.0
    hits = sum(
        1
        for result in top_five
        if result.memory_item.id in relevant_memory_ids
    )
    return hits / len(top_five)


def stale_memory_injection_count(memory_context: Iterable[dict[str, object]]) -> int:
    return sum(
        1
        for item in memory_context
        if item.get("status") in {"archived", "rejected", "deleted"}
        or item.get("stale") is True
    )


def prompt_injection_write_block_rate(blocked_attempts: int, total_attempts: int) -> float:
    if total_attempts <= 0:
        return 1.0
    return blocked_attempts / total_attempts


def snapshot_consistency_rate(snapshot_ids: Iterable[str | None]) -> float:
    ids = list(snapshot_ids)
    if not ids:
        return 1.0
    expected = ids[0]
    if expected is None:
        return 0.0
    return sum(1 for snapshot_id in ids if snapshot_id == expected) / len(ids)
