from __future__ import annotations
import asyncio
from typing import Any
from app.data.market_klines import fetch_market_klines
from app.quant.indicators.analysis import analyze_bars

TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]

class MTFAnalysisService:
    async def build(self, symbol: str, market: str, current: str = "15m", limit: int = 200) -> dict[str, Any]:
        current = current if current in TIMEFRAMES else "15m"
        async def one(tf: str):
            bars = await fetch_market_klines(symbol, market, interval=tf, limit=limit)
            if len(bars) < 30:
                return tf, None
            raw = symbol.upper().replace("/", "").replace("-", "")
            display = symbol if ("/" in symbol or "." in symbol or "=F" in symbol) else (raw[:-4] + "/USDT" if raw.endswith("USDT") else raw)
            r = analyze_bars(instrument_id=f"{market}:{raw}", symbol=display, timeframe=tf, market=market, bars=bars)
            return tf, r.model_dump()
        pairs = await asyncio.gather(*(one(tf) for tf in TIMEFRAMES))
        reports = {tf: value for tf, value in pairs if value is not None}
        bullish = sum(1 for x in reports.values() if x.get("trend_sma") == "bullish")
        bearish = sum(1 for x in reports.values() if x.get("trend_sma") == "bearish")
        if bullish >= 3 and bullish > bearish:
            resonance = "多周期偏多"
            note = "多数已取得周期趋势偏多；高周期仍需结合结构与收盘确认。"
        elif bearish >= 3 and bearish > bullish:
            resonance = "多周期偏空"
            note = "多数已取得周期趋势偏空；短周期反弹不等于高周期反转。"
        elif bullish and bearish:
            resonance = "周期分歧"
            note = "不同周期方向不一致，应分别观察高周期背景与当前周期触发条件。"
        else:
            resonance = "多周期中性"
            note = "当前已取得周期尚未形成明确方向共振。"
        return {
            "data_contract": "mtf-analysis-v1", "analysis_only": True, "read_only": True,
            "symbol": symbol, "market": market, "current_timeframe": current,
            "generated_at": __import__("time").time_ns() // 1_000_000,
            "timeframes": reports, "resonance": resonance, "resonance_note": note,
            "missing_timeframes": [tf for tf in TIMEFRAMES if tf not in reports],
            "closed_candle_rule": "未收盘K线仅作为实时观察；结构突破/跌破需等待对应周期收盘确认。",
        }
