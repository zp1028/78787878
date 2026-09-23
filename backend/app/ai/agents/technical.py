"""Technical agent — rule-based structured view from FeatureSnapshot + signals."""

from __future__ import annotations

from typing import Any

from app.ai.models import EvidenceItem
from app.quant.features.engine import FeatureSnapshot
from app.core.events import SignalEvent


def analyze_technical(
    snap: FeatureSnapshot | None,
    signals: list[SignalEvent],
) -> tuple[dict[str, Any], list[str], list[str], list[EvidenceItem], str, float]:
    """
    Returns:
        technical_dict, bull_points, bear_points, evidence, trend, confidence
    """
    technical: dict[str, Any] = {}
    bull: list[str] = []
    bear: list[str] = []
    evidence: list[EvidenceItem] = []
    trend = "neutral"
    conf = 0.0

    if snap is None:
        return technical, bull, bear, evidence, trend, conf

    f = snap.features
    observed_keys = ("close", "rsi_14", "macd_hist", "bb_pct", "sma_20", "sma_50", "volume_ratio")
    observed = sum(1 for key in observed_keys if f.get(key) is not None)
    data_confidence = observed / len(observed_keys)
    conf = data_confidence
    technical = {
        "close": f.get("close"),
        "rsi_14": f.get("rsi_14"),
        "macd": f.get("macd"),
        "macd_hist": f.get("macd_hist"),
        "bb_pct": f.get("bb_pct"),
        "sma_20": f.get("sma_20"),
        "sma_50": f.get("sma_50"),
        "volume_ratio": f.get("volume_ratio"),
    }

    rsi = f.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            bull.append(f"RSI(14)={rsi:.1f} 超卖区域，存在反弹可能")
            evidence.append(
                EvidenceItem(
                    source="technical",
                    agent="TechnicalAgent",
                    summary=f"RSI oversold at {rsi:.1f}",
                    confidence=data_confidence,
                    raw={"rsi_14": rsi},
                )
            )
            trend = "bullish"
            conf = max(conf, data_confidence)
        elif rsi > 70:
            bear.append(f"RSI(14)={rsi:.1f} 超买区域，存在回落可能")
            evidence.append(
                EvidenceItem(
                    source="technical",
                    agent="TechnicalAgent",
                    summary=f"RSI overbought at {rsi:.1f}",
                    confidence=data_confidence,
                    raw={"rsi_14": rsi},
                )
            )
            trend = "bearish"
            conf = max(conf, data_confidence)

    hist = f.get("macd_hist")
    if hist is not None:
        if hist > 0:
            bull.append(f"MACD 柱线为正 ({hist:.4f})，动量偏多")
            evidence.append(
                EvidenceItem(
                    source="technical",
                    agent="TechnicalAgent",
                    summary=f"MACD histogram positive ({hist:.4f})",
                    confidence=data_confidence,
                    raw={"macd_hist": hist},
                )
            )
            if trend == "neutral":
                trend = "bullish"
            conf = max(conf, data_confidence)
        elif hist < 0:
            bear.append(f"MACD 柱线为负 ({hist:.4f})，动量偏空")
            evidence.append(
                EvidenceItem(
                    source="technical",
                    agent="TechnicalAgent",
                    summary=f"MACD histogram negative ({hist:.4f})",
                    confidence=data_confidence,
                    raw={"macd_hist": hist},
                )
            )
            if trend == "neutral":
                trend = "bearish"
            conf = max(conf, data_confidence)

    bb = f.get("bb_pct")
    if bb is not None:
        if bb < 0.1:
            bull.append(f"价格接近布林带下轨 (pct={bb:.2f})")
        elif bb > 0.9:
            bear.append(f"价格接近布林带上轨 (pct={bb:.2f})")

    close = f.get("close")
    sma20 = f.get("sma_20")
    sma50 = f.get("sma_50")
    if close and sma20 and sma50:
        if close > sma20 > sma50:
            bull.append("价格位于 SMA20/SMA50 上方，短期趋势偏多")
            if trend != "bearish":
                trend = "bullish"
        elif close < sma20 < sma50:
            bear.append("价格位于 SMA20/SMA50 下方，短期趋势偏空")
            if trend != "bullish":
                trend = "bearish"

    for s in signals:
        evidence.append(
            EvidenceItem(
                source="signal",
                agent="SignalEngine",
                summary=f"{s.signal_name} → {s.direction} (strength={s.strength})",
                confidence=s.strength,
                timestamp=s.generated_at,
                raw={"signal_name": s.signal_name, "direction": s.direction},
            )
        )
        if s.direction == "long":
            bull.append(f"信号 {s.signal_name} 看多")
        elif s.direction == "short":
            bear.append(f"信号 {s.signal_name} 看空")

    if bull and bear:
        trend = "mixed"
        conf = min(conf, 0.45)

    return technical, bull, bear, evidence, trend, conf
