"""Conservative request boundaries; recognition evidence grants no permissions."""
from dataclasses import dataclass, replace
import re
import unicodedata
from typing import Literal


RequestType = Literal["change", "review", "explain", "status", "chat", "no_action", "clarification", "unknown"]
Route = Literal["continue", "planner", "reply", "clarify"]
Source = Literal["rule", "llm"]


@dataclass(frozen=True)
class IntentDecision:
    request_type: RequestType
    route: Route
    source: Source = "rule"
    action: str | None = None
    target: str | None = None
    parameters: tuple[tuple[str, str], ...] = ()
    reason_codes: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()

    @property
    def allows_rule_fallback(self) -> bool:
        return self.route == "continue"

    @property
    def allows_rule_mutation(self) -> bool:
        return self.allows_rule_fallback and self.request_type in {"unknown", "change"}

    def to_payload(self) -> dict:
        return {"schemaVersion": 1, "requestType": self.request_type,
                "route": self.route, "source": self.source, "action": self.action,
                "target": self.target, "parameters": dict(self.parameters),
                "reasonCodes": list(self.reason_codes), "missingFields": list(self.missing_fields),
                "roles": list(self.roles)}


# Only matched quote pairs are removed. Apostrophes in don't/it's are prose.
QUOTED = re.compile(r"```[\s\S]*?```|`[^`\n]*`|\"[^\"\n]*\"|“[^”\n]*”|‘[^’\n]*’|(?<!\w)'[^'\n]*'(?!\w)")
# An ASCII mailbox/local token is data. Chinese prose may directly precede
# an alias, so a blanket Unicode word boundary would break "请@frontend".
# Unicode mailbox tails, including combining marks, need a category check.
# Bare unknown aliases still reach the existing fail-closed role validation.
_MENTION = re.compile(r"(?<![A-Za-z0-9._%+\-])@([A-Za-z][A-Za-z0-9_-]*)")
_DOMAIN_SUFFIX = re.compile(r"\.[A-Za-z0-9]")


def _is_agent_mention(match: re.Match) -> bool:
    if match.start() == 0:
        return True
    previous = match.string[match.start() - 1]
    mailbox_tail = previous.isalnum() or unicodedata.category(previous).startswith("M")
    return not (mailbox_tail and _DOMAIN_SUFFIX.match(match.string, match.end()))


def mention_aliases(content: str) -> list[str]:
    return [match.group(1) for match in _MENTION.finditer(content) if _is_agent_mention(match)]


def remove_agent_mentions(content: str) -> str:
    return _MENTION.sub(lambda match: "" if _is_agent_mention(match) else match.group(), content)


# Strip only explicit neutral scope/politeness clauses. Arbitrary prose before
# a comma may contain another action, negation or a question and must stay.
INTRODUCTION = re.compile(
    r"^(?:(?:(?:in|on|inside|within|for)\s+(?:(?:the|this|current|a)\s+)*"
    r"(?:demo(?:\s+(?:app|application|frontend))?|apps/demo|page|login\s+page|task)|"
    r"(?:在|针对|对于|为)(?:当前|本次|这个)?(?:演示应用|demo(?:\s+app)?|apps/demo|页面|登录页|任务)(?:中|里)?|"
    r"please|请)\s*[,，]\s*)+", re.I,
)
NEGATION = re.compile(r"^(?:please\s+|请\s*)?(?:先|暂时)?(?:do\s+not\b|don't\b|never\b|不要|不用|别|禁止|我不想|我不需要|我不是要)", re.I)
EXPLAIN = re.compile(r"^(?:(?:please|could you|would you|can you)\s+|请\s*|帮我\s*|先\s*|(?:你能|能否|可以)(?:不能)?\s*)?(?:explain\b|describe\b|tell me\b|how\s+(?:to|do|can)\b|what\s+(?:is|does|are)\b|why\b|解释|说明|讲解|介绍|为什么|如何|怎么|请问|我想知道|想了解)", re.I)
STATUS = re.compile(r"^(?:(?:please\s+)?(?:show|check)\s+(?:the\s+)?(?:task|run|execution)\s+status\b|(?:查看|查询)(?:一下)?(?:任务|运行|执行)(?:的)?(?:状态|进度)|(?:任务|运行|执行)(?:完成了吗|到哪了|的进度))", re.I)
REVIEW = re.compile(r"^(?:please\s+|请\s*|帮我\s*)?(?:review\b|audit\b|审查|评审|检查(?:一下)?(?:代码|改动|diff))", re.I)
REFERENCE = re.compile(r"^(?:example\b|quoted?\b|documentation\b|write documentation\b|示例|例子|引用|这句话|下面(?:这段|的)?(?:代码|文本)|文档(?:中|里|写))", re.I)
ACTION = r"(?:change\b|add\b|build\b|create\b|implement\b|fix\b|update\b|改成|修改|添加|新增|创建|实现|修复|构建|接入|对接)"
SECOND_ACTION = re.compile(r"(?:\b(?:and|then|also)\s+|同时|然后|并且|并|再|[;；，,]\s*)(?:please\s+|请\s*|把[^，,;；]{0,20}?)?" + ACTION, re.I)
SECOND_COPY = re.compile(r"(?:\band\s+|[;；，,]\s*|同时|然后)(?:the\s+|把|将)?(?:button(?:\s+text)?|title|heading|按钮(?:文案)?|标题(?:文案)?)(?:\s+to\b|改成)", re.I)


