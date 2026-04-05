from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.common import AIQualityMode


class ClaudeTask(str, Enum):
    BULK_ANALYSIS = "bulk_analysis"
    PROFILE_SYNTHESIS = "profile_synthesis"
    QA = "qa"
    REPLY_COACH = "reply_coach"


@dataclass(frozen=True)
class ClaudeModelPricing:
    model: str
    input_cost_per_mtok: float
    output_cost_per_mtok: float


@dataclass(frozen=True)
class ClaudeRequestPlan:
    task: ClaudeTask
    mode: AIQualityMode
    model: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    downgraded: bool


@dataclass(frozen=True)
class ClaudeTextResult:
    content: str
    plan: ClaudeRequestPlan


@dataclass(frozen=True)
class ClaudeJSONResult:
    data: dict[str, Any]
    raw_content: str
    plan: ClaudeRequestPlan


def plan_claude_request(
    system_prompt: str,
    user_prompt: str,
    *,
    task: ClaudeTask,
    max_tokens: int = 1200,
    mode: AIQualityMode | None = None,
    settings: Settings | None = None,
) -> ClaudeRequestPlan | None:
    settings = settings or get_settings()
    if not settings.anthropic_api_key:
        return None

    resolved_mode = mode or settings.anthropic_default_mode
    requested_models = _candidate_models(task, resolved_mode, settings)
    estimated_input_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
    estimated_output_tokens = max_tokens
    budget_cap = _budget_cap(task, settings)

    first_model = requested_models[0]
    first_plan = _build_plan(
        model=first_model,
        task=task,
        mode=resolved_mode,
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        downgraded=False,
    )
    if len(requested_models) == 1 or first_plan.estimated_cost_usd <= budget_cap:
        return first_plan

    for candidate in requested_models[1:]:
        downgraded_plan = _build_plan(
            model=candidate,
            task=task,
            mode=resolved_mode,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            downgraded=True,
        )
        if downgraded_plan.estimated_cost_usd <= budget_cap or candidate == requested_models[-1]:
            return downgraded_plan

    return first_plan


def maybe_generate_text(
    system_prompt: str,
    user_prompt: str,
    *,
    task: ClaudeTask,
    max_tokens: int = 1200,
    mode: AIQualityMode | None = None,
) -> ClaudeTextResult | None:
    plan = plan_claude_request(
        system_prompt,
        user_prompt,
        task=task,
        max_tokens=max_tokens,
        mode=mode,
    )
    if not plan:
        return None

    settings = get_settings()
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=plan.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        chunks: list[str] = []
        for item in response.content:
            text = getattr(item, "text", None)
            if text:
                chunks.append(text)
        content = "\n".join(chunks).strip()
        if not content:
            return None
        return ClaudeTextResult(content=content, plan=plan)
    except Exception:
        return None


def maybe_generate_json(
    system_prompt: str,
    user_prompt: str,
    *,
    task: ClaudeTask,
    max_tokens: int = 1200,
    mode: AIQualityMode | None = None,
) -> ClaudeJSONResult | None:
    text_result = maybe_generate_text(
        system_prompt,
        user_prompt,
        task=task,
        max_tokens=max_tokens,
        mode=mode,
    )
    if not text_result:
        return None

    payload = _parse_json_payload(text_result.content)
    if payload is None:
        return None
    return ClaudeJSONResult(
        data=payload,
        raw_content=text_result.content,
        plan=text_result.plan,
    )


def _candidate_models(
    task: ClaudeTask,
    mode: AIQualityMode,
    settings: Settings,
) -> list[str]:
    if settings.anthropic_model:
        return [settings.anthropic_model]

    haiku = settings.anthropic_model_haiku
    sonnet = settings.anthropic_model_sonnet
    opus = settings.anthropic_model_opus

    match task:
        case ClaudeTask.BULK_ANALYSIS:
            mapping = {
                AIQualityMode.CHEAP: [haiku],
                AIQualityMode.BALANCED: [haiku, sonnet],
                AIQualityMode.PREMIUM: [sonnet, haiku],
            }
        case ClaudeTask.PROFILE_SYNTHESIS:
            mapping = {
                AIQualityMode.CHEAP: [haiku],
                AIQualityMode.BALANCED: [sonnet, haiku],
                AIQualityMode.PREMIUM: ([opus, sonnet, haiku] if settings.anthropic_allow_opus else [sonnet, haiku]),
            }
        case ClaudeTask.QA | ClaudeTask.REPLY_COACH:
            mapping = {
                AIQualityMode.CHEAP: [haiku],
                AIQualityMode.BALANCED: [sonnet, haiku],
                AIQualityMode.PREMIUM: ([opus, sonnet, haiku] if settings.anthropic_allow_opus else [sonnet, haiku]),
            }
        case _:
            mapping = {
                AIQualityMode.CHEAP: [haiku],
                AIQualityMode.BALANCED: [sonnet, haiku],
                AIQualityMode.PREMIUM: ([opus, sonnet, haiku] if settings.anthropic_allow_opus else [sonnet, haiku]),
            }

    return list(dict.fromkeys(mapping[mode]))


def _budget_cap(task: ClaudeTask, settings: Settings) -> float:
    if task == ClaudeTask.BULK_ANALYSIS:
        return settings.anthropic_bulk_request_budget_usd
    if task == ClaudeTask.PROFILE_SYNTHESIS:
        return settings.anthropic_profile_request_budget_usd
    return settings.anthropic_live_request_budget_usd


def _build_plan(
    *,
    model: str,
    task: ClaudeTask,
    mode: AIQualityMode,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
    downgraded: bool,
) -> ClaudeRequestPlan:
    pricing = _resolve_pricing(model)
    estimated_cost = (
        (estimated_input_tokens / 1_000_000) * pricing.input_cost_per_mtok
        + (estimated_output_tokens / 1_000_000) * pricing.output_cost_per_mtok
    )
    return ClaudeRequestPlan(
        task=task,
        mode=mode,
        model=model,
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        estimated_cost_usd=round(estimated_cost, 4),
        downgraded=downgraded,
    )


def _resolve_pricing(model: str) -> ClaudeModelPricing:
    normalized = model.lower()
    if "opus" in normalized:
        return ClaudeModelPricing(model=model, input_cost_per_mtok=5.0, output_cost_per_mtok=25.0)
    if "sonnet" in normalized:
        return ClaudeModelPricing(model=model, input_cost_per_mtok=3.0, output_cost_per_mtok=15.0)
    if "haiku" in normalized:
        return ClaudeModelPricing(model=model, input_cost_per_mtok=1.0, output_cost_per_mtok=5.0)
    return ClaudeModelPricing(model=model, input_cost_per_mtok=3.0, output_cost_per_mtok=15.0)


def _estimate_tokens(content: str) -> int:
    return max(1, math.ceil(len(content) / 4))


def _parse_json_payload(content: str) -> dict[str, Any] | None:
    direct = _try_json_load(content)
    if direct is not None:
        return direct

    stripped = content.strip()
    if stripped.startswith("```"):
        fenced = stripped.split("\n", 1)[-1]
        if fenced.endswith("```"):
            fenced = fenced[:-3]
        direct = _try_json_load(fenced.strip())
        if direct is not None:
            return direct

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return _try_json_load(stripped[start : end + 1])
    return None


def _try_json_load(content: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
