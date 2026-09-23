"""Risk proposal / validation contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AccountState(BaseModel):
    account_id: str = "default"
    equity: float = 10_000.0
    cash: float = 10_000.0
    used_margin: float = 0.0
    open_positions: list[dict[str, Any]] = Field(default_factory=list)
    # open_positions item: instrument_id, side, quantity, entry_price, notional


class RiskLimits(BaseModel):
    max_position_pct: float = 0.25          # single name max 25% equity
    max_leverage: float = 3.0
    max_portfolio_exposure_pct: float = 1.0  # 100% gross
    max_account_loss_pct: float = 0.10       # 10% daily/session loss halt
    min_stop_distance_pct: float = 0.005     # stop at least 0.5% away
    max_stop_distance_pct: float = 0.15      # stop not wider than 15%
    max_correlated_exposure_pct: float = 0.40
    min_liquidity_notional: float = 0.0      # placeholder
    allow_short: bool = True


class TradeProposal(BaseModel):
    """What AI or strategy proposes — Risk Engine decides if valid."""

    instrument_id: str
    symbol: str
    side: Literal["long", "short", "flat"]
    entry_price: float | None = None
    stop_price: float | None = None
    take_profit: float | None = None
    position_pct: float | None = None       # requested fraction of equity
    quantity: float | None = None
    leverage: float = 1.0
    reason: str = ""
    source: str = "ai"  # ai | strategy | manual


class RiskViolation(BaseModel):
    code: str
    message: str
    severity: Literal["block", "warn"] = "block"


class RiskDecision(BaseModel):
    approved: bool
    proposal: TradeProposal
    adjusted: TradeProposal | None = None   # size/stop clipped version if partially ok
    violations: list[RiskViolation] = Field(default_factory=list)
    risk_score: float = 0.0                 # 0 safe → 1 high
    metrics: dict[str, Any] = Field(default_factory=dict)
    checked_at: int = 0
