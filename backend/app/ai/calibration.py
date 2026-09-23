"""Empirical calibration for analysis scenarios.

This module never invents historical outcomes.  It only uses persisted analysis
feedback records whose state has already been evaluated as validated/invalidated.
With no observations it returns an explicitly uncalibrated result instead of a
pretend probability.
"""
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Calibration:
    long_rate: float | None
    short_rate: float | None
    long_samples: int
    short_samples: int
    source: str

    @property
    def calibrated(self) -> bool:
        return self.long_samples + self.short_samples > 0


def load_calibration(path: str | Path = "data/analysis_feedback.json") -> Calibration:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raw = {}
    rows = raw.values() if isinstance(raw, dict) else []
    long_wins = long_losses = short_wins = short_losses = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        direction = row.get("direction")
        state = row.get("state")
        if state not in {"validated", "invalidated"}:
            state = (row.get("feedback") or {}).get("state")
        if direction == "long" and state in {"validated", "invalidated"}:
            if state == "validated": long_wins += 1
            else: long_losses += 1
        elif direction == "short" and state in {"validated", "invalidated"}:
            if state == "validated": short_wins += 1
            else: short_losses += 1
    long_n = long_wins + long_losses
    short_n = short_wins + short_losses
    return Calibration(
        long_rate=(long_wins / long_n if long_n else None),
        short_rate=(short_wins / short_n if short_n else None),
        long_samples=long_n,
        short_samples=short_n,
        source="persisted_feedback" if long_n + short_n else "no_completed_feedback",
    )


def scenario_probabilities(*, directional_score: float, calibration: Calibration) -> tuple[float | None, float | None, float | None, dict[str, Any]]:
    """Return empirical probabilities only when historical outcomes exist.

    The current directional score is used as a ranking signal, while the
    displayed probability is anchored to completed historical feedback.  The
    neutral/base case is the residual after the two directional probabilities.
    No fallback probability is fabricated when calibration is absent.
    """
    if not calibration.calibrated:
        return None, None, None, {
            "calibrated": False,
            "source": calibration.source,
            "sample_count": 0,
            "note": "没有已完成历史反馈，暂不显示伪造概率。",
        }

    # Pick the empirical rate belonging to the currently supported direction.
    # When both sides have samples, use the current directional score only to
    # distribute the empirical evidence between bull and bear; it is not itself
    # presented as a probability.
    bull = calibration.long_rate
    bear = calibration.short_rate
    if bull is None and bear is not None:
        bull = 1.0 - bear
    if bear is None and bull is not None:
        bear = 1.0 - bull
    assert bull is not None and bear is not None

    # Separate long/short validation rates are conditional statistics, not a
    # mutually-exclusive bull/base/bear probability distribution. Do not turn
    # them into percentages by adding arbitrary mass or weighting rules.
    return None, None, None, {
        "calibrated": False,
        "source": calibration.source,
        "long_samples": calibration.long_samples,
        "short_samples": calibration.short_samples,
        "historical_long_validation_rate": calibration.long_rate,
        "historical_short_validation_rate": calibration.short_rate,
        "note": "已有方向验证率仅作为条件统计展示；尚未训练并校准互斥 Bull/Base/Bear 概率模型。",
    }
