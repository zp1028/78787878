from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class GuardDecision:
    allowed: bool
    risk_level: str
    reasons: list[str] = field(default_factory=list)
    limits: dict[str, Any] = field(default_factory=dict)

class PostAIGuard:
    """Deterministic safety layer between analysis and any candidate action."""
    def evaluate(self, *, confidence: float, data_quality: float, portfolio_risk: str = "low", requested_leverage: float = 1.0) -> GuardDecision:
        reasons: list[str] = []
        if data_quality < 0.5:
            reasons.append("insufficient data quality")
        if confidence < 0.5:
            reasons.append("low analysis confidence")
        if portfolio_risk == "high":
            reasons.append("portfolio risk is high")
        if requested_leverage > 3:
            reasons.append("requested leverage exceeds guard limit")
        allowed = not reasons
        level = "blocked" if not allowed else ("medium" if confidence < .7 or data_quality < .8 else "low")
        return GuardDecision(allowed, level, reasons, {"max_leverage": 3.0, "min_confidence": .5, "min_data_quality": .5})
