"""Walk-forward research engine with deterministic parameter search.

The optimizer only scores parameters on the in-sample segment. Validation is
used for selection stability and the OOS segment is never used for fitting.
"""
from __future__ import annotations

from typing import Any

from app.backtest.models import BacktestConfig, BacktestResult
from app.backtest.vectorized.engine import run_vectorized


def split_bars(bars: list[dict[str, Any]], train_ratio: float = 0.6, val_ratio: float = 0.2) -> tuple[list, list, list]:
    if not 0 < train_ratio < 1 or not 0 <= val_ratio < 1 or train_ratio + val_ratio >= 1:
        raise ValueError("train_ratio + val_ratio must be < 1")
    ordered = sorted(bars, key=lambda b: int(b.get("close_time") or b.get("open_time") or 0))
    n = len(ordered)
    t, v = int(n * train_ratio), int(n * (train_ratio + val_ratio))
    return ordered[:t], ordered[t:v], ordered[v:]


def _default_grid(strategy: str) -> list[dict[str, Any]]:
    grids = {
        "rsi": [{"low": lo, "high": hi} for lo, hi in ((25, 75), (30, 70), (35, 65), (20, 80))],
        "volume": [{"threshold": x} for x in (1.5, 2.0, 2.5, 3.0)],
        "bollinger": [{"lower": x, "upper": 1.0 - x} for x in (0.03, 0.05, 0.10)],
        "macd": [{}],
        "buy_hold": [{}],
    }
    return grids.get(strategy, [{}])


def _score(result: BacktestResult) -> float:
    # Prefer return but penalize drawdown and unstable tiny samples.
    trades = max(result.trade_count, 1)
    return float(result.total_return_pct) - 0.50 * float(result.max_drawdown_pct) + min(trades, 20) * 0.01


def optimize_parameters(base: BacktestConfig, bars: list[dict[str, Any]], candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    grid = candidates or _default_grid(base.strategy)
    scored: list[dict[str, Any]] = []
    for params in grid:
        cfg = base.model_copy(deep=True)
        cfg.bars = bars
        cfg.strategy_params = {**base.strategy_params, **params}
        result = run_vectorized(cfg)
        scored.append({"params": cfg.strategy_params, "score": round(_score(result), 6), "result": result.model_dump()})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"best": scored[0] if scored else None, "candidates": scored}


def run_walk_forward(
    base: BacktestConfig,
    *,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    train, val, oos = split_bars(base.bars, train_ratio, val_ratio)
    if len(train) < 30 or len(val) < 10 or len(oos) < 10:
        return {"error": "insufficient bars for walk-forward", "splits": {"train_bars": len(train), "validation_bars": len(val), "oos_bars": len(oos)}}

    train_opt = optimize_parameters(base, train, candidates)
    best_params = train_opt["best"]["params"] if train_opt["best"] else dict(base.strategy_params)

    val_cfg = base.model_copy(deep=True)
    val_cfg.bars = val
    val_cfg.strategy_params = best_params
    validation = run_vectorized(val_cfg)

    oos_cfg = base.model_copy(deep=True)
    oos_cfg.bars = oos
    oos_cfg.strategy_params = best_params
    oos_result = run_vectorized(oos_cfg)

    train_result = train_opt["best"]["result"] if train_opt["best"] else None
    stability = {
        "train_score": train_opt["best"]["score"] if train_opt["best"] else None,
        "validation_return_pct": validation.total_return_pct,
        "oos_return_pct": oos_result.total_return_pct,
        "oos_drawdown_pct": oos_result.max_drawdown_pct,
        "parameter_stability": "stable" if validation.total_return_pct >= 0 and oos_result.total_return_pct >= 0 else "unstable",
    }
    warnings = []
    if stability["parameter_stability"] != "stable":
        warnings.append("selected parameters did not remain profitable through validation and OOS")
    if oos_result.trade_count < 5:
        warnings.append("OOS trade count is low; performance is statistically weak")

    return {
        "method": "train_validate_oos",
        "strategy": base.strategy,
        "strategy_params_selected": best_params,
        "splits": {"train_bars": len(train), "validation_bars": len(val), "oos_bars": len(oos)},
        "optimization": train_opt,
        "results": {"train": train_result, "validation": validation.model_dump(), "oos": oos_result.model_dump()},
        "validation": validation.model_dump(),
        "oos": oos_result.model_dump(),
        "stability": stability,
        "warnings": warnings,
        "pit_enforced": base.enforce_pit,
    }
