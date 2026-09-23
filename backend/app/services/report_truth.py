from __future__ import annotations
from typing import Any

# A report may only be marked available when the exact evidence required by the
# report is present in the current snapshot. Provider objects with
# available=False are treated as missing; they are never accepted merely
# because the object itself is non-empty.
SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "quote": ("evidence.technical.last_price",),
    "ohlcv": ("evidence.technical.last_price", "evidence.technical.sma_20"),
    "technical": ("evidence.technical.last_price", "evidence.technical.trend_label"),
    "ohlcv_mtf": ("evidence.technical.last_price",),
    "risk": ("scenario_analysis.risk_notes",),
    "session": ("session_context",),
    "report": ("summary",),
    "derivatives": ("market_enrichment.binance_derivatives",),
    "funding": ("market_enrichment.binance_derivatives.funding",),
    "flow": ("evidence.technical.volume_ratio",),
    "fundamental": ("market_enrichment.fundamentals",),
    "news": ("market_enrichment.news",),
    "sentiment": ("market_enrichment.sentiment",),
    "events": ("market_enrichment.events",),
    "calendar": ("market_enrichment.calendar",),
    "fx": ("market_enrichment.fx",),
    "onchain": ("market_enrichment.onchain",),
    "historical": ("probability.samples",),
    "strategy": ("strategy_backtest",),
    "observation": ("scenario_analysis.holding",),
    "journal": ("journal",),
}


def _get(root: dict[str, Any], path: str) -> Any:
    cur: Any = root
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _present(value: Any) -> bool:
    """Return true only for evidence that actually contains usable data.

    An object such as {"available": False, "reason": "provider unavailable"}
    is deliberately considered missing. This closes a subtle truth-gate bug
    where an unavailable provider object could previously pass because it was
    a non-empty dictionary.
    """
    if value is None or value is False:
        return False
    if isinstance(value, (list, tuple, set, str)):
        return bool(value)
    if isinstance(value, dict):
        if value.get("available") is False:
            return False
        if "status" in value and str(value.get("status")).lower() in {"unavailable", "pending_provider", "provider_required"}:
            return False
        return bool(value)
    return True


def truth(definition: Any, base: dict[str, Any], market_status: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    for req in definition.source_requirements:
        paths = SOURCE_KEYS.get(req)
        if not paths:
            missing.append(f"unmapped_source_requirement:{req}")
            continue
        for path in paths:
            if not _present(_get(base, path)):
                missing.append(path)

    if definition.key == "probability":
        p = base.get("probability") or {}
        if p.get("status") != "calibrated" or p.get("long") is None or p.get("short") is None:
            missing.append("probability.status=calibrated")

    if not market_status.get("configured", True) and definition.source_requirements:
        return {"status": "unavailable", "reason": "市场数据源未配置；未生成替代数据。", "missing": missing}
    if missing:
        return {
            "status": "pending_provider",
            "reason": "当前数据快照缺少该报告所需的真实数据源；未用默认值填充。",
            "missing": sorted(set(missing)),
        }
    return {"status": "available", "reason": "所需证据已在当前快照中取得。", "missing": []}
