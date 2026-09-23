from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class ContextFinding:
    agent: str
    stance: str
    score: float | None
    confidence: float
    reasons: list[str]


def _finding(agent: str, score: float | None, reason: str, confidence: float) -> ContextFinding:
    if score is None:
        return ContextFinding(agent, "unavailable", None, 0.0, [reason])
    score = max(0.0, min(1.0, float(score)))
    stance = "bullish" if score > .55 else "bearish" if score < .45 else "neutral"
    return ContextFinding(agent, stance, score, confidence, [reason])


def analyze_news(features):
    value = features.get("news_sentiment")
    if value is None:
        return _finding("NewsAgent", None, "no point-in-time news sentiment supplied", 0.0)
    return _finding("NewsAgent", (float(value) + 1) / 2, "point-in-time news sentiment", 1.0)


def analyze_macro(features):
    value = features.get("macro_score")
    if value is None:
        return _finding("MacroAgent", None, "no point-in-time macro score supplied", 0.0)
    return _finding("MacroAgent", (float(value) + 1) / 2, "point-in-time macro context", 1.0)


def analyze_onchain(features):
    value = features.get("onchain_score")
    if value is None:
        return _finding("OnChainAgent", None, "no on-chain score supplied", 0.0)
    return _finding("OnChainAgent", (float(value) + 1) / 2, "on-chain flow context", 1.0)
