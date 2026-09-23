"""Single-instrument analysis + long/short entry & position advice."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.ai.advice import TradingAdvice, build_trading_advice, build_indicator_only_advice
from app.data.market_klines import fetch_market_klines
from app.quant.indicators.analysis import analyze_bars
from app.main import (
    ai_orchestrator,
    feature_engine,
    instruments,
    risk_engine,
)

router = APIRouter(tags=["advice"])


class AdviceRequest(BaseModel):
    instrument_id: str | None = None
    symbol: str | None = None
    timeframe: str = "1m"
    run_analysis: bool = True
    holding_side: str | None = None
    market: str = "crypto"


def _resolve(instrument_id: str | None, symbol: str | None) -> tuple[str, str]:
    if instrument_id and symbol:
        return instrument_id, symbol
    if instrument_id:
        inst = instruments.get(instrument_id)
        if inst:
            return inst.instrument_id, inst.symbol
        # tolerate raw id
        return instrument_id, instrument_id.split(":")[-1]
    if symbol:
        raw = symbol.upper().replace("/", "")
        iid = f"binance:{raw}"
        inst = instruments.get(iid) or instruments.get_by_symbol(
            symbol if "/" in symbol else f"{raw[:-4]}/USDT" if raw.endswith("USDT") else symbol,
            "binance",
        )
        if inst:
            return inst.instrument_id, inst.symbol
        return iid, symbol.upper()
    raise HTTPException(400, "instrument_id or symbol required")


@router.get("/advice/{instrument_key}", response_model=TradingAdvice)
async def get_advice(
    instrument_key: str,
    timeframe: str = Query("1m"),
    run_analysis: bool = Query(True),
    market: str = Query("crypto"),
):
    """
    instrument_key: instrument_id (binance:BTCUSDT) or symbol (BTCUSDT / BTC/USDT)
    """
    if ":" in instrument_key:
        iid, sym = _resolve(instrument_key, None)
    else:
        iid, sym = _resolve(None, instrument_key)
    return await _build(iid, sym, timeframe, run_analysis, None, market)


async def _build(instrument_id: str, symbol: str, timeframe: str, run_analysis: bool, holding_side: str | None = None, market: str = "crypto") -> TradingAdvice:
    if market.lower() != "crypto":
        bars = await fetch_market_klines(symbol, market, timeframe, 250)
        report = analyze_bars(instrument_id=instrument_id, symbol=symbol, timeframe=timeframe, market=market, bars=bars)
        return build_indicator_only_advice(report, holding_side)
    analysis = ai_orchestrator.get_latest(instrument_id)
    if run_analysis or analysis is None:
        analysis = await ai_orchestrator.run(
            instrument_id=instrument_id,
            symbol=symbol,
            trigger="advice",
            timeframe=timeframe,
        )

    snap = feature_engine.get_latest(instrument_id, timeframe)
    last_price = None
    if snap and snap.features.get("close") is not None:
        last_price = float(snap.features["close"])

    # Analysis-only: optional user-supplied holding context; never query an account.
    has_long = holding_side == "long"
    has_short = holding_side == "short"

    return build_trading_advice(
        instrument_id=instrument_id,
        symbol=symbol,
        analysis=analysis,
        snapshot=snap,
        last_price=last_price,
        has_open_long=has_long,
        has_open_short=has_short,
        risk_limits=risk_engine.limits,
    )
