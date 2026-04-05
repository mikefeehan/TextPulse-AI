from __future__ import annotations

import os

from app.core.config import get_settings
from app.schemas.common import AIQualityMode
from app.services.llm import ClaudeTask, plan_claude_request


def _configure_claude_env(**overrides: str) -> None:
    defaults = {
        "ANTHROPIC_API_KEY": "test-key",
        "ANTHROPIC_DEFAULT_MODE": "balanced",
        "ANTHROPIC_MODEL_HAIKU": "claude-haiku-4-5",
        "ANTHROPIC_MODEL_SONNET": "claude-sonnet-4-6",
        "ANTHROPIC_MODEL_OPUS": "claude-opus-4-6",
        "ANTHROPIC_ALLOW_OPUS": "false",
        "ANTHROPIC_BULK_REQUEST_BUDGET_USD": "0.15",
        "ANTHROPIC_LIVE_REQUEST_BUDGET_USD": "0.35",
        "ANTHROPIC_PROFILE_REQUEST_BUDGET_USD": "0.90",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        os.environ[key] = value
    get_settings.cache_clear()


def test_balanced_profile_prefers_sonnet_under_normal_budget() -> None:
    _configure_claude_env(ANTHROPIC_PROFILE_REQUEST_BUDGET_USD="1.50")

    plan = plan_claude_request(
        "Profile synthesis strategy",
        "Condensed relationship data",
        task=ClaudeTask.PROFILE_SYNTHESIS,
        max_tokens=1400,
        mode=AIQualityMode.BALANCED,
    )

    assert plan is not None
    assert plan.model == "claude-sonnet-4-6"
    assert plan.downgraded is False


def test_profile_downgrades_to_haiku_when_budget_is_tight() -> None:
    _configure_claude_env(ANTHROPIC_PROFILE_REQUEST_BUDGET_USD="0.02")
    long_digest = "signal " * 3000

    plan = plan_claude_request(
        "Profile synthesis strategy",
        long_digest,
        task=ClaudeTask.PROFILE_SYNTHESIS,
        max_tokens=1400,
        mode=AIQualityMode.BALANCED,
    )

    assert plan is not None
    assert plan.model == "claude-haiku-4-5"
    assert plan.downgraded is True
