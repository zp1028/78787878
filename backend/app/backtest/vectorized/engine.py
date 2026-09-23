"""Fast causal backtest using the versioned StrategyRegistry.

The engine intentionally shares strategy definitions with live signal generation.
Indicators are calculated incrementally from OHLCV history and each strategy is
asked for the signal at that bar only. Execution is still deterministic and
includes fees/slippage.
"""
from __future__ import annotations

import math
import uuid
from typing import Any

from app.backtest.models import BacktestConfig, BacktestResult, TradeRecord
from app.quant.indicators.basic import bollinger, ema, latest, macd, rsi, sma
from app.quant.strategies import default_registry
from app.quant.features.engine import FeatureSnapshot


def _apply_slippage(price: float, side: str, bps: float) -> float:
    adj = price * (bps / 10_000.0)
    return price + adj if side == "long" else price - adj


def _feature_snapshots(config: BacktestConfig) -> list[FeatureSnapshot]:
    bars = config.bars
    closes = [float(b["close"]) for b in bars]
    volumes = [float(b.get("volume", 0)) for b in bars]
    highs = [float(b.get("high", b["close"])) for b in bars]
    lows = [float(b.get("low", b["close"])) for b in bars]
    out: list[FeatureSnapshot] = []
    # Keep the calculation causal: every index uses only bars[:i+1].
    for i in range(len(bars)):
        c = closes[: i + 1]
        v = volumes[: i + 1]
        h = highs[i]
        lo = lows[i]
        rsi_s = rsi(c, 14)
        macd_line, signal_line, hist = macd(c, 12, 26, 9)
        bb_mid, bb_upper, bb_lower = bollinger(c, 20)
        sma20, sma50 = sma(c, 20), sma(c, 50)
        ema12, ema26 = ema(c, 12), ema(c, 26)
        avg_vol = sum(v[-20:]) / 20.0 if len(v) >= 20 else None
        features: dict[str, float | None] = {
            "close": c[-1], "high": h, "low": lo, "volume": v[-1],
            "rsi_14": latest(rsi_s), "macd": latest(macd_line),
            "macd_signal": latest(signal_line), "macd_hist": latest(hist),
            "bb_mid": latest(bb_mid), "bb_upper": latest(bb_upper),
            "bb_lower": latest(bb_lower), "sma_20": latest(sma20),
            "sma_50": latest(sma50), "ema_12": latest(ema12),
            "ema_26": latest(ema26), "volume_sma_20": avg_vol,
        }
        if features["bb_upper"] is not None and features["bb_lower"] is not None:
            width = float(features["bb_upper"]) - float(features["bb_lower"])
            features["bb_width"] = width
            if width > 0:
                features["bb_pct"] = (c[-1] - float(features["bb_lower"])) / width
        if avg_vol and avg_vol > 0:
            features["volume_ratio"] = v[-1] / avg_vol
        close_time = int(bars[i].get("close_time") or bars[i].get("open_time") or i)
        out.append(FeatureSnapshot(
            config.instrument_id, config.symbol, config.timeframe,
            close_time, close_time, features, close_time,
        ))
    return out


def _legacy_strategy(config: BacktestConfig) -> tuple[str, dict[str, Any]]:
    # Keep old API names working while routing through StrategyRegistry.
    aliases = {"bb": "bollinger", "rsi": "rsi", "macd": "macd"}
    return aliases.get(config.strategy, config.strategy), dict(config.strategy_params)


def _metrics(trades: list[TradeRecord], equity_curve: list[dict[str, Any]], initial: float, final: float) -> dict[str, Any]:
    pnls = [float(t.pnl or 0.0) for t in trades]
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    returns: list[float] = []
    prev = initial
    for point in equity_curve:
        eq = float(point["equity"])
        if prev > 0:
            returns.append(eq / prev - 1.0)
        prev = eq
    sharpe = None
    if len(returns) > 1:
        mean = sum(returns) / len(returns)
        var = sum((x - mean) ** 2 for x in returns) / (len(returns) - 1)
        sd = math.sqrt(var)
        if sd > 0:
            sharpe = mean / sd * math.sqrt(len(returns))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    avg = sum(pnls) / len(pnls) if pnls else 0.0
    return {
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "profit_factor": round(profit_factor, 4) if math.isfinite(profit_factor) else "inf",
        "avg_trade_pnl": round(avg, 4),
        "expectancy": round(avg, 4),
        "sharpe": round(sharpe, 4) if sharpe is not None else None,
        "net_pnl": round(final - initial, 4),
    }


