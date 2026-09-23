from __future__ import annotations
from typing import Any


def build_holding_observation(*, price: float, support: float | None, resistance: float | None,
                              trend: str, rsi: float | None, macd_hist: float | None,
                              adx: float | None, side: str | None = None,
                              entry_price: float | None = None) -> dict[str, Any]:
    """Read-only holding observation. It never reads or mutates a broker/account.

    `side`/`entry_price` are optional user-supplied context only. Without them the
    result remains a market-risk observation rather than pretending an account exists.
    """
    side = side if side in {"long", "short"} else None
    pnl_pct = None
    if side and entry_price and entry_price > 0:
        pnl_pct = ((price - entry_price) / entry_price * 100) * (1 if side == "long" else -1)

    support_dist = ((price - support) / price * 100) if support is not None and price else None
    resistance_dist = ((resistance - price) / price * 100) if resistance is not None and price else None

    risk = "正常观察"
    nodes: list[str] = []
    if side == "long":
        if support is not None and price <= support:
            risk = "高风险节点"
            nodes.append("价格已触及/跌破结构支撑，需等待收盘确认是否失守")
        elif resistance is not None and price >= resistance:
            risk = "关键确认节点"
            nodes.append("价格正在测试结构阻力，重点观察放量与收盘确认")
        if macd_hist is not None and macd_hist < 0:
            nodes.append("MACD 动能转弱，关注多头动能衰减")
        if rsi is not None and rsi >= 70:
            nodes.append("RSI 高位，追涨风险增加；持有观察重点转向回踩")
    elif side == "short":
        if resistance is not None and price >= resistance:
            risk = "高风险节点"
            nodes.append("价格已触及/突破结构阻力，需等待收盘确认是否有效")
        elif support is not None and price <= support:
            risk = "关键确认节点"
            nodes.append("价格正在测试结构支撑，重点观察放量与收盘确认")
        if macd_hist is not None and macd_hist > 0:
            nodes.append("MACD 动能转强，关注空头动能衰减")
        if rsi is not None and rsi <= 30:
            nodes.append("RSI 低位，空头继续扩张需等待反弹失败确认")
    else:
        if support is not None and price <= support or resistance is not None and price >= resistance:
            risk = "关键观察节点"
        nodes.append("未提供实际持仓上下文；当前仅展示市场结构风险节点")

    if not nodes:
        nodes.append("当前未触发明显结构风险节点，继续观察趋势、支撑/阻力与动能变化")

    return {
        "analysis_only": True,
        "read_only": True,
        "context_source": "user_supplied" if side else "market_only",
        "side": side,
        "entry_price": entry_price,
        "unrealized_change_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
        "risk_level": risk,
        "support_distance_pct": round(support_dist, 4) if support_dist is not None else None,
        "resistance_distance_pct": round(resistance_dist, 4) if resistance_dist is not None else None,
        "invalidation": (
            "结构支撑有效失守并经周期收盘确认" if side == "long" else
            "结构阻力有效突破并经周期收盘确认" if side == "short" else
            "任一结构边界经周期收盘确认后，重新评估情景"
        ),
        "watchpoints": nodes,
        "trend": trend,
        "adx": adx,
        "closed_candle_rule": "盘中触及仅视为测试；结构失效/突破需等待对应周期收盘确认。",
    }
