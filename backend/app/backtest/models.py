"""Backtest request / result contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    instrument_id: str
    symbol: str
    timeframe: str = "1m"
    # candle bars as list of dicts: open,high,low,close,volume,open_time,close_time
    bars: list[dict[str, Any]] = Field(default_factory=list)
    initial_cash: float = 10_000.0
    fee_rate: float = 0.0004  # 4 bps per side
    slippage_bps: float = 1.0  # 1 bp
    strategy: str = "rsi"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    engine: Literal["vectorized", "event"] = "vectorized"
    # PIT: analysis may only use data with available_at <= bar close_time
    enforce_pit: bool = True


class TradeRecord(BaseModel):
    entry_time: int
    exit_time: int | None = None
    side: str  # long | short
    entry_price: float
    exit_price: float | None = None
    quantity: float
    pnl: float | None = None
    pnl_pct: float | None = None
    fee: float = 0.0


class BacktestResult(BaseModel):
    run_id: str
    config_summary: dict[str, Any]
    engine: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate: float | None = None
    trades: list[TradeRecord] = Field(default_factory=list)
    equity_curve: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    pit_enforced: bool = True
    warnings: list[str] = Field(default_factory=list)
