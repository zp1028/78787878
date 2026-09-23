"""Event-driven backtest skeleton.

Replays closed candles as events through the same Feature/Signal path
conceptually (simplified in-process loop). Suitable for validating
parity with live logic; slower than vectorized but closer to reality.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.backtest.models import BacktestConfig, BacktestResult, TradeRecord
from app.backtest.vectorized.engine import _apply_slippage
from app.core.event_bus import EventBus
from app.core.events import CandleEvent
from app.quant.features.engine import FeatureEngine
from app.quant.signals.engine import SignalEngine
from app.quant.strategies import default_registry
from app.quant.features.engine import FeatureSnapshot


async def run_event_driven(config: BacktestConfig) -> BacktestResult:
    """Replay bars as CandleEvents → Feature → Signal, then simple execution."""
    bus = EventBus()
    fe = FeatureEngine(bus, max_bars=500)
    se = SignalEngine(bus, fe)
    fe.subscribe()
    se.subscribe()
    registry = default_registry()
    strategy_id = {"bb": "bollinger"}.get(config.strategy, config.strategy)
    strategy_params = dict(config.strategy_params)
    if strategy_id != "buy_hold":
        registry.get(strategy_id)

    cash = config.initial_cash
    position_qty = 0.0
    entry_price = 0.0
    entry_time = 0
    trades: list[TradeRecord] = []
    equity_curve: list[dict[str, Any]] = []
    peak = cash
    max_dd = 0.0
    warnings: list[str] = []

    if config.enforce_pit:
        # ensure bars are sorted by time (causal replay)
        bars = sorted(config.bars, key=lambda b: int(b.get("close_time") or b.get("open_time") or 0))
    else:
        bars = list(config.bars)
        warnings.append("PIT not enforced: bar order may allow look-ahead")

    for i, b in enumerate(bars):
        open_time = int(b.get("open_time") or i)
        close_time = int(b.get("close_time") or open_time + 60_000)
        close = float(b["close"])
        event = CandleEvent(
            instrument_id=config.instrument_id,
            symbol=config.symbol,
            interval=config.timeframe,
            open=float(b.get("open", close)),
            high=float(b.get("high", close)),
            low=float(b.get("low", close)),
            close=close,
            volume=float(b.get("volume", 0)),
            open_time=open_time,
            close_time=close_time,
            is_closed=True,
            source_timestamp=close_time,
            received_at=close_time,
            venue="backtest",
        )
        await bus.publish(event)

        snap = fe.get_latest(config.instrument_id, config.timeframe)
        enter = False
        exit_ = False
        if strategy_id == "buy_hold":
            enter = i == 0
            exit_ = i == len(bars) - 1
        elif snap is not None:
            feature = FeatureSnapshot(
                snap.instrument_id, snap.symbol, snap.timeframe, snap.computed_at,
                snap.available_at, snap.features, snap.source_close_time,
            )
            signals = registry.evaluate(strategy_id, feature, strategy_params)
            enter = any(s.get("direction") == "long" for s in signals)
            exit_ = any(s.get("direction") == "short" for s in signals)

        if position_qty > 0 and (exit_ or i == len(bars) - 1):
            px = _apply_slippage(close, "short", config.slippage_bps)
            fee = position_qty * px * config.fee_rate
            cash += position_qty * px - fee
            pnl = (px - entry_price) * position_qty - fee
            trades.append(
                TradeRecord(
                    entry_time=entry_time,
                    exit_time=close_time,
                    side="long",
                    entry_price=entry_price,
                    exit_price=px,
                    quantity=position_qty,
                    pnl=round(pnl, 4),
                    pnl_pct=round((px / entry_price - 1) * 100, 4) if entry_price else 0,
                    fee=round(fee, 4),
                )
            )
            position_qty = 0.0

        if position_qty == 0 and enter and i < len(bars) - 1:
            px = _apply_slippage(close, "long", config.slippage_bps)
            fee = cash * config.fee_rate
            spendable = cash - fee
            if spendable > 0 and px > 0:
                qty = spendable / px
                cash -= qty * px + fee
                position_qty = qty
                entry_price = px
                entry_time = close_time

        equity = cash + position_qty * close
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak else 0
        max_dd = max(max_dd, dd)
        equity_curve.append({"time": close_time, "equity": round(equity, 4)})

    if position_qty > 0 and bars:
        close = float(bars[-1]["close"])
        close_time = int(bars[-1].get("close_time") or 0)
        px = _apply_slippage(close, "short", config.slippage_bps)
        fee = position_qty * px * config.fee_rate
        cash += position_qty * px - fee
        trades.append(
            TradeRecord(
                entry_time=entry_time,
                exit_time=close_time,
                side="long",
                entry_price=entry_price,
                exit_price=px,
                quantity=position_qty,
                pnl=round((px - entry_price) * position_qty - fee, 4),
                pnl_pct=round((px / entry_price - 1) * 100, 4) if entry_price else 0,
                fee=round(fee, 4),
            )
        )

    final_equity = cash
    total_ret = (final_equity / config.initial_cash - 1.0) * 100 if config.initial_cash else 0
    wins = [t for t in trades if (t.pnl or 0) > 0]
    win_rate = len(wins) / len(trades) if trades else None

    return BacktestResult(
        run_id=str(uuid.uuid4()),
        config_summary={
            "instrument_id": config.instrument_id,
            "symbol": config.symbol,
            "strategy": strategy_id,
            "strategy_version": registry.get(strategy_id).version if strategy_id != "buy_hold" else None,
            "strategy_params": strategy_params,
            "bars": len(bars),
            "fee_rate": config.fee_rate,
            "slippage_bps": config.slippage_bps,
        },
        engine="event",
        initial_cash=config.initial_cash,
        final_equity=round(final_equity, 4),
        total_return_pct=round(total_ret, 4),
        max_drawdown_pct=round(max_dd * 100, 4),
        trade_count=len(trades),
        win_rate=round(win_rate, 4) if win_rate is not None else None,
        trades=trades,
        equity_curve=equity_curve[:: max(1, len(equity_curve) // 200)],
        metrics={},
        pit_enforced=config.enforce_pit,
        warnings=warnings,
    )
