"""Point-in-Time filter — the hard integrity rule for all historical analysis.

Rule:
    A data record may only be used in an analysis if
        record.available_at <= analysis_time

Never use source_timestamp / published_at alone. Those can be in the past
relative to when the data actually became available (news lag, revised
macro prints, delayed fundamentals, etc.).
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, TypeVar


class HasAvailableAt(Protocol):
    available_at: int


T = TypeVar("T", bound=HasAvailableAt)


def is_available(record: HasAvailableAt, analysis_time: int) -> bool:
    """Return True if the record was legally usable at analysis_time (ms)."""
    return record.available_at <= analysis_time


def filter_available(records: Sequence[T], analysis_time: int) -> list[T]:
    """Keep only records that satisfy the PIT constraint."""
    return [r for r in records if is_available(r, analysis_time)]


def assert_no_lookahead(
    records: Sequence[HasAvailableAt],
    analysis_time: int,
    *,
    context: str = "",
) -> None:
    """Raise if any record violates PIT. Use in tests and backtest guards."""
    violators = [r for r in records if not is_available(r, analysis_time)]
    if violators:
        sample = violators[0]
        raise ValueError(
            f"Look-ahead detected{(' in ' + context) if context else ''}: "
            f"available_at={sample.available_at} > analysis_time={analysis_time} "
            f"({len(violators)} violator(s))"
        )


def pit_slice(
    records: Sequence[dict[str, Any]],
    analysis_time: int,
    *,
    available_key: str = "available_at",
) -> list[dict[str, Any]]:
    """Convenience for raw dict payloads (e.g. JSONB rows)."""
    return [r for r in records if int(r.get(available_key, 0)) <= analysis_time]
