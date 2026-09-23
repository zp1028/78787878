"""Structured AI analysis contract — the only allowed AI output shape."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    source: str  # technical | money_flow | news | macro | onchain | signal | feature
    agent: str
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    data_snapshot_id: str | None = None
    timestamp: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Scenario(BaseModel):
    name: str  # bull | base | bear
    thesis: str
    # None means there are not enough completed historical outcomes to claim a calibrated probability.
    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    invalidation: str | None = None


class AnalysisResult(BaseModel):
    """Frozen API contract for all AI outputs."""

    analysis_id: str
    instrument_id: str
    symbol: str
    timestamp: int
    market_state: str = "unknown"
    trend: str = "neutral"  # bullish | bearish | neutral | mixed
    technical: dict[str, Any] = Field(default_factory=dict)
    money_flow: dict[str, Any] = Field(default_factory=dict)
    sentiment: dict[str, Any] = Field(default_factory=dict)
    macro: dict[str, Any] = Field(default_factory=dict)
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    support: list[float] = Field(default_factory=list)
    resistance: list[float] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    risk: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    trigger: str = "manual"
    regime: str | None = None
