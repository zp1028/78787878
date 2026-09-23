"""Single-instrument trading advice from latest analysis + market state.

Produces actionable long/short entry zones, stops, targets and position
guidance. This is still a *proposal* — RiskEngine must approve before any order.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ai.models import AnalysisResult
from app.quant.features.engine import FeatureSnapshot
from app.risk.models import RiskLimits


class EntryPlan(BaseModel):
    direction: Literal["long", "short", "wait"]
    conviction: float = Field(ge=0.0, le=1.0)
    score_type: str = "rule_evidence_score"
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    suggested_entry: float | None = None
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    risk_reward: float | None = None
    position_pct: float | None = None  # suggested fraction of equity
    rationale: list[str] = Field(default_factory=list)


class PositionAdvice(BaseModel):
    action: Literal["open", "add", "hold", "reduce", "close", "wait"]
    side: Literal["long", "short", "flat"] | None = None
    note: str = ""
    max_position_pct: float | None = None


class TradingAdvice(BaseModel):
    instrument_id: str
    symbol: str
    generated_at: int
    last_price: float | None
    market_bias: str  # bullish | bearish | neutral | mixed
    analysis_id: str | None = None
    # Always expose BOTH directions so the user can compare long/short setups.
    long_entry: EntryPlan
    short_entry: EntryPlan
    # Backward-compatible selected setup: whichever side has stronger conviction, or wait.
    entry: EntryPlan
    position: PositionAdvice
    risk_notes: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "仅用于市场研究与情景分析，不构成投资建议；不提供模拟或下单功能。"
    )
    technical_snapshot: dict[str, Any] = Field(default_factory=dict)


def build_trading_advice(
    *,
    instrument_id: str,
    symbol: str,
    analysis: AnalysisResult | None,
    snapshot: FeatureSnapshot | None,
    last_price: float | None = None,
    has_open_long: bool = False,
    has_open_short: bool = False,
    risk_limits: RiskLimits | None = None,
) -> TradingAdvice:
    limits = risk_limits or RiskLimits()
    now = int(time.time() * 1000)

    price = last_price
    tech: dict[str, Any] = {}
    if snapshot:
        tech = dict(snapshot.features)
        if price is None:
            price = snapshot.features.get("close")

    trend = analysis.trend if analysis else "neutral"
    conf = analysis.confidence if analysis else 0.0
    support = list(analysis.support) if analysis else []
    resistance = list(analysis.resistance) if analysis else []

    # enrich support/resistance from bollinger if needed
    if snapshot:
        bl = snapshot.features.get("bb_lower")
        bu = snapshot.features.get("bb_upper")
        mid = snapshot.features.get("bb_mid")
        if bl and bl not in support:
            support.append(float(bl))
        if mid and mid not in support:
            support.append(float(mid))
        if mid and mid not in resistance:
            resistance.append(float(mid))
        if bu and bu not in resistance:
            resistance.append(float(bu))

    support = sorted({round(x, 6) for x in support if x})
    resistance = sorted({round(x, 6) for x in resistance if x})

    rsi = tech.get("rsi_14")
    macd_h = tech.get("macd_hist")
    bb_pct = tech.get("bb_pct")

    def build_plan(side: Literal["long", "short"]) -> EntryPlan:
        rationale: list[str] = []
        side_direction = side
        # This is an explainable rule-evidence score, not a probability or
        # calibrated confidence. Every point must come from an observed field.
        evidence_total = 0
        supporting = 0

        if trend in {"bullish", "bearish", "neutral", "mixed"}:
            evidence_total += 1
            trend_matches = (side == "long" and trend == "bullish") or (side == "short" and trend == "bearish")
            if trend_matches:
                supporting += 1
                rationale.append(f"综合趋势与{('多' if side == 'long' else '空')}单方向一致")
            elif trend in {"bullish", "bearish"}:
                rationale.append(f"当前趋势与{('多' if side == 'long' else '空')}单不一致，保留为反向观察情景")
            else:
                rationale.append("趋势中性/混合，等待结构确认")

        if rsi is not None:
            evidence_total += 1
            favorable = (side == "long" and rsi < 30) or (side == "short" and rsi > 70)
            unfavorable = (side == "long" and rsi > 70) or (side == "short" and rsi < 30)
            if favorable:
                supporting += 1
                rationale.append(f"RSI={rsi:.1f} 为{('超卖' if side == 'long' else '超买')}，对应情景条件增强")
            elif unfavorable:
                rationale.append(f"RSI={rsi:.1f} 对当前{('多' if side == 'long' else '空')}单不利")
            else:
                rationale.append(f"RSI={rsi:.1f} 未形成方向性极值")

        if macd_h is not None:
            evidence_total += 1
            favorable = (side == "long" and macd_h > 0) or (side == "short" and macd_h < 0)
            if favorable:
                supporting += 1
                rationale.append(f"MACD柱方向与{('多' if side == 'long' else '空')}单一致")
            else:
                rationale.append("MACD动量暂未完全配合")

        if bb_pct is not None:
            evidence_total += 1
            favorable = (side == "long" and bb_pct < 0.15) or (side == "short" and bb_pct > 0.85)
            if favorable:
                supporting += 1
                rationale.append(f"价格处于布林带有利观察区域 (pct={bb_pct:.2f})")
            else:
                rationale.append(f"布林位置={bb_pct:.2f}，未形成该方向的极端位置优势")

        if analysis:
            cases = analysis.bull_case if side == "long" else analysis.bear_case
            rationale.extend(cases[:3])

        conviction = (supporting / evidence_total) if evidence_total else 0.0
        entry_low = entry_high = suggested = stop = tp1 = tp2 = None
        rr = None
        pos_pct = None

        if price and price > 0:
            if side == "long":
                nearest_sup = max([x for x in support if x <= price], default=price * 0.995)
                entry_low = round(min(nearest_sup, price * 0.998), 6)
                entry_high = round(price, 6)
                suggested = round((entry_low + entry_high) / 2, 6)
                stop = round(min(entry_low * 0.992, price * 0.985), 6)
                min_stop = price * (1 - limits.min_stop_distance_pct)
                if stop > min_stop:
                    stop = round(min_stop, 6)
                risk = suggested - stop
                tp1 = round(suggested + risk * 1.5, 6)
                tp2 = round(suggested + risk * 2.5, 6)
                above = [x for x in resistance if x > suggested]
                if above:
                    tp1 = min(tp1, above[0])
            else:
                nearest_res = min([x for x in resistance if x >= price], default=price * 1.005)
                entry_low = round(price, 6)
                entry_high = round(max(nearest_res, price * 1.002), 6)
                suggested = round((entry_low + entry_high) / 2, 6)
                stop = round(max(entry_high * 1.008, price * 1.015), 6)
                max_tight = price * (1 + limits.min_stop_distance_pct)
                if stop < max_tight:
                    stop = round(max_tight, 6)
                risk = stop - suggested
                tp1 = round(suggested - risk * 1.5, 6)
                tp2 = round(suggested - risk * 2.5, 6)
                below = [x for x in support if x < suggested]
                if below:
                    tp1 = max(tp1, below[-1])

            if suggested and stop and suggested != stop:
                risk = abs(suggested - stop)
                reward = abs((tp1 or suggested) - suggested)
                rr = round(reward / risk, 2) if risk > 0 else None

            base = limits.max_position_pct * 0.5
            pos_pct = round(min(limits.max_position_pct, base * (0.5 + conviction)), 4)
            if conviction < 0.4:
                pos_pct = round(pos_pct * 0.5, 4)
                rationale.append("置信度偏低，建议仅观察或显著降低风险暴露")

        return EntryPlan(
            direction=side_direction,
            conviction=round(conviction, 3),
            entry_zone_low=entry_low,
            entry_zone_high=entry_high,
            suggested_entry=suggested,
            stop_loss=stop,
            take_profit_1=tp1,
            take_profit_2=tp2,
            risk_reward=rr,
            position_pct=pos_pct,
            rationale=rationale[:8],
            score_type="rule_evidence_score",
        )

    long_entry = build_plan("long")
    short_entry = build_plan("short")
    # Selected setup is informational only; both plans remain visible.
    if trend == "mixed":
        direction: Literal["long", "short", "wait"] = "wait"
        selected = EntryPlan(direction="wait", conviction=max(long_entry.conviction, short_entry.conviction), rationale=["当前多空依据并存，综合方向保持观望；同时保留多单/空单情景供比较"])
    elif long_entry.conviction >= short_entry.conviction and long_entry.conviction >= 0.4:
        direction = "long"
        selected = long_entry
    elif short_entry.conviction > long_entry.conviction and short_entry.conviction >= 0.4:
        direction = "short"
        selected = short_entry
    else:
        direction = "wait"
        selected = EntryPlan(direction="wait", conviction=max(long_entry.conviction, short_entry.conviction), rationale=["多空条件均未达到观察阈值，等待确认"])

    # position management advice
    if has_open_long:
        if direction == "short":
            pos_adv = PositionAdvice(
                action="reduce",
                side="long",
                note="出现空头信号，建议重点观察多单减仓/止盈条件",
                max_position_pct=selected.position_pct,
            )
        elif direction == "long":
            pos_adv = PositionAdvice(
                action="hold" if selected.conviction < 0.7 else "add",
                side="long",
                note="趋势仍偏多，可持有；高置信时可轻仓加仓",
                max_position_pct=selected.position_pct,
            )
        else:
            pos_adv = PositionAdvice(action="hold", side="long", note="方向不明，持仓观望")
    elif has_open_short:
        if direction == "long":
            pos_adv = PositionAdvice(
                action="reduce",
                side="short",
                note="出现多头信号，建议重点观察空单减仓/平仓条件",
                max_position_pct=selected.position_pct,
            )
        elif direction == "short":
            pos_adv = PositionAdvice(
                action="hold" if selected.conviction < 0.7 else "add",
                side="short",
                note="趋势仍偏空，可持有；高置信时可轻仓加仓",
                max_position_pct=selected.position_pct,
            )
        else:
            pos_adv = PositionAdvice(action="hold", side="short", note="方向不明，持仓观望")
    else:
        if direction == "wait":
            pos_adv = PositionAdvice(action="wait", side="flat", note="暂不建议开仓")
        else:
            pos_adv = PositionAdvice(
                action="open",
                side=direction,
                note=f"可按建议区间观察{('多' if direction == 'long' else '空')}单情景，先等待确认",
                max_position_pct=selected.position_pct,
            )

    risk_notes = [
        f"单标的上限 {limits.max_position_pct:.0%}",
        f"最大杠杆 {limits.max_leverage}x",
        f"止损距离建议 ≥ {limits.min_stop_distance_pct:.1%}",
    ]
    if long_entry.risk_reward is not None and long_entry.risk_reward < 1.0:
        risk_notes.append(f"多单当前盈亏比约 {long_entry.risk_reward}，偏低")
    if short_entry.risk_reward is not None and short_entry.risk_reward < 1.0:
        risk_notes.append(f"空单当前盈亏比约 {short_entry.risk_reward}，偏低")

    return TradingAdvice(
        instrument_id=instrument_id,
        symbol=symbol,
        generated_at=now,
        last_price=price,
        market_bias=trend,
        analysis_id=analysis.analysis_id if analysis else None,
        long_entry=long_entry,
        short_entry=short_entry,
        entry=selected,
        position=pos_adv,
        risk_notes=risk_notes,
        technical_snapshot={
            k: tech.get(k)
            for k in ("close", "rsi_14", "macd", "macd_hist", "bb_pct", "sma_20", "volume_ratio")
            if tech.get(k) is not None
        },
    )


def build_indicator_only_advice(report, holding_side: str|None=None) -> TradingAdvice:
    """Analysis-only advice for any market provider; never reads an account or broker."""
    p=report.last_price; trend=report.trend_sma; rsi=report.rsi_14; mh=report.macd_hist; adxv=report.adx_14
    support=report.structure.support; resistance=report.structure.resistance
    def plan(side):
        reasons=[]; total=0; supporting=0
        if trend in {"bullish", "bearish"}:
            total += 1
            if (side=="long" and trend=="bullish") or (side=="short" and trend=="bearish"):
                supporting += 1; reasons.append("价格均线结构与该方向一致")
            else:
                reasons.append("当前均线结构与该方向不一致")
        if mh is not None:
            total += 1
            if (side=="long" and mh>0) or (side=="short" and mh<0):
                supporting += 1; reasons.append("MACD动能与该方向一致")
            else: reasons.append("MACD动能暂未配合")
        if rsi is not None:
            total += 1
            if (side=="long" and rsi<35) or (side=="short" and rsi>70):
                supporting += 1; reasons.append("RSI进入该方向值得观察的区域")
            elif (side=="long" and rsi>70) or (side=="short" and rsi<30):
                reasons.append("RSI处于对该方向不利的极值")
            else: reasons.append("RSI未形成明显方向性极值")
        if adxv is not None: reasons.append(f"ADX={adxv:.1f}，仅用于描述趋势强度")
        score=(supporting/total) if total else 0.0
        if side=="long":
            entry=max([x for x in support if p and x<=p],default=p) if p else None
            stop=entry*0.985 if entry else None; tp=next((x for x in resistance if entry and x>entry),entry*1.03 if entry else None)
        else:
            entry=min([x for x in resistance if p and x>=p],default=p) if p else None
            stop=entry*1.015 if entry else None; tp=next((x for x in reversed(support) if entry and x<entry),entry*.97 if entry else None)
        return EntryPlan(direction=side,conviction=round(score,3),score_type="rule_evidence_score",entry_zone_low=entry*.998 if entry else None,entry_zone_high=entry*1.002 if entry else None,suggested_entry=entry,stop_loss=stop,take_profit_1=tp,take_profit_2=(tp*1.02 if side=="long" and tp else tp*.98 if tp else None),risk_reward=(abs(tp-entry)/abs(entry-stop) if p and entry and stop and tp and entry!=stop else None),position_pct=None,rationale=reasons[:8])
    lp=plan("long"); sp=plan("short")
    if holding_side=="long": action="hold" if lp.conviction>=.45 else "reduce"; side="long"; note="按当前指标重新评估多头持仓条件，重点观察支撑与趋势是否破坏。"
    elif holding_side=="short": action="hold" if sp.conviction>=.45 else "reduce"; side="short"; note="按当前指标重新评估空头持仓条件，重点观察阻力与趋势是否破坏。"
    elif trend=="bullish": action="hold"; side="long"; note="当前趋势偏多；持仓观察重点为支撑失守、动能衰减和超买后的回落。"
    elif trend=="bearish": action="hold"; side="short"; note="当前趋势偏空；持仓观察重点为阻力突破、动能修复和超卖后的反弹。"
    else: action="wait"; side="flat"; note="当前周期趋势混合，持仓方向需要等待结构确认。"
    return TradingAdvice(instrument_id=report.instrument_id,symbol=report.symbol,generated_at=int(time.time()*1000),last_price=p,market_bias="bullish" if trend=="bullish" else "bearish" if trend=="bearish" else "neutral",long_entry=lp,short_entry=sp,entry=lp if lp.conviction>=sp.conviction else sp,position=PositionAdvice(action=action,side=side,note=note),risk_notes=["这是分析情景，不是实际下单指令。","未使用交易账户或持仓数据。"],technical_snapshot=report.model_dump())
