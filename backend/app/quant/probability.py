"""Walk-forward, data-derived directional probability research.

Probabilities are empirical and only emitted when there are enough historical
samples.  Each historical sample is built from bars available *before* the
outcome window, so future prices never enter the feature vector.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.quant.indicators.analysis import analyze_bars


@dataclass(frozen=True)
class ProbabilityResearch:
    long_probability: float | None
    short_probability: float | None
    samples: int
    train_samples: int
    calibration_samples: int
    oos_samples: int
    brier_long: float | None
    brier_short: float | None
    method: str
    status: str
    note: str


def _score(report) -> float | None:
    """A transparent feature score, not a probability."""
    vals: list[float] = []
    if report.trend_sma == "bullish": vals.append(1.0)
    elif report.trend_sma == "bearish": vals.append(-1.0)
    else: vals.append(0.0)
    if report.macd_hist is not None:
        vals.append(1.0 if report.macd_hist > 0 else -1.0 if report.macd_hist < 0 else 0.0)
    if report.rsi_14 is not None:
        vals.append(max(-1.0, min(1.0, (report.rsi_14 - 50.0) / 20.0)))
    if report.bb_pct is not None:
        vals.append(max(-1.0, min(1.0, (report.bb_pct - 0.5) * 2.0)))
    return sum(vals) / len(vals) if vals else None


def _label(report, future_close: float, horizon: int, threshold: float) -> tuple[int, int]:
    if report.last_price is None or report.last_price <= 0:
        return 0, 0
    move = future_close / report.last_price - 1.0
    return int(move >= threshold), int(move <= -threshold)


def _bin_rate(train: list[tuple[float, int]], score: float, bins: int = 5) -> float | None:
    if len(train) < 10:
        return None
    ordered = sorted(x[0] for x in train)
    rank = sum(1 for x in ordered if x <= score) / len(ordered)
    idx = min(bins - 1, int(rank * bins))
    members = [y for x, y in train if min(bins - 1, int((sum(1 for z in ordered if z <= x) / len(ordered)) * bins)) == idx]
    if len(members) < 5:
        return None
    # Laplace smoothing avoids 0/1 certainty from a small bin.
    return (sum(members) + 1.0) / (len(members) + 2.0)


def research_probability(bars: list[dict[str, Any]], *, horizon: int = 10, threshold: float = 0.01, min_train: int = 30) -> ProbabilityResearch:
    """Build a genuinely expanding walk-forward probability estimate.

    Every OOS prediction is produced using samples strictly before that OOS
    sample.  The calibration window is also strictly historical at each step.
    No future outcome is used to select the bin count or the displayed current
    probability.
    """
    ordered = sorted(bars, key=lambda b: int(b.get("close_time") or b.get("open_time") or 0))
    if len(ordered) < max(90, min_train + horizon + 30):
        return ProbabilityResearch(None, None, 0, 0, 0, 0, None, None, "expanding_walk_forward", "insufficient_history", "历史K线不足，暂不显示经过校准的概率。")

    samples: list[tuple[float, int, int]] = []
    start = 60
    end = len(ordered) - horizon
    for i in range(start, end):
        try:
            report = analyze_bars(
                instrument_id="research", symbol="research", timeframe="research",
                market="research", bars=ordered[: i + 1],
            )
            score = _score(report)
            if score is None:
                continue
            long_y, short_y = _label(report, float(ordered[i + horizon]["close"]), horizon, threshold)
            samples.append((score, long_y, short_y))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue

    if len(samples) < min_train + 15:
        return ProbabilityResearch(None, None, len(samples), len(samples), 0, 0, None, None, "expanding_walk_forward", "insufficient_samples", "可计算样本不足，暂不显示概率。")

    # Expanding walk-forward OOS evaluation. At each step the model can only
    # see outcomes strictly before the sample being predicted.
    candidate_bins = (3, 4, 5, 6)
    oos_preds: list[tuple[float, float, int, int]] = []
    total_train = 0
    total_cal = 0
    first_oos = max(min_train + 5, int(len(samples) * 0.70))
    for idx in range(first_oos, len(samples)):
        history = samples[:idx]
        cal_size = max(5, min(len(history) // 5, 30))
        train = history[:-cal_size]
        calibration = history[-cal_size:]
        if len(train) < min_train:
            continue
        best_bins = 5
        best_loss = float("inf")
        long_train = [(sc, yl) for sc, yl, _ in train]
        short_train = [(sc, ys) for sc, _, ys in train]
        for bins in candidate_bins:
            losses: list[float] = []
            for sc, yl, ys in calibration:
                pl = _bin_rate(long_train, sc, bins)
                ps = _bin_rate(short_train, sc, bins)
                if pl is not None:
                    losses.append((pl - yl) ** 2)
                if ps is not None:
                    losses.append((ps - ys) ** 2)
            if losses:
                loss = sum(losses) / len(losses)
                if loss < best_loss:
                    best_loss, best_bins = loss, bins
        sc, yl, ys = samples[idx]
        pl = _bin_rate(long_train, sc, best_bins)
        ps = _bin_rate(short_train, sc, best_bins)
        if pl is not None and ps is not None:
            oos_preds.append((pl, ps, yl, ys))
            total_train += len(train)
            total_cal += len(calibration)

    if len(oos_preds) < 10:
        return ProbabilityResearch(None, None, len(samples), max(0, first_oos - 5), 0, len(oos_preds), None, None, "expanding_walk_forward", "weak_oos", "样本存在，但独立扩展式OOS样本不足以展示校准概率。")

    brier_l = sum((p - y) ** 2 for p, _, y, _ in oos_preds) / len(oos_preds)
    brier_s = sum((p - y) ** 2 for _, p, _, y in oos_preds) / len(oos_preds)

    # Final estimate: fit only on all completed samples before the current
    # decision point, using a historical calibration tail to choose bins.
    history = samples[:-1]
    cal_size = max(5, min(len(history) // 5, 30))
    train = history[:-cal_size]
    calibration = history[-cal_size:]
    long_train = [(sc, yl) for sc, yl, _ in train]
    short_train = [(sc, ys) for sc, _, ys in train]
    best_bins = 5
    best_loss = float("inf")
    for bins in candidate_bins:
        losses: list[float] = []
        for sc, yl, ys in calibration:
            pl = _bin_rate(long_train, sc, bins)
            ps = _bin_rate(short_train, sc, bins)
            if pl is not None:
                losses.append((pl - yl) ** 2)
            if ps is not None:
                losses.append((ps - ys) ** 2)
        if losses:
            loss = sum(losses) / len(losses)
            if loss < best_loss:
                best_loss, best_bins = loss, bins

    current = samples[-1][0]
    pl = _bin_rate(long_train, current, best_bins)
    ps = _bin_rate(short_train, current, best_bins)
    if pl is None or ps is None:
        return ProbabilityResearch(None, None, len(samples), len(train), len(calibration), len(oos_preds), round(brier_l, 6), round(brier_s, 6), "expanding_walk_forward", "uncalibrated", "OOS验证完成，但当前条件没有足够同类历史样本，暂不显示概率。")

    return ProbabilityResearch(
        round(pl, 6), round(ps, 6), len(samples), len(train), len(calibration), len(oos_preds),
        round(brier_l, 6), round(brier_s, 6), "expanding_walk_forward", "calibrated",
        f"基于{len(samples)}个历史样本；采用扩展式Walk-Forward，独立OOS={len(oos_preds)}；当前训练/校准={len(train)}/{len(calibration)}；Brier long/short={brier_l:.4f}/{brier_s:.4f}。",
    )

