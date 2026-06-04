from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from sqlmodel import Session as DbSession

from app.memory_store import (
    MemoryFilter,
    list_memory_items,
    memory_agent_roles,
    memory_target_ids,
)
from app.models import MemoryItem, utc_now

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
DEFAULT_RETRIEVAL_STATUSES = ("active", "warm")
STALE_PATTERN_DAYS = 365


@dataclass(frozen=True)
class RetrievedMemory:
    memory_item: MemoryItem
    score: float
    matched_terms: tuple[str, ...]
    rank: int

    def to_context(self) -> dict[str, object]:
        return {
            "id": self.memory_item.id,
            "scope": self.memory_item.scope,
            "type": self.memory_item.memory_type,
            "source": self.memory_item.source,
            "status": self.memory_item.status,
            "trustLevel": self.memory_item.trust_level,
            "title": self.memory_item.title,
            "contentMd": self.memory_item.content_md,
            "targetIds": memory_target_ids(self.memory_item),
            "agentRoles": memory_agent_roles(self.memory_item),
            "score": round(self.score, 4),
            "matchedTerms": list(self.matched_terms),
            "rank": self.rank,
        }


def retrieve_relevant_memories(
    db: DbSession,
    *,
    query: str,
    workspace_id: str | None,
    target_id: Optional[str] = None,
    agent_role: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 5,
) -> list[RetrievedMemory]:
    query_terms = _tokenize(query)
    if not query_terms:
        return []
    candidates: list[MemoryItem] = []
    for status in DEFAULT_RETRIEVAL_STATUSES:
        candidates.extend(
            list_memory_items(
                db,
                MemoryFilter(
                    workspace_id=workspace_id,
                    status=status,
                    scope=scope,
                ),
            )
        )
    seen: set[str] = set()
    scored: list[RetrievedMemory] = []
    for item in candidates:
        if item.id in seen or _is_stale_excluded(item):
            continue
        if not _matches_context(item, target_id=target_id, agent_role=agent_role):
            continue
        seen.add(item.id)
        score, matched_terms = _score_memory(query_terms, item)
        if score <= 0:
            continue
        scored.append(
            RetrievedMemory(
                memory_item=item,
                score=score,
                matched_terms=tuple(matched_terms),
                rank=0,
            )
        )
    ranked = sorted(
        scored,
        key=lambda result: (-result.score, result.memory_item.updated_at, result.memory_item.id),
    )[:limit]
    return [
        RetrievedMemory(
            memory_item=result.memory_item,
            score=result.score,
            matched_terms=result.matched_terms,
            rank=index + 1,
        )
        for index, result in enumerate(ranked)
    ]


def retrieved_memory_context(results: list[RetrievedMemory]) -> list[dict[str, object]]:
    return [result.to_context() for result in results]


def memory_precision_at_k(
    results: list[RetrievedMemory],
    relevant_ids: set[str],
    *,
    k: int = 5,
) -> float:
    if k <= 0:
        return 0.0
    top_k = results[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for result in top_k if result.memory_item.id in relevant_ids)
    return hits / min(k, len(top_k))


def _score_memory(query_terms: list[str], item: MemoryItem) -> tuple[float, list[str]]:
    corpus_terms = _tokenize(f"{item.title} {item.content_md}")
    if not corpus_terms:
        return 0.0, []
    matched_terms = sorted({term for term in query_terms if term in corpus_terms})
    if not matched_terms:
        return 0.0, []
    term_frequency = sum(corpus_terms.count(term) for term in matched_terms)
    bm25_like = term_frequency * (1.2 + len(matched_terms) / max(1, len(query_terms)))
    importance_boost = 1 + (item.importance / 200)
    trust_boost = _trust_boost(item.trust_level)
    recency_boost = _recency_boost(item)
    token_cost_penalty = _token_cost_penalty(item)
    stale_penalty = 0.5 if _is_stale_penalized(item) else 1.0
    status_boost = 1.0 if item.status == "active" else 0.7
    score = (
        bm25_like
        * importance_boost
        * trust_boost
        * recency_boost
        * stale_penalty
        * status_boost
        * token_cost_penalty
    )
    return score, matched_terms


def _matches_context(
    item: MemoryItem,
    *,
    target_id: Optional[str],
    agent_role: Optional[str],
) -> bool:
    target_ids = memory_target_ids(item)
    agent_roles = memory_agent_roles(item)
    if target_id is not None and target_ids and target_id not in target_ids:
        return False
    if agent_role is not None and agent_roles and agent_role not in agent_roles:
        return False
    return True


def _tokenize(value: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_PATTERN.finditer(value):
        token = match.group(0).lower()
        tokens.append(token)
        cjk_chars = [char for char in token if "\u4e00" <= char <= "\u9fff"]
        if cjk_chars:
            tokens.extend(cjk_chars)
            tokens.extend(
                "".join(cjk_chars[index : index + 2])
                for index in range(len(cjk_chars) - 1)
            )
    return tokens


def _trust_boost(trust_level: str) -> float:
    return {
        "user_confirmed": 1.4,
        "system": 1.15,
        "external": 0.75,
        "untrusted": 0.5,
    }.get(trust_level, 0.6)


def _recency_boost(item: MemoryItem) -> float:
    timestamp = item.last_used_at or item.updated_at
    age_days = max(0, (utc_now() - timestamp).days)
    return 1 + (1 / (1 + math.log1p(age_days)))


def _token_cost_penalty(item: MemoryItem) -> float:
    token_count = max(1, len(_tokenize(item.content_md)))
    if token_count <= 120:
        return 1.0
    return max(0.5, 120 / token_count)


def _is_stale_penalized(item: MemoryItem) -> bool:
    if item.memory_type not in {"pattern", "external_suggestion"}:
        return False
    timestamp = item.last_used_at or item.updated_at
    return utc_now() - timestamp > timedelta(days=STALE_PATTERN_DAYS)


def _is_stale_excluded(item: MemoryItem) -> bool:
    if item.status not in DEFAULT_RETRIEVAL_STATUSES:
        return True
    if item.memory_type != "pattern":
        return False
    timestamp = item.last_used_at or item.updated_at
    return utc_now() - timestamp > timedelta(days=STALE_PATTERN_DAYS * 2)
