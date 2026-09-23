from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from app.services.analysis_report import HumanAnalysisReportService
from app.services.unified_analysis_report import UnifiedAnalysisReportService


class AnalysisFeedbackService:
    """Freezes analytical reports and evaluates later market movement against them.

    Historical reports are immutable snapshots. Later evaluations never rewrite the
    original report; they create feedback records tied to that report id.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or "data/analysis_feedback.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._reports: dict[str, dict[str, Any]] = {}
        self._load()
        self.human = HumanAnalysisReportService()
        self.unified = UnifiedAnalysisReportService()

    def _load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._reports = raw if isinstance(raw, dict) else {}
        except Exception:
            self._reports = {}

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._reports, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _confidence(report: dict[str, Any]) -> float:
        """Predictive confidence is never inferred from indicator heuristics.

        Until a calibrated, point-in-time model is available, keep this at zero
        and expose the evidence quality separately. A UI must render this as
        "未校准", not as 0% probability or a made-up confidence score.
        """
        return 0.0

    @staticmethod
    def _direction(report: dict[str, Any]) -> str:
        tech = report.get("indicator_report") or {}
        trend = tech.get("trend_sma")
        if trend == "bullish": return "long"
        if trend == "bearish": return "short"
        return "neutral"

    @staticmethod
    def _report_id(symbol: str, market: str, timeframe: str, generated_at: int) -> str:
        seed = f"{market}:{symbol}:{timeframe}:{generated_at}".encode()
        return "R-" + hashlib.sha1(seed).hexdigest()[:12].upper()

    async def current_price(self, symbol: str, market: str, timeframe: str, limit: int = 250) -> float | None:
        """Read the latest market price without creating or mutating a historical report."""
        report = await self.human.build(symbol, market, timeframe, limit)
        value = report.get("last_price")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    async def capture(self, symbol: str, market: str, timeframe: str, limit: int = 250) -> dict[str, Any]:
        report = await self.human.build(symbol, market, timeframe, limit)
        now = int(report.get("generated_at") or time.time() * 1000)
        confidence = self._confidence(report)
        direction = self._direction(report)
        # De-duplicate repeated 15-second refreshes when the analytical state is unchanged.
        key = f"{market.lower()}:{symbol.upper()}:{timeframe}"
        recent = [r for r in self._reports.values() if r.get("key") == key]
        if recent:
            last = max(recent, key=lambda x: x.get("generated_at", 0))
            same_state = (last.get("direction") == direction and last.get("summary") == report.get("summary"))
            if same_state and now - int(last.get("generated_at", 0)) < 60_000:
                return last
        rid = self._report_id(symbol, market, timeframe, now)
        snapshot = {
            "report_id": rid, "key": key, "symbol": report["symbol"], "market": market,
            "timeframe": timeframe, "generated_at": now, "price_at_report": report.get("last_price"),
            "direction": direction, "confidence": confidence, "confidence_status": "uncalibrated", "state": "tracking",
            "summary": report.get("summary", ""), "narrative": report.get("narrative", ""),
            "structure": report.get("structure", {}), "overbought": report.get("overbought", {}),
            "oversold": report.get("oversold", {}), "indicator_report": report.get("indicator_report", {}),
            "feedback": {"state": "waiting", "summary": "等待后续行情验证。", "evaluated_at": now},
        }
        self._reports[rid] = snapshot
        self._save()
        return snapshot

    def _evaluate(self, r: dict[str, Any], current_price: float | None) -> tuple[str, str]:
        if current_price is None or r.get("price_at_report") is None:
            return "waiting", "当前价格数据不足，暂不能评价此前报告。"
        p0 = float(r["price_at_report"]); p = float(current_price)
        if p0 <= 0: return "waiting", "基准价格无效，等待新的有效行情。"
        move = (p - p0) / p0 * 100
        direction = r.get("direction")
        if direction == "long":
            if move >= 1.0: return "validated", f"报告后价格向多头方向运行 {move:.2f}%，原多头情景得到阶段性验证。"
            if move <= -1.0: return "invalidated", f"报告后价格向反方向运行 {move:.2f}%，原多头情景明显转弱，需要重新分析。"
        elif direction == "short":
            if move <= -1.0: return "validated", f"报告后价格向空头方向运行 {move:.2f}%，原空头情景得到阶段性验证。"
            if move >= 1.0: return "invalidated", f"报告后价格向反方向运行 +{move:.2f}%，原空头情景明显转弱，需要重新分析。"
        return "tracking", f"报告后价格变化 {move:+.2f}%，暂未达到验证或失效阈值，继续跟踪。"

    def feedback_for(self, symbol: str, market: str, timeframe: str, current_price: float | None = None, limit: int = 20) -> dict[str, Any]:
        key = f"{market.lower()}:{symbol.upper()}:{timeframe}"
        rows = [r for r in self._reports.values() if r.get("key") == key]
        rows.sort(key=lambda x: x.get("generated_at", 0), reverse=True)
        history = []
        for r in rows[:limit]:
            state, summary = self._evaluate(r, current_price)
            r.setdefault("feedback", {})["state"] = state
            r.setdefault("feedback", {})["summary"] = summary
            r.setdefault("feedback", {})["evaluated_at"] = int(time.time() * 1000)
            history.append({
                "report_id": r["report_id"], "generated_at": r["generated_at"], "direction": r["direction"],
                "confidence": r["confidence"], "state": r["state"], "feedback_state": state,
                "feedback_summary": summary, "price_at_report": r.get("price_at_report"), "current_price": current_price,
            })
        if rows: self._save()
        current = history[0] if history else None
        return {
            "symbol": symbol, "market": market, "timeframe": timeframe,
            "current_state": current["feedback_state"] if current else "no_history",
            "current_summary": current["feedback_summary"] if current else "当前还没有冻结的历史分析报告。",
            "history": history,
        }

    async def feed(self, market: str, timeframe: str, candidates: list[str], limit: int = 8) -> dict[str, Any]:
        items = []
        for symbol in candidates[:max(limit * 2, limit)]:
            try:
                r = await self.capture(symbol, market, timeframe, 250)
                # Never evaluate a report against its own frozen report price.
                # The feedback loop must use a fresh market observation.
                price = await self.current_price(symbol, market, timeframe, 250)
                fb = self.feedback_for(symbol, market, timeframe, price, 1)
                current = fb.get("history", [{}])[0] if fb.get("history") else {}
                items.append({
                    "report_id": r["report_id"], "symbol": r["symbol"], "market": market, "timeframe": timeframe,
                    "confidence": r["confidence"], "confidence_status": r.get("confidence_status", "uncalibrated"), "state": r["state"], "direction": r["direction"],
                    "summary": r["summary"], "generated_at": r["generated_at"],
                    "feedback_state": current.get("feedback_state", "waiting"),
                    "feedback_summary": current.get("feedback_summary", "等待后续行情验证。"),
                })
            except Exception:
                continue
        items.sort(key=lambda x: (x["confidence"], x["generated_at"]), reverse=True)
        return {"generated_at": int(time.time() * 1000), "data_quality": "live_analysis", "items": items[:limit]}
