from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.data.market_klines import fetch_market_klines
from app.quant.indicators.analysis import analyze_bars
from app.quant.probability import research_probability


@dataclass
class _Previous:
    timestamp: float
    price: float | None
    trend: str
    rsi: float | None
    macd_hist: float | None
    structure: str
    overbought: int
    oversold: int


class HumanAnalysisReportService:
    """Turns the quantitative snapshot into a concise, explainable market report.

    This is deliberately deterministic: the report explains measurable conditions
    and never pretends that an indicator alone proves a future move.
    """

    def __init__(self) -> None:
        self._previous: dict[tuple[str, str, str], _Previous] = {}

    async def build(self, symbol: str, market: str, timeframe: str, limit: int = 250) -> dict[str, Any]:
        bars = await fetch_market_klines(symbol, market, interval=timeframe, limit=limit)
        if len(bars) < 30:
            raise ValueError("not enough bars for analysis report")
        raw = symbol.upper().replace("/", "").replace("-", "")
        display = symbol if ("/" in symbol or "." in symbol or "=F" in symbol) else (raw[:-4] + "/USDT" if raw.endswith("USDT") else raw)
        report = analyze_bars(
            instrument_id=f"{market}:{raw}", symbol=display, timeframe=timeframe,
            market=market, bars=bars,
        )
        probability = research_probability(bars)
        key = (market.lower(), display.upper(), timeframe)
        previous = self._previous.get(key)
        change = self._change(previous, report)
        self._previous[key] = _Previous(
            time.time(), report.last_price, report.trend_sma, report.rsi_14,
            report.macd_hist, report.structure.state, report.overbought_count,
            report.oversold_count,
        )
        return {
            "symbol": report.symbol,
            "market": market,
            "timeframe": timeframe,
            "generated_at": int(time.time() * 1000),
            "last_price": report.last_price,
            "last_close_time": report.last_close_time,
            "trend": report.trend_label,
            "trend_strength": report.trend_strength,
            "structure": report.structure.model_dump(),
            "overbought": {
                "count": report.overbought_count,
                "score": report.overbought_score,
                "interpretation": self._oscillator_note(report, "overbought"),
            },
            "oversold": {
                "count": report.oversold_count,
                "score": report.oversold_score,
                "interpretation": self._oscillator_note(report, "oversold"),
            },
            "summary": report.summary,
            "narrative": report.narrative,
            "change": change,
            "indicator_report": report.model_dump(),
            "data_quality": report.data_quality,
            "realtime": {
                "is_live_snapshot": True,
                "unclosed_candle_note": report.realtime_note,
                "refresh_policy": "客户端刷新行情后重新计算全部当前周期指标；未收盘K线只视为临时状态。",
            },
            "market_context": self._market_context(market),
            "probability": {"long": probability.long_probability, "short": probability.short_probability, "status": probability.status, "method": probability.method, "samples": probability.samples, "train_samples": probability.train_samples, "calibration_samples": probability.calibration_samples, "oos_samples": probability.oos_samples, "brier_long": probability.brier_long, "brier_short": probability.brier_short, "note": probability.note},
        }

    @staticmethod
    def _oscillator_note(report, side: str) -> str:
        names = [x.name for x in report.oscillators if x.state == side]
        if not names:
            return "目前没有形成明显的多指标共振。"
        if side == "overbought":
            return f"{', '.join(names)}同时偏热。上涨趋势中这代表短线偏热，不等于已经确认反转；应继续观察价格结构、MACD动能和支撑。"
        return f"{', '.join(names)}同时偏弱。下跌趋势中这代表短线偏弱，不等于已经确认反转；应观察止跌结构、MACD动能和阻力。"

    @staticmethod
    def _change(previous: _Previous | None, report) -> dict[str, Any]:
        if previous is None:
            return {"available": False, "text": "首次生成该周期报告，等待下一次刷新后比较变化。", "items": []}
        items: list[str] = []
        if previous.trend != report.trend_sma:
            items.append(f"趋势由 {previous.trend} 变为 {report.trend_sma}")
        if previous.structure != report.structure.state:
            items.append(f"结构由 {previous.structure} 变为 {report.structure.state}")
        if previous.rsi is not None and report.rsi_14 is not None and abs(report.rsi_14 - previous.rsi) >= 3:
            items.append(f"RSI {previous.rsi:.1f} → {report.rsi_14:.1f}")
        if previous.macd_hist is not None and report.macd_hist is not None:
            if (previous.macd_hist >= 0) != (report.macd_hist >= 0):
                items.append("MACD柱由正转负或由负转正")
            elif abs(report.macd_hist - previous.macd_hist) > max(abs(previous.macd_hist) * .25, 1e-12):
                items.append("MACD动能出现明显变化")
        if previous.overbought != report.overbought_count:
            items.append(f"超买指标数量 {previous.overbought} → {report.overbought_count}")
        if previous.oversold != report.oversold_count:
            items.append(f"超卖指标数量 {previous.oversold} → {report.oversold_count}")
        if not items:
            items.append("本次刷新未发现主要分析状态切换。")
        return {"available": True, "text": "；".join(items), "items": items, "previous_at": int(previous.timestamp * 1000)}

    @staticmethod
    def _market_context(market: str) -> dict[str, Any]:
        m = market.lower()
        if m == "crypto":
            return {
                "category": "加密货币",
                "additional_data": ["现货/永续市场结构", "资金费率", "持仓量", "多空比", "清算", "盘口失衡"],
                "status": "技术分析已接入；衍生品字段按配置的数据源提供，未接入的数据明确标记缺失。",
            }
        if m in {"us", "hk"}:
            return {
                "category": "股票",
                "additional_data": ["财务报表", "估值", "盈利能力", "股息", "行业/板块", "公司公告/新闻"],
                "status": "行情技术分析可用；基本面字段需要配置相应数据源，不使用虚构数据。",
            }
        if m == "commodities":
            return {
                "category": "大宗商品/期货",
                "additional_data": ["合约到期", "持仓量", "期限结构", "库存", "基差"],
                "status": "技术分析可用；合约与库存等字段按数据源能力提供。",
            }
        return {"category": market, "additional_data": [], "status": "未定义市场扩展字段。"}
