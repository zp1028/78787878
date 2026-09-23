from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Literal

from app.backtest.event_driven.engine import run_event_driven
from app.backtest.models import BacktestConfig
from app.backtest.vectorized.engine import run_vectorized
from app.backtest.walk_forward import run_walk_forward

router = APIRouter(tags=["backtests"])


class BacktestRequest(BaseModel):
    instrument_id: str = "binance:BTCUSDT"
    symbol: str = "BTCUSDT"
    timeframe: str = "1m"
    bars: list[dict[str, Any]] = Field(default_factory=list)
    initial_cash: float = 10_000.0
    fee_rate: float = 0.0004
    slippage_bps: float = 1.0
    strategy: str = "rsi"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    engine: Literal["vectorized", "event", "walk_forward"] = "vectorized"
    enforce_pit: bool = True
    train_ratio: float = 0.6
    validation_ratio: float = 0.2
    parameter_candidates: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/backtests")
async def create_backtest(body: BacktestRequest):
    if len(body.bars) < 10:
        raise HTTPException(status_code=400, detail="need at least 10 bars")

    cfg = BacktestConfig(
        instrument_id=body.instrument_id,
        symbol=body.symbol,
        timeframe=body.timeframe,
        bars=body.bars,
        initial_cash=body.initial_cash,
        fee_rate=body.fee_rate,
        slippage_bps=body.slippage_bps,
        strategy=body.strategy if body.strategy != "buy_hold" or body.engine != "event" else "rsi",
        strategy_params=body.strategy_params,
        engine="vectorized" if body.engine == "walk_forward" else body.engine,
        enforce_pit=body.enforce_pit,
    )

    if body.engine == "walk_forward":
        return run_walk_forward(cfg, train_ratio=body.train_ratio, val_ratio=body.validation_ratio, candidates=body.parameter_candidates or None)

    if body.engine == "event":
        result = await run_event_driven(cfg)
    else:
        result = run_vectorized(cfg)
    return result.model_dump()
