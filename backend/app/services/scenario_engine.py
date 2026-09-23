from __future__ import annotations
from typing import Any
from app.data.market_klines import fetch_market_klines
from app.quant.indicators.analysis import analyze_bars
from app.services.market_structure import MarketStructureService
from app.services.mtf_analysis import MTFAnalysisService, TIMEFRAMES
from app.services.holding_observation import build_holding_observation

class ScenarioEngine:
    """Builds conditional bull/base/bear research scenarios from current evidence.

    It deliberately does not manufacture probabilities. A scenario is a conditional
    path with observable trigger/invalidation conditions, not a prediction.
    """
    async def build(self, symbol: str, market: str, timeframe: str = "15m", limit: int = 200, holding_side: str | None = None, entry_price: float | None = None) -> dict[str, Any]:
        tf = timeframe if timeframe in TIMEFRAMES else "15m"
        bars = await fetch_market_klines(symbol, market, interval=tf, limit=limit)
        if len(bars) < 30:
            return {"data_contract":"scenario-analysis-v1","analysis_only":True,"read_only":True,
                    "available":False,"symbol":symbol,"market":market,"timeframe":tf,
                    "reason":"K线不足，无法构建条件情景。","scenarios":[]}
        report = analyze_bars(instrument_id=f"{market}:{symbol.upper().replace('/','').replace('-','')}", symbol=symbol, timeframe=tf, market=market, bars=bars)
        structure = await MarketStructureService().build(symbol, market, tf, limit)
        mtf = await MTFAnalysisService().build(symbol, market, tf, min(limit, 160))
        f = report.model_dump()
        price = float(bars[-1]["close"])
        support = structure.get("support")
        resistance = structure.get("resistance")
        trend = f.get("trend_sma", "unknown")
        rsi = f.get("rsi_14")
        macd = f.get("macd_hist")
        adx = f.get("adx_14")
        volume_ratio = f.get("volume_ratio")
        mtf_res = mtf.get("resonance", "多周期中性")

        def fmt(x):
            return f"{x:.8g}" if isinstance(x, (int,float)) else "—"
        def levels(items): return [x for x in items if x is not None]

        bull_triggers = levels([resistance])
        bear_triggers = levels([support])
        bull_confirm = f"价格在 {fmt(resistance)} 上方完成 {tf} 收盘确认" if resistance else f"{tf} 收盘创出新的结构高点"
        bear_confirm = f"价格在 {fmt(support)} 下方完成 {tf} 收盘确认" if support else f"{tf} 收盘创出新的结构低点"
        bull_invalid = f"重新跌回结构阻力 {fmt(resistance)} 下方并失守近期支撑" if resistance else "跌破最近结构低点"
        bear_invalid = f"重新站回结构支撑 {fmt(support)} 上方并突破近期阻力" if support else "突破最近结构高点"
        base_range = f"价格继续在 {fmt(support)}–{fmt(resistance)} 之间运行" if support is not None and resistance is not None else "价格继续在近期结构区间内运行"

        bull_reasons = []
        bear_reasons = []
        if trend == "bullish": bull_reasons.append("当前周期趋势偏多")
        elif trend == "bearish": bear_reasons.append("当前周期趋势偏空")
        if isinstance(rsi,(int,float)):
            if rsi >= 70: bull_reasons.append("RSI 已高位，趋势仍强但追涨需等待回踩确认")
            elif rsi <= 30: bear_reasons.append("RSI 已低位，空头延续需等待反弹失败确认")
        if isinstance(macd,(int,float)):
            (bull_reasons if macd >= 0 else bear_reasons).append("MACD 动能位于零轴%s" % ("上方" if macd >= 0 else "下方"))
        if isinstance(adx,(int,float)) and adx >= 25: bull_reasons.append("ADX 显示当前趋势具有一定强度") if trend == "bullish" else bear_reasons.append("ADX 显示当前趋势具有一定强度") if trend == "bearish" else None
        if isinstance(volume_ratio,(int,float)) and volume_ratio >= 1.5:
            bull_reasons.append("成交量高于近期均值，突破若伴随放量更有验证价值")
            bear_reasons.append("成交量高于近期均值，跌破若伴随放量更有验证价值")

        holding = build_holding_observation(price=price, support=support, resistance=resistance, trend=trend, rsi=rsi, macd_hist=macd, adx=adx, side=holding_side, entry_price=entry_price)

        scenarios = [
            {"name":"bull","label":"多头情景","status":"conditional","trigger":bull_confirm,
             "observation_zone":fmt(resistance) if resistance else "近期结构高点",
             "invalidation":bull_invalid,
             "targets":"向下一阻力区/近期波段高点推进；目标随新K线动态重算",
             "reasons":bull_reasons or ["当前证据尚不足以确认多头路径，等待结构突破与收盘确认"],
             "probability":None},
            {"name":"base","label":"中性/震荡情景","status":"active_observation",
             "trigger":base_range,
             "observation_zone":f"{fmt(support)}–{fmt(resistance)}" if support is not None and resistance is not None else "近期结构区间",
             "invalidation":"有效突破任一侧结构边界后转入对应方向情景",
             "targets":"区间内部继续观察支撑/阻力反应",
             "reasons":[f"当前多周期状态：{mtf_res}","未出现经过收盘确认的结构性突破时，不把盘中波动当作趋势反转"],
             "probability":None},
            {"name":"bear","label":"空头情景","status":"conditional","trigger":bear_confirm,
             "observation_zone":fmt(support) if support else "近期结构低点",
             "invalidation":bear_invalid,
             "targets":"向下一支撑区/近期波段低点推进；目标随新K线动态重算",
             "reasons":bear_reasons or ["当前证据尚不足以确认空头路径，等待结构跌破与收盘确认"],
             "probability":None},
        ]
        return {"data_contract":"scenario-analysis-v1","analysis_only":True,"read_only":True,
                "available":True,"symbol":symbol,"market":market,"timeframe":tf,
                "generated_at":__import__('time').time_ns()//1_000_000,
                "data_timestamp":int(bars[-1].get("close_time") or bars[-1].get("timestamp") or 0),
                "last_price":price,"trend":trend,"rsi":rsi,"macd_hist":macd,"adx":adx,
                "volume_ratio":volume_ratio,"market_structure":structure,"mtf_resonance":mtf_res,
                "scenarios":scenarios,
                "holding_observation": holding,
                "probability_rule":"本接口不输出未经历史校准的概率；probability=null表示条件情景而非预测概率。",
                "closed_candle_rule":f"{tf} 突破/跌破必须等待该周期收盘确认；盘中仅标记为测试。"}
