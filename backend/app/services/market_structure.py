from __future__ import annotations
from typing import Any
from app.data.market_klines import fetch_market_klines
from app.services.mtf_analysis import TIMEFRAMES


def _pivot_points(bars: list[dict[str, Any]], left: int = 2, right: int = 2) -> tuple[list[dict], list[dict]]:
    highs: list[dict] = []
    lows: list[dict] = []
    for i in range(left, len(bars) - right):
        h = float(bars[i]["high"]); lo = float(bars[i]["low"])
        if h >= max(float(bars[j]["high"]) for j in range(i-left, i+right+1)):
            highs.append({"index": i, "price": h, "timestamp": bars[i].get("timestamp")})
        if lo <= min(float(bars[j]["low"]) for j in range(i-left, i+right+1)):
            lows.append({"index": i, "price": lo, "timestamp": bars[i].get("timestamp")})
    return highs[-8:], lows[-8:]


def _labels(points: list[dict]) -> list[dict]:
    out=[]
    for i,p in enumerate(points):
        if i == 0: label="H" if p.get("kind") == "high" else "L"
        else:
            prev=points[i-1]["price"]
            if p.get("kind") == "high": label="HH" if p["price"] > prev else "LH"
            else: label="HL" if p["price"] > prev else "LL"
        q=dict(p); q["label"]=label; out.append(q)
    return out

class MarketStructureService:
    async def build(self, symbol: str, market: str, timeframe: str, limit: int = 200) -> dict[str, Any]:
        tf = timeframe if timeframe in TIMEFRAMES else "15m"
        bars = await fetch_market_klines(symbol, market, interval=tf, limit=limit)
        if len(bars) < 20:
            return {"data_contract":"market-structure-v1","analysis_only":True,"read_only":True,"symbol":symbol,"timeframe":tf,"available":False,"reason":"K线不足"}
        highs,lows=_pivot_points(bars)
        for x in highs: x["kind"]="high"
        for x in lows: x["kind"]="low"
        pivots=sorted(highs+lows,key=lambda x:x["index"])
        pivots=_labels(pivots)
        last=float(bars[-1]["close"])
        # Use completed bars before the live candle for breakout reference levels.
        # This prevents the current candle from moving the boundary away from the
        # price that is testing it, and keeps intrabar state explicitly provisional.
        reference = bars[-61:-1] if len(bars) > 61 else bars[:-1]
        support=min(float(x["low"]) for x in reference[-60:])
        resistance=max(float(x["high"]) for x in reference[-60:])
        prev=float(bars[-2]["close"])
        breakout="none"
        if last > resistance and prev <= resistance: breakout="up_breakout_testing"
        elif last < support and prev >= support: breakout="down_breakout_testing"
        high_points = sorted(highs, key=lambda x: x["index"])
        low_points = sorted(lows, key=lambda x: x["index"])
        high_labels = [x["label"] for x in _labels(high_points)][-3:]
        low_labels = [x["label"] for x in _labels(low_points)][-3:]
        if len(high_labels) >= 2 and len(low_labels) >= 2 and high_labels[-2:] == ["HH", "HH"] and low_labels[-2:] == ["HL", "HL"]:
            trend = "上涨结构"
        elif len(high_labels) >= 2 and len(low_labels) >= 2 and high_labels[-2:] == ["LH", "LH"] and low_labels[-2:] == ["LL", "LL"]:
            trend = "下降结构"
        else:
            trend = "混合/震荡结构"
        return {"data_contract":"market-structure-v1","analysis_only":True,"read_only":True,"symbol":symbol,"market":market,"timeframe":tf,"available":True,"last_price":last,"support":support,"resistance":resistance,"trend":trend,"breakout":breakout,"pivots":pivots,"closed_candle_rule":"突破/跌破在未收盘K线阶段只标记为测试；对应周期收盘后才确认。","note":"结构由当前周期真实K线局部高低点计算；HH/HL/LH/LL用于描述结构，不单独构成买卖信号。"}
