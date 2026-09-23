from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class MarketRegime:
    name: str
    confidence: float
    trend_score: float
    volatility_score: float
    liquidity_score: float
    reasons: list[str]

class RegimeEngine:
    def classify(self, features: dict[str, float | None]) -> MarketRegime:
        adx=float(features.get('adx_14') or 0); atr=float(features.get('atr_pct') or 0)
        bb=float(features.get('bb_width') or 0); vr=float(features.get('volume_ratio') or 1)
        trend=min(1.0, adx/50.0); vol=min(1.0, atr/5.0 if atr else bb/0.2)
        liq=min(1.0, max(0.0, vr/2.0))
        reasons=[]
        if trend>.6: name='trending'; reasons.append('ADX indicates directional strength')
        elif vol>.7: name='high_volatility'; reasons.append('volatility regime is elevated')
        else: name='ranging'; reasons.append('trend strength is limited')
        if liq<.3: name='low_liquidity'; reasons.append('volume/liquidity is weak')
        conf=round(max(.2, min(1.0, .45*trend+.35*vol+.20*liq)),3)
        return MarketRegime(name,conf,round(trend,3),round(vol,3),round(liq,3),reasons)
