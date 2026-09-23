"""Multi-timeframe indicator + oversold/overbought analysis API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
import asyncio

from app.data.klines import SUPPORTED_INTERVALS
from app.data.market_klines import fetch_market_klines
from app.quant.indicators.analysis import IndicatorReport, analyze_bars

router = APIRouter(tags=["indicators"])


@router.get("/timeframes")
async def list_timeframes():
    return {
        "intervals": sorted(SUPPORTED_INTERVALS, key=lambda x: (
            {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
             "4h": 240, "6h": 360, "12h": 720, "1d": 1440, "1w": 10080}.get(x, 9999)
        )),
        "default": "15m",
    }


@router.get("/indicators/{symbol}", response_model=IndicatorReport)
async def get_indicators(
    symbol: str,
    timeframe: str = Query("15m", description="1m/5m/15m/1h/4h/1d/..."),
    limit: int = Query(200, ge=30, le=500),
    rsi_period: int = Query(14, ge=2, le=50),
    rsi_oversold: float = Query(30.0, ge=1, le=40),
    rsi_overbought: float = Query(70.0, ge=60, le=99),
    market: str = Query("crypto"),
):
    """
    Switch period via `timeframe`. Returns RSI/MACD/Bollinger/SMA/EMA,
    oversold/overbought states, and active signals for that period.
    """
    tf = timeframe.strip().lower()
    if tf not in SUPPORTED_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported timeframe '{tf}', choose from {sorted(SUPPORTED_INTERVALS)}",
        )

    raw = symbol.upper().replace("/", "").replace("-", "")
    instrument_id = f"{market.lower()}:{raw}"
    display = symbol if ("/" in symbol or "." in symbol or "=F" in symbol) else (raw[:-4] + "/USDT" if raw.endswith("USDT") else raw)

    try:
        bars = await fetch_market_klines(symbol, market, interval=tf, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"kline fetch failed: {exc}") from exc

    if len(bars) < 30:
        raise HTTPException(status_code=422, detail="not enough bars for indicators")

    return analyze_bars(
        instrument_id=instrument_id,
        symbol=display,
        timeframe=tf,
        bars=bars,
        market=market,
        rsi_period=rsi_period,
        rsi_os=rsi_oversold,
        rsi_ob=rsi_overbought,
    )


@router.get("/signals/{symbol}")
async def get_signals_for_timeframe(
    symbol: str,
    timeframe: str = Query("15m"),
    limit: int = Query(200, ge=30, le=500),
):
    """Convenience: only active signals (oversold/overbought/macd/bb/volume) for period."""
    report = await get_indicators(symbol, timeframe=timeframe, limit=limit)
    return {
        "instrument_id": report.instrument_id,
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "last_price": report.last_price,
        "summary": report.summary,
        "oscillators": [o.model_dump() for o in report.oscillators],
        "signals": report.active_signals,
    }


@router.get("/indicators/{symbol}/multi")
async def get_multi_timeframe_indicators(
    symbol: str,
    current: str = Query("15m"),
    market: str = Query("crypto"),
    limit: int = Query(200, ge=60, le=500),
):
    """Independent MTF reports. Each timeframe is fetched and recalculated separately."""
    order = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    if current not in order: current = "15m"
    async def one(tf: str):
        bars = await fetch_market_klines(symbol, market, interval=tf, limit=limit)
        if len(bars) < 30: raise HTTPException(status_code=422, detail=f"not enough bars for {tf}")
        raw=symbol.upper().replace("/","").replace("-","")
        display = symbol if ("/" in symbol or "." in symbol or "=F" in symbol) else (raw[:-4] + "/USDT" if raw.endswith("USDT") else raw)
        return analyze_bars(instrument_id=f"{market}:{raw}", symbol=display, timeframe=tf, market=market, bars=bars)
    reports = await asyncio.gather(*(one(tf) for tf in order))
    by_tf={r.timeframe:r.model_dump() for r in reports}; cur=by_tf[current]
    bullish=sum(1 for r in reports if r.trend_sma=="bullish"); bearish=sum(1 for r in reports if r.trend_sma=="bearish")
    if bullish>=3 and bullish>bearish: resonance,resonance_note="多周期偏多","多数周期趋势偏多，高周期对当前多头结构形成背景支持。"
    elif bearish>=3 and bearish>bullish: resonance,resonance_note="多周期偏空","多数周期趋势偏空，高周期对当前空头结构形成背景支持。"
    elif bullish and bearish: resonance,resonance_note="周期分歧","短周期与高周期方向不一致，当前更适合观察反弹/回调是否获得高周期确认。"
    else: resonance,resonance_note="多周期中性","各周期尚未形成明确共振。"
    return {"symbol":symbol,"market":market,"current_timeframe":current,"generated_at":__import__("time").time_ns()//1_000_000,"current":cur,"timeframes":by_tf,"resonance":resonance,"resonance_note":resonance_note,"realtime":True,"realtime_note":"行情更新后重新计算；未收盘K线为临时状态，收盘后才形成确认值。"}
