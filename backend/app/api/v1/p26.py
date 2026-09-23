"""P26 enhancement endpoints: calibration, attribution, quality, audit, memory, regime, alerts."""
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.analysis_feedback import AnalysisFeedbackService
from app.services.p26_engine import P26Engine

router = APIRouter(tags=["p26"])
_feedback = AnalysisFeedbackService()
_engine = P26Engine()


@router.get("/p26/attribution")
async def p26_attribution(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m")):
    try:
        fb = _feedback.feedback_for(symbol.upper(), market, timeframe, None, 50)
        return {"symbol": symbol.upper(), "market": market, "timeframe": timeframe, **_engine.attribution(fb)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"attribution failed: {exc}") from exc


@router.get("/p26/calibration")
async def p26_calibration(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m")):
    try:
        fb = _feedback.feedback_for(symbol.upper(), market, timeframe, None, 50)
        return {"symbol": symbol.upper(), "market": market, "timeframe": timeframe, **_engine.calibration(fb)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"calibration failed: {exc}") from exc


@router.get("/p26/quality")
async def p26_quality(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m")):
    try:
        report = await _feedback.capture(symbol.upper(), market, timeframe, 250)
        _engine.record_audit(report)  # every capture is hashed into the audit chain
        return {"symbol": symbol.upper(), "market": market, "timeframe": timeframe, **_engine.quality_scorecard(report)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"quality failed: {exc}") from exc


@router.get("/p26/audit")
async def p26_audit(symbol: str | None = Query(None), market: str = Query("crypto"), timeframe: str = Query("15m"), limit: int = Query(50, ge=1, le=200)):
    try:
        return _engine.audit_chain(symbol, market, timeframe, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"audit failed: {exc}") from exc


@router.get("/p26/memory")
async def p26_memory(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m")):
    try:
        report = await _feedback.capture(symbol.upper(), market, timeframe, 250)
        fb = _feedback.feedback_for(symbol.upper(), market, timeframe, None, 50)
        return {"symbol": symbol.upper(), "market": market, "timeframe": timeframe, **_engine.memory(fb, report)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"memory failed: {exc}") from exc


@router.get("/p26/regime")
async def p26_regime(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m"), limit: int = Query(200, ge=20, le=500)):
    try:
        from app.services.crypto_provider_gateway import CryptoProviderGateway

        bars, _provider = await CryptoProviderGateway().fetch_klines(symbol.upper(), timeframe, limit)
        return {"symbol": symbol.upper(), "market": market, "timeframe": timeframe, **_engine.market_regime(bars)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"regime failed: {exc}") from exc


@router.get("/p26/alerts-center")
async def p26_alerts_center(limit: int = Query(40, ge=1, le=100)):
    """Alert center: P0/P1/P2 auto alerts derived from live market data,
    merged per symbol, plus user-defined alerts. Purely observational."""
    try:
        from app.services.crypto_provider_gateway import CryptoProviderGateway

        rows = await CryptoProviderGateway().market_rows()
        auto: list[dict[str, Any]] = []
        for r in rows:
            chg = r.get("change_pct")
            if chg is None:
                continue
            abs_chg = abs(float(chg))
            if abs_chg >= 15:
                level = "P0"
            elif abs_chg >= 8:
                level = "P1"
            elif abs_chg >= 4:
                level = "P2"
            else:
                continue
            direction = "涨" if chg > 0 else "跌"
            auto.append({
                "symbol": r["symbol"], "name": r.get("name", r["symbol"]), "venue": r.get("venue", ""),
                "level": level, "kind": "价格异动",
                "message": f"{direction}幅 {chg:+.2f}%",
                "change_pct": round(float(chg), 2),
                "price": r.get("price"), "quote_volume": r.get("quote_volume"),
            })
        auto.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        # merge per symbol: keep the highest level, concat messages
        merged: dict[str, dict[str, Any]] = {}
        for a in auto[: limit * 2]:
            s = a["symbol"]
            if s not in merged:
                a["messages"] = [a.pop("message")]
                merged[s] = a
            else:
                merged[s]["level"] = min(merged[s]["level"], a["level"])
                merged[s]["messages"].append(a["message"])
        auto_alerts = sorted(merged.values(), key=lambda x: ("P0", "P1", "P2").index(x["level"]))[:limit]

        user_rows = []
        try:
            from app.main import alert_engine

            user_rows = [
                {"id": n.id, "symbol": n.symbol, "kind": n.kind, "operator": n.operator,
                 "threshold": n.threshold, "enabled": n.enabled}
                for n in alert_engine.list()
            ]
        except Exception:
            user_rows = []
        return {
            "auto_alerts": auto_alerts,
            "user_alerts": user_rows,
            "level_counts": {
                "P0": sum(1 for a in auto_alerts if a["level"] == "P0"),
                "P1": sum(1 for a in auto_alerts if a["level"] == "P1"),
                "P2": sum(1 for a in auto_alerts if a["level"] == "P2"),
            },
            "merge_note": "同一标的的多条异动已合并为一条，按最高级别展示；P0 实时、P1 15 分钟、P2 列表。",
            "generated_at": int(time.time() * 1000),
            "read_only": True,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"alerts-center failed: {exc}") from exc
