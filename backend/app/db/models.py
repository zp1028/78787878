"""PostgreSQL / SQLite schema for Smart Trader core entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Use generic JSON so the same models work on SQLite and PostgreSQL.
# On PostgreSQL you can later switch specific columns to JSONB via migration.
JSONType = JSON


class InstrumentRow(Base, TimestampMixin):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quote_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    base_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contract_type: Mapped[str] = mapped_column(String(32), default="unknown")
    tick_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str] = mapped_column(String(32), default="UTC")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    __table_args__ = (
        UniqueConstraint("symbol", "venue", name="uq_symbol_venue"),
        Index("ix_instruments_market_asset", "market", "asset_type"),
    )


class MarketSnapshotRow(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    published_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    venue: Mapped[str] = mapped_column(String(32), default="binance")

    __table_args__ = (
        Index("ix_market_snap_inst_avail", "instrument_id", "available_at"),
        Index("ix_market_snap_type_avail", "snapshot_type", "available_at"),
    )


class CandleRow(Base, TimestampMixin):
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False, default="binance")
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    open_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    close_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    source_timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("instrument_id", "timeframe", "open_time", name="uq_candle_inst_tf_open"),
        Index("ix_candles_inst_tf_time", "instrument_id", "timeframe", "open_time"),
    )


class FeatureSnapshotRow(Base):
    __tablename__ = "feature_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    computed_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    source_snapshot_ids: Mapped[list[Any]] = mapped_column(JSONType, default=list)

    __table_args__ = (
        UniqueConstraint("instrument_id", "timeframe", "available_at", name="uq_feature_inst_tf_avail"),
        Index("ix_feature_inst_avail", "instrument_id", "available_at"),
    )


class SignalRow(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_name: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    source_timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    generated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    __table_args__ = (
        Index("ix_signals_inst_time", "instrument_id", "generated_at"),
        Index("ix_signals_inst_name_time", "instrument_id", "signal_name", "generated_at"),
    )


class AIAnalysisRow(Base, TimestampMixin):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    completed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    evidence: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    available_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    __table_args__ = (
        Index("ix_ai_inst_avail", "instrument_id", "available_at"),
    )


class ObservationNodeRow(Base, TimestampMixin):
    __tablename__ = "observation_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_value: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class AnalysisReplayRow(Base):
    __tablename__ = "analysis_replays"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    analysis_time: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    market_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    feature_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    signals: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    ai_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    evidence: Mapped[list[Any]] = mapped_column(JSONType, default=list)
    risk: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    outcome: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