def routing_text(content: str) -> str:
    """Quoted mentions must not select recipients or produce unknown-role errors."""
    return QUOTED.sub(" ", content)


def strip_mentions(content: str) -> str:
    parts = []
    start = 0
    for match in QUOTED.finditer(content):
        parts.extend((remove_agent_mentions(content[start:match.start()]), match.group()))
        start = match.end()
    return "".join((*parts, remove_agent_mentions(content[start:])))


def command_match(pattern: re.Pattern, text: str):
    quoted = [(match.start(), match.end()) for match in QUOTED.finditer(text)]
    return next((match for match in pattern.finditer(text)
                 if not any(start <= match.start() < end for start, end in quoted)), None)


def request_boundary(content: str) -> IntentDecision:
    if content.count("```") % 2:
        return IntentDecision("clarification", "clarify", reason_codes=("UNCLOSED_CODE_REFERENCE",))
    text = remove_agent_mentions(routing_text(content)).strip().strip(".!。！ ")
    text = INTRODUCTION.sub("", text)
    if not text:
        return IntentDecision("clarification", "clarify", reason_codes=("NO_ACTION_OUTSIDE_REFERENCE",), missing_fields=("request",))
    if NEGATION.search(text):
        if SECOND_ACTION.search(text):
            return IntentDecision("unknown", "planner", reason_codes=("NEGATED_MIXED_REQUEST",))
        return IntentDecision("no_action", "reply", reason_codes=("NEGATED_REQUEST",))
    if EXPLAIN.search(text) or REFERENCE.search(text):
        # An explanation plus a separate imperative needs full semantic planning.
        if SECOND_ACTION.search(text):
            return IntentDecision("unknown", "planner", reason_codes=("MIXED_REQUEST",))
        return IntentDecision("explain", "reply", reason_codes=("INFORMATIONAL_REQUEST",))
    if STATUS.search(text):
        if SECOND_ACTION.search(text):
            return IntentDecision("unknown", "planner", reason_codes=("MIXED_STATUS_WRITE",))
        return IntentDecision("status", "reply", reason_codes=("STATUS_REQUEST",))
    if REVIEW.search(text):
        if SECOND_ACTION.search(text):
            return IntentDecision("unknown", "planner", reason_codes=("MIXED_REVIEW_WRITE",))
        return IntentDecision("review", "continue", reason_codes=("REVIEW_REQUEST",))
    if text.lower().strip(" ?？") in {"你好", "您好", "hello", "hi", "hey", "你能做什么", "你可以做什么", "what can you do", "what can agenthub do"}:
        return IntentDecision("chat", "reply", reason_codes=("FIXED_CHAT",))
    # Process notes supported by the old login template do not add product actions.
    product_text = re.sub(r"(?:代码改动必须)?更新\s+docs/change-log\.md(?:\s+并运行项目验证)?", "", text)
    if SECOND_ACTION.search(product_text) or SECOND_COPY.search(product_text):
        return IntentDecision("unknown", "planner", reason_codes=("MULTIPLE_ACTIONS",))
    if re.search(r"(?:那个|这个|它)(?:改|修)|(?:改|修)(?:一下|好)?(?:那个|这个|它)|\b(?:change|fix)\s+(?:it|that|this)\b", text, re.I):
        return IntentDecision("clarification", "planner", reason_codes=("UNRESOLVED_REFERENCE",), missing_fields=("target",))
    return IntentDecision("unknown", "continue", reason_codes=("NO_BOUNDED_RULE",))


def decision_from_outcome(prior: IntentDecision, outcome: dict) -> IntentDecision:
    """Map validated existing Planner outcomes; never trust an LLM confidence number."""
    kind = outcome["outcomeType"]
    if kind == "task_plan":
        tasks = outcome.get("planDraft", {}).get("tasks", [])
        review_only = bool(tasks) and all(item.get("role") in {"qa", "review"} for item in tasks)
        return replace(prior, source="llm", request_type="review" if review_only else "change",
                       route="continue", action=None, target=None, parameters=(), missing_fields=(),
                       reason_codes=("LLM_TASK_PLAN",))
    request_type = "clarification" if kind == "clarification" else (
        prior.request_type if prior.request_type in {"explain", "status", "chat", "no_action"} else "unknown")
    return replace(prior, source="llm", request_type=request_type,
                   route="clarify" if kind == "clarification" else "reply", action=None,
                   target=None, parameters=(), reason_codes=("LLM_" + kind.upper(),))


def boundary_reply(decision: IntentDecision) -> str:
    if "LLM_ACTION_CONFLICT" in decision.reason_codes:
        return "Planner 返回的写任务与本条解释、查询或审查请求不符，未创建任务。请明确是否需要修改代码。"
    if decision.request_type == "no_action":
        return "已识别到不要执行修改的要求，本条消息未创建修改任务。"
    if decision.request_type in {"explain", "status", "chat"}:
        return "这是一条解释、查询或对话请求，未创建修改任务。需要结合项目回答时，请使用可用的 @orchestrator Planner；查看进度也可使用执行过程面板。"
    if decision.request_type == "review":
        return "已识别为审查请求，未创建写任务。请使用 @review 或 @qa 指定审查角色。"
    return "当前无法安全地把这条消息转换为单一规则任务，未创建修改任务。请明确操作对象和完整参数，或启用 Planner 处理多项需求与上下文指代。"
