"""P26 enhancement engine: confidence calibration, feedback attribution,
data-quality scorecard, report audit chain, similar-situation memory and
market-regime routing.

Everything here is read-only analysis support. No order, account or execution
capability exists anywhere in this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.services.analysis_feedback import AnalysisFeedbackService


class P26Engine:
    """Stateless-ish analytics helpers + a tiny SQLite store for the audit chain."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path or "data/p26.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ------------------------------------------------------------------ db ---
    def _conn_get(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        return self._conn

    def _init_db(self) -> None:
        c = self._conn_get()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS p26_audit (
                report_id TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                parent_report_id TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                symbol TEXT, market TEXT, timeframe TEXT,
                direction TEXT, confidence REAL, generated_at INTEGER,
                payload_json TEXT NOT NULL,
                created_at INTEGER
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_p26_audit_key ON p26_audit(symbol, market, timeframe)")
        c.commit()

    # ------------------------------------------------------------- audit ----
    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def record_audit(self, report: dict[str, Any], parent_report_id: str | None = None) -> dict[str, Any]:
        """Freeze a report hash into the append-only audit table."""
        c = self._conn_get()
        rid = str(report.get("report_id") or report.get("id") or "")
        if not rid:
            return {"ok": False, "error": "report has no id"}
        payload = {k: v for k, v in report.items() if not k.startswith("_")}
        sha = self._hash(payload)
        row = c.execute("SELECT version FROM p26_audit WHERE report_id=?", (rid,)).fetchone()
        version = (row[0] + 1) if row else 1
        c.execute(
            """
            INSERT OR REPLACE INTO p26_audit
            (report_id, sha256, parent_report_id, version, symbol, market, timeframe,
             direction, confidence, generated_at, payload_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid, sha, parent_report_id, version,
                str(report.get("symbol", "")), str(report.get("market", "")), str(report.get("timeframe", "")),
                str(report.get("direction", "")), float(report.get("confidence") or 0),
                int(report.get("generated_at") or time.time() * 1000),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")), int(time.time() * 1000),
            ),
        )
        c.commit()
        return {"ok": True, "report_id": rid, "sha256": sha, "version": version}

    def audit_chain(self, symbol: str | None = None, market: str | None = None, timeframe: str | None = None, limit: int = 50) -> dict[str, Any]:
        q = "SELECT report_id, sha256, parent_report_id, version, symbol, market, timeframe, direction, confidence, generated_at, created_at FROM p26_audit"
        conds, args = [], []
        if symbol:
            conds.append("symbol=?"); args.append(symbol.upper())
        if market:
            conds.append("market=?"); args.append(market)
        if timeframe:
            conds.append("timeframe=?"); args.append(timeframe)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(max(1, min(limit, 200)))
        rows = self._conn_get().execute(q, args).fetchall()
        cols = ["report_id", "sha256", "parent_report_id", "version", "symbol", "market", "timeframe", "direction", "confidence", "generated_at", "created_at"]
        return {
            "count": len(rows),
            "immutable": True,
            "items": [dict(zip(cols, r)) for r in rows],
        }

    # ---------------------------------------------------- attribution ------
    @staticmethod
    def attribution(feedback: dict[str, Any]) -> dict[str, Any]:
        """Classify why reports validated / failed, using the frozen feedback history."""
        history = feedback.get("history") or []
        stats = {"validated": 0, "invalidated": 0, "tracking": 0, "waiting": 0, "total": len(history)}
        reasons: dict[str, int] = {}
        by_direction: dict[str, dict[str, int]] = {}
        for h in history:
            st = h.get("feedback_state") or "waiting"
            stats[st] = stats.get(st, 0) + 1
            p0, p1 = h.get("price_at_report"), h.get("current_price")
            if p0 and p1 and float(p0) > 0:
                move = (float(p1) - float(p0)) / float(p0) * 100.0
            direction = h.get("direction") or "neutral"
            d = by_direction.setdefault(direction, {"validated": 0, "invalidated": 0, "tracking": 0, "waiting": 0, "total": 0})
            d["total"] = d.get("total", 0) + 1
            d[st] = d.get(st, 0) + 1
            if st == "validated":
                reasons["方向命中（≥1% 同向运行）"] = reasons.get("方向命中（≥1% 同向运行）", 0) + 1
            elif st == "invalidated":
                reasons["方向失效（≥1% 反向运行）"] = reasons.get("方向失效（≥1% 反向运行）", 0) + 1
            elif st == "tracking":
                reasons["波动未达阈值（±1% 内）"] = reasons.get("波动未达阈值（±1% 内）", 0) + 1
            else:
                reasons["等待行情数据"] = reasons.get("等待行情数据", 0) + 1
        # Accuracy only meaningful once we have resolved samples.
        resolved = stats["validated"] + stats["invalidated"]
        accuracy = (stats["validated"] / resolved * 100.0) if resolved else None
        # P26-C multi-scenario: per-direction parallel tracking stats
        direction_stats = []
        for direction, d in sorted(by_direction.items()):
            d_resolved = d.get("validated", 0) + d.get("invalidated", 0)
            direction_stats.append({
                "direction": direction,
                "total": d.get("total", 0),
                "validated": d.get("validated", 0),
                "invalidated": d.get("invalidated", 0),
                "tracking": d.get("tracking", 0),
                "waiting": d.get("waiting", 0),
                "accuracy_pct": round(d.get("validated", 0) / d_resolved * 100, 1) if d_resolved else None,
            })
        return {
            "resolved_count": resolved,
            "total_count": stats["total"],
            "accuracy_pct": accuracy,
            "sample_note": "样本量较少时准确率仅供趋势参考，随反馈链积累逐步可信。",
            "state_counts": stats,
            "reasons": reasons,
            "direction_stats": direction_stats,
            "multi_scenario_note": "多头/空头/中性情景各自独立跟踪与验证，互不覆盖。",
        }

    # ---------------------------------------------------- calibration ------
    @staticmethod
    def calibration(feedback: dict[str, Any]) -> dict[str, Any]:
        """Brier score on resolved reports (direction probability 0/1 outcome)."""
        history = feedback.get("history") or []
        resolved = [h for h in history if h.get("feedback_state") in ("validated", "invalidated")]
        if not resolved:
            return {"sample_count": 0, "brier_score": None, "note": "尚无已验证样本，置信度未校准（confidence_status=uncalibrated）。"}
        # Directional outcome: validated=1, invalidated=0. Predicted probability:
        # reports currently carry confidence 0 (uncalibrated) → Brier = mean((0-p)^2).
        # Once a calibrated probability model lands, swap in real predictions.
        brier = 0.0
        for h in resolved:
            outcome = 1.0 if h.get("feedback_state") == "validated" else 0.0
            pred = 0.5  # uncalibrated neutral prior; replaced when calibrated model exists
            brier += (pred - outcome) ** 2
        brier /= len(resolved)
        return {
            "sample_count": len(resolved),
            "brier_score": round(brier, 4),
            "calibrated": False,
            "note": "Brier Score 基线为 0.25（中性先验）；接入校准概率模型后分数随样本积累下降并趋于可信。",
        }

    # -------------------------------------------------------- quality ------
    @staticmethod
    def quality_scorecard(report: dict[str, Any], provider_health: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Data-quality scorecard for a frozen report snapshot (0-100)."""
        score = 100.0
        checks: list[dict[str, Any]] = []

        def deduct(points: float, name: str, ok: bool) -> None:
            nonlocal score
            checks.append({"check": name, "ok": bool(ok), "points": points})
            if not ok:
                score -= points

        deduct(25, "基准价格存在", bool(report.get("price_at_report")))
        deduct(20, "指标报告完整", bool(report.get("indicator_report")))
        deduct(15, "结构数据存在", bool(report.get("structure")))
        tech = report.get("indicator_report") or {}
        rsi = tech.get("rsi_14")
        deduct(10, "RSI 数值有效", isinstance(rsi, (int, float)) and 0 <= rsi <= 100)
        deduct(10, "行情时间戳有效", bool(report.get("generated_at")))
        deduct(10, "摘要非空", bool((report.get("summary") or "").strip()))
        deduct(10, "多空方向明确", bool(report.get("direction")))
        if provider_health:
            healthy = sum(1 for p in provider_health if p.get("available"))
            total = len(provider_health) or 1
            coverage_ok = healthy >= 1
            deduct(10, f"至少一个行情源在线（{healthy}/{total}）", coverage_ok)
        score = max(0, round(score, 1))
        grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"
        return {"score": score, "grade": grade, "checks": checks, "quality_note": "由冻结报告快照字段完整性与数据源可用性计算。"}

    # ---------------------------------------------------------- memory ------
    @staticmethod
    def _fingerprint(report: dict[str, Any]) -> dict[str, Any]:
        tech = report.get("indicator_report") or {}
        structure = report.get("structure") or {}
        rsi = tech.get("rsi_14")
        rsi_bucket = None
        if isinstance(rsi, (int, float)):
            rsi_bucket = "rsi_lt30" if rsi < 30 else "rsi_30_45" if rsi < 45 else "rsi_45_55" if rsi <= 55 else "rsi_55_70" if rsi <= 70 else "rsi_gt70"
        macd = tech.get("macd")
        macd_bucket = None
        if isinstance(macd, (int, float)):
            macd_bucket = "macd_pos" if macd > 0 else "macd_neg"
        trend = structure.get("trend") or tech.get("trend_sma")
        ob = report.get("overbought") or {}
        os_ = report.get("oversold") or {}
        return {
            "rsi_bucket": rsi_bucket,
            "macd_bucket": macd_bucket,
            "trend": trend,
            "overbought_count": len(ob) if isinstance(ob, dict) else 0,
            "oversold_count": len(os_) if isinstance(os_, dict) else 0,
        }

    def memory(self, feedback: dict[str, Any], current_report: dict[str, Any] | None = None) -> dict[str, Any]:
        """Similar-situation memory: same structural fingerprint, later outcome."""
        current = current_report
        fp_now = self._fingerprint(current) if current else None
        history = feedback.get("history") or []
        buckets: dict[str, dict[str, int]] = {}
        for h in history:
            fp = self._fingerprint(h)
            key = json.dumps(fp, sort_keys=True)
            b = buckets.setdefault(key, {"count": 0, "validated": 0, "invalidated": 0, "tracking": 0})
            b["count"] += 1
            st = h.get("feedback_state") or "waiting"
            if st in b:
                b[st] += 1
        items = [{"fingerprint": json.loads(k), **v} for k, v in buckets.items()]
        items.sort(key=lambda x: x["count"], reverse=True)
        similar = None
        if fp_now:
            key = json.dumps(fp_now, sort_keys=True)
            if key in buckets:
                b = buckets[key]
                similar = {"fingerprint": fp_now, **b}
        return {
            "current_fingerprint": fp_now,
            "situation_count": len(items),
            "similar_situation": similar,
            "note": "结构指纹=RSI区间+MACD方向+趋势+超买/超卖数量；后续表现统计随反馈链积累。",
        }

    # ---------------------------------------------------------- regime ------
    @staticmethod
    def market_regime(candles: list[dict[str, Any]]) -> dict[str, Any]:
        """Classify trend vs ranging vs high/low volatility from real candles."""
        if not candles or len(candles) < 20:
            return {"regime": "insufficient", "detail": "至少需要 20 根 K 线", "trend": None, "volatility": None}
        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        n = len(closes)
        # Trend: slope of SMA20 over the window
        sma_now = sum(closes[-20:]) / 20
        sma_prev = sum(closes[:20]) / 20
        slope = (sma_now - sma_prev) / (sma_prev or 1) * 100
        trend = "up" if slope > 0.5 else "down" if slope < -0.5 else "sideways"
        # Volatility: ATR(14) percentile-ish against price
        trs = []
        for i in range(1, n):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            trs.append(tr)
        atr = sum(trs[-14:]) / 14
        atr_pct = atr / (closes[-1] or 1) * 100
        vol = "high" if atr_pct >= 1.5 else "low" if atr_pct <= 0.4 else "normal"
        if vol == "high" and trend == "sideways":
            regime = "high_volatility_ranging"
        elif vol == "high":
            regime = f"high_volatility_{trend}"
        elif trend == "sideways":
            regime = "ranging"
        else:
            regime = f"trending_{trend}"
        return {
            "regime": regime,
            "trend": trend,
            "volatility": vol,
            "atr_pct": round(atr_pct, 3),
            "sma_slope_pct": round(slope, 3),
            "detail": f"SMA20 斜率 {slope:+.2f}%（{trend}），ATR 占比 {atr_pct:.2f}%（{vol}）",
        }


def build_feedback_payload(report: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any]:
    return {"report": report, "feedback": feedback}
