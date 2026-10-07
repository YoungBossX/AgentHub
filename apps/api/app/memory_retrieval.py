from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

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
MEMORY_SELECTION_POLICY_VERSION = "memory_rule_budget_v1"
DEFAULT_MEMORY_MAX_CHARS = 16000
CONFIRMED_TRUST_LEVELS = {"system", "user_confirmed"}


class MemoryContextBudgetError(ValueError):
    error_code = "MEMORY_CONTEXT_BUDGET_EXCEEDED"
    message = (
        "Active project rules exceed the memory context budget; shorten or archive "
        "rules, explicitly refresh the session snapshot, and retry."
    )

    def __init__(self) -> None:
        super().__init__(self.message)


@dataclass(frozen=True)
class RetrievedMemory:
    memory_item: MemoryItem
    score: float
    matched_terms: tuple[str, ...]
    rank: int
    layer: str = "experience"
    selection_reason: str = "lexical_match"

    def to_context(self) -> dict[str, object]:
        return {
            "id": self.memory_item.id,
            "version": self.memory_item.version,
            "contentHash": self.memory_item.content_hash,
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
            "layer": self.layer,
            "selectionReason": self.selection_reason,
        }


@dataclass(frozen=True)
class MemorySelection:
    memories: tuple[RetrievedMemory, ...]
    evidence: dict[str, object]

    def to_context(self) -> list[dict[str, object]]:
        return retrieved_memory_context(list(self.memories))


def serialized_memory_chars(memories: list[dict[str, object]]) -> int:
    """Measure the memory value, not the whole prompt or model token count."""
    return len(json.dumps(memories, ensure_ascii=True, sort_keys=True, indent=2))


def retrieve_relevant_memories(
    db: DbSession,
    *,
    query: str,
    workspace_id: str | None,
    target_id: Optional[str] = None,
    agent_role: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 5,
    candidates: Iterable[MemoryItem] | None = None,
    as_of: datetime | None = None,
    max_chars: int = DEFAULT_MEMORY_MAX_CHARS,
) -> list[RetrievedMemory]:
    return list(select_memory_context(
        db, query=query, workspace_id=workspace_id, target_id=target_id,
        agent_role=agent_role, scope=scope, limit=limit, candidates=candidates,
        as_of=as_of, max_chars=max_chars,
    ).memories)


def select_memory_context(
    db: DbSession,
    *,
    query: str,
    workspace_id: str | None,
    target_id: Optional[str] = None,
    agent_role: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 5,
    candidates: Iterable[MemoryItem] | None = None,
    as_of: datetime | None = None,
    max_chars: int = DEFAULT_MEMORY_MAX_CHARS,
) -> MemorySelection:
    if limit < 0 or max_chars < 2:
        raise ValueError("Memory limits require nonnegative experience slots and at least two JSON characters.")
    query_terms = _tokenize(query)
    scoring_time = as_of if as_of is not None else utc_now()
    if candidates is None:
        candidates = list_memory_items(
            db, MemoryFilter(workspace_id=workspace_id, scope=scope)
        )
    seen: set[str] = set()
    layers: dict[str, list[RetrievedMemory]] = {"rule": [], "preference": [], "experience": []}
    for item in candidates:
        if item.workspace_id != workspace_id or (scope is not None and item.scope != scope):
            continue
        if item.id in seen or _is_stale_excluded(item, scoring_time):
            continue
        if not _matches_context(item, target_id=target_id, agent_role=agent_role):
            continue
        seen.add(item.id)
        layer = _memory_layer(item)
        score, matched_terms = _score_memory(query_terms, item, scoring_time)
        if layer == "experience" and score <= 0:
            continue
        layers[layer].append(
            RetrievedMemory(
                memory_item=item,
                score=score,
                matched_terms=tuple(matched_terms),
                rank=0,
                layer=layer,
                selection_reason={
                    "rule": "applicable_trusted_rule",
                    "preference": "applicable_confirmed_preference",
                    "experience": "lexical_match",
                }[layer],
            )
        )
    selected: list[RetrievedMemory] = []
    contexts: list[dict[str, object]] = []
    counts = {layer: 0 for layer in layers}
    omitted_budget = {"preference": 0, "experience": 0}
    omitted_limit = 0
    for layer, memories in layers.items():
        ranked = sorted(memories, key=(
            (lambda result: (-result.score, result.memory_item.updated_at, result.memory_item.id))
            if layer == "experience" else
            (lambda result: (-result.memory_item.importance, result.memory_item.updated_at, result.memory_item.id))
        ))
        for result in ranked:
            if layer == "experience" and counts[layer] >= limit:
                omitted_limit += 1
                continue
            candidate = RetrievedMemory(
                memory_item=result.memory_item,
                score=result.score,
                matched_terms=result.matched_terms,
                rank=len(selected) + 1,
                layer=result.layer,
                selection_reason=result.selection_reason,
            )
            candidate_context = candidate.to_context()
            if serialized_memory_chars([*contexts, candidate_context]) > max_chars:
                if layer == "rule":
                    raise MemoryContextBudgetError()
                omitted_budget[layer] += 1
                continue
            selected.append(candidate)
            contexts.append(candidate_context)
            counts[layer] += 1
    return MemorySelection(tuple(selected), {
        "policyVersion": MEMORY_SELECTION_POLICY_VERSION,
        "budgetUnit": "serialized_json_characters",
        "maxChars": max_chars,
        "usedChars": serialized_memory_chars(contexts),
        "experienceLimit": limit,
        "selectedCounts": counts,
        "omittedByBudget": omitted_budget,
        "omittedByExperienceLimit": omitted_limit,
    })


def _memory_layer(item: MemoryItem) -> str:
    if item.status == "active" and item.trust_level in CONFIRMED_TRUST_LEVELS:
        if item.memory_type == "project_rule":
            return "rule"
        if item.memory_type == "user_preference":
            return "preference"
    return "experience"


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


def _score_memory(
    query_terms: list[str], item: MemoryItem, as_of: datetime
) -> tuple[float, list[str]]:
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
    recency_boost = _recency_boost(item, as_of)
    token_cost_penalty = _token_cost_penalty(item)
    stale_penalty = 0.5 if _is_stale_penalized(item, as_of) else 1.0
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
    # The current schema has no Session owner; do not widen that scope to a workspace.
    if item.scope == "session" or (item.scope == "target" and not target_ids):
        return False
    if target_ids and target_id not in target_ids:
        return False
    if agent_roles and agent_role not in agent_roles:
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


def _recency_boost(item: MemoryItem, as_of: datetime) -> float:
    timestamp = item.last_used_at or item.updated_at
    age_days = max(0, (as_of - timestamp).days)
    return 1 + (1 / (1 + math.log1p(age_days)))


def _token_cost_penalty(item: MemoryItem) -> float:
    token_count = max(1, len(_tokenize(item.content_md)))
    if token_count <= 120:
        return 1.0
    return max(0.5, 120 / token_count)


def _is_stale_penalized(item: MemoryItem, as_of: datetime) -> bool:
    if item.memory_type not in {"pattern", "external_suggestion"}:
        return False
    timestamp = item.last_used_at or item.updated_at
    return as_of - timestamp > timedelta(days=STALE_PATTERN_DAYS)


def _is_stale_excluded(item: MemoryItem, as_of: datetime) -> bool:
    if item.status not in DEFAULT_RETRIEVAL_STATUSES:
        return True
    if item.memory_type != "pattern":
        return False
    timestamp = item.last_used_at or item.updated_at
    return as_of - timestamp > timedelta(days=STALE_PATTERN_DAYS * 2)
