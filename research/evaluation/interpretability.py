"""LLM-based interpretability scoring for regression models."""

from __future__ import annotations

import re

from research.agent.llm_client import LLMClient
from research.agent.prompts import INTERPRETABILITY_PROMPT


def score_interpretability(
    model_description: str,
    feature_names: list[str],
    metric_type: str,
    llm_client: LLMClient | None = None,
) -> float:
    """Score model interpretability using LLM judge.

    Returns a score between 0 and 1.
    Falls back to 0.5 if LLM call fails.
    """
    client = llm_client or LLMClient()

    prompt = INTERPRETABILITY_PROMPT.format(
        model_description=model_description,
        feature_names=", ".join(feature_names),
        metric_type=metric_type,
    )

    try:
        response = client.complete(
            system="You are a quantitative finance expert.",
            user=prompt,
            max_tokens=50,
            temperature=0.0,
        )

        text = response.content.strip()
        match = re.search(r"[\d.]+", text)
        if match:
            score = float(match.group())
            return max(0.0, min(1.0, score))
    except Exception:
        pass

    return 0.5
