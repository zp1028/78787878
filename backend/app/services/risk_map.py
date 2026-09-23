from __future__ import annotations
from typing import Any
from app.services.market_structure import MarketStructureService
from app.services.mtf_analysis import TIMEFRAMES


class RiskMapService:
    """Read-only, multi-timeframe market risk map.

    Every level is derived from the same market-structure service used by the
    detail page. It does not create orders, positions, or account state.
    """
    async def build(self, symbol: str, market: str, current_timeframe: str = "15m", limit: int = 200) -> dict[str, Any]:
        tf = current_timeframe if current_timeframe in TIMEFRAMES else "15m"
        service = MarketStructureService()
        levels: dict[str, Any] = {}
        for item_tf in TIMEFRAMES:
            levels[item_tf] = await service.build(symbol, market, item_tf, min(limit, 200))

        available = {k: v for k, v in levels.items() if v.get("available")}
        supports = [(k, v.get("support")) for k, v in available.items() if isinstance(v.get("support"), (int, float))]
        resistances = [(k, v.get("resistance")) for k, v in available.items() if isinstance(v.get("resistance"), (int, float))]
        current = levels.get(tf, {})
        current_price = current.get("last_price")

        def distance(level: float | None) -> float | None:
            if not isinstance(level, (int, float)) or not isinstance(current_price, (int, float)) or current_price == 0:
                return None
            return (level - current_price) / current_price * 100

        return {
            "data_contract": "risk-map-v1",
            "analysis_only": True,
            "read_only": True,
            "symbol": symbol,
            "market": market,
            "current_timeframe": tf,
            "last_price": current_price,
            "timeframes": levels,
            "nearest_support": min((x for _, x in supports if x <= current_price), default=None) if isinstance(current_price, (int, float)) else None,
            "nearest_resistance": min((x for _, x in resistances if x >= current_price), default=None) if isinstance(current_price, (int, float)) else None,
            "support_distance_pct": distance(current.get("support")),
            "resistance_distance_pct": distance(current.get("resistance")),
            "support_sources": [k for k, _ in supports],
            "resistance_sources": [k for k, _ in resistances],
            "rule": "各周期支撑/阻力均来自已完成K线结构参考；盘中突破只标记为测试，周期收盘后才可确认。",
        }