def run_vectorized(config: BacktestConfig) -> BacktestResult:
    bars = config.bars
    warnings: list[str] = []
    if len(bars) < 30:
        warnings.append("insufficient bars (<30); results may be unstable")
    if not bars:
        return BacktestResult(
            run_id=str(uuid.uuid4()), config_summary={}, engine="vectorized",
            initial_cash=config.initial_cash, final_equity=config.initial_cash,
            total_return_pct=0.0, max_drawdown_pct=0.0, trade_count=0,
            pit_enforced=config.enforce_pit, warnings=["no bars"],
        )

    # Sort before simulation when PIT is requested; otherwise preserve caller order.
    if config.enforce_pit:
        bars = sorted(bars, key=lambda b: int(b.get("close_time") or b.get("open_time") or 0))
    local = config.model_copy(deep=True)
    local.bars = bars
    strategy_id, params = _legacy_strategy(local)
    registry = default_registry()
    if strategy_id == "buy_hold":
        snapshots = []
    else:
        try:
            registry.get(strategy_id)
        except KeyError as exc:
            raise ValueError(f"unknown strategy: {strategy_id}") from exc
        snapshots = _feature_snapshots(local)

    cash = local.initial_cash
    qty = 0.0
    entry_price = 0.0
    entry_time = 0
    entry_fee = 0.0
    trades: list[TradeRecord] = []
    equity_curve: list[dict[str, Any]] = []
    peak = cash
    max_dd = 0.0

    for i, bar in enumerate(bars):
        close = float(bar["close"])
        t = int(bar.get("close_time") or bar.get("open_time") or i)
        if strategy_id == "buy_hold":
            signals = [{"direction": "long"}] if i == 0 else []
            exit_signal = i == len(bars) - 1
        else:
            signals = registry.evaluate(strategy_id, snapshots[i], params)
            exit_signal = any(s["direction"] == "short" for s in signals)

        if qty > 0 and (exit_signal or i == len(bars) - 1):
            px = _apply_slippage(close, "short", local.slippage_bps)
            proceeds = qty * px
            fee = proceeds * local.fee_rate
            cash += proceeds - fee
            pnl = (px - entry_price) * qty - entry_fee - fee
            pnl_pct = (px / entry_price - 1.0) * 100 if entry_price else 0.0
            trades.append(TradeRecord(
                entry_time=entry_time, exit_time=t, side="long",
                entry_price=entry_price, exit_price=px, quantity=qty,
                pnl=round(pnl, 4), pnl_pct=round(pnl_pct, 4),
                fee=round(entry_fee + fee, 4),
            ))
            qty = 0.0

        if qty == 0 and signals and any(s["direction"] == "long" for s in signals) and i < len(bars) - 1:
            px = _apply_slippage(close, "long", local.slippage_bps)
            fee = cash * local.fee_rate
            spendable = cash - fee
            if spendable > 0 and px > 0:
                qty = spendable / px
                cash -= qty * px + fee
                entry_price, entry_time, entry_fee = px, t, fee

        equity = cash + qty * close
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)
        equity_curve.append({"time": t, "equity": round(equity, 4)})

    final_equity = cash
    total_ret = (final_equity / local.initial_cash - 1.0) * 100 if local.initial_cash else 0.0
    wins = [t for t in trades if (t.pnl or 0) > 0]
    win_rate = len(wins) / len(trades) if trades else None
    sampled = equity_curve[:: max(1, len(equity_curve) // 200)]
    return BacktestResult(
        run_id=str(uuid.uuid4()),
        config_summary={
            "instrument_id": local.instrument_id, "symbol": local.symbol,
            "timeframe": local.timeframe, "strategy": strategy_id,
            "strategy_params": params, "strategy_version": registry.get(strategy_id).version if strategy_id != "buy_hold" else None,
            "bars": len(bars), "fee_rate": local.fee_rate, "slippage_bps": local.slippage_bps,
        },
        engine="vectorized", initial_cash=local.initial_cash,
        final_equity=round(final_equity, 4), total_return_pct=round(total_ret, 4),
        max_drawdown_pct=round(max_dd * 100, 4), trade_count=len(trades),
        win_rate=round(win_rate, 4) if win_rate is not None else None,
        trades=trades, equity_curve=sampled,
        metrics=_metrics(trades, equity_curve, local.initial_cash, final_equity),
        pit_enforced=local.enforce_pit, warnings=warnings,
    )
