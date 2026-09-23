"""Risk Engine — independent gate between AI/Strategy and any execution.

AI may only propose. This module validates against account limits and
returns approve / reject / adjusted. Cannot be bypassed by upper layers.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.event_bus import EventBus
from app.core.events import RiskChangedEvent
from app.risk.models import (
    AccountState,
    RiskDecision,
    RiskLimits,
    RiskViolation,
    TradeProposal,
)


class RiskEngine:
    def __init__(
        self,
        bus: EventBus | None = None,
        limits: RiskLimits | None = None,
        account: AccountState | None = None,
    ):
        self.bus = bus
        self.limits = limits or RiskLimits()
        self.account = account or AccountState()
        self._last_decision: RiskDecision | None = None
        self._halted = False
        self._session_start_equity = self.account.equity

    def update_account(self, **kwargs: Any) -> None:
        data = self.account.model_dump()
        data.update(kwargs)
        self.account = AccountState(**data)

    def set_limits(self, limits: RiskLimits) -> None:
        self.limits = limits

    def reset_session(self) -> None:
        self._session_start_equity = self.account.equity
        self._halted = False

    def validate(self, proposal: TradeProposal) -> RiskDecision:
        now = int(time.time() * 1000)
        violations: list[RiskViolation] = []
        metrics: dict[str, Any] = {}
        adjusted = proposal.model_copy(deep=True)

        equity = max(self.account.equity, 1e-9)
        metrics["equity"] = equity

        # --- account loss halt ---
        session_loss_pct = (self._session_start_equity - equity) / max(
            self._session_start_equity, 1e-9
        )
        metrics["session_loss_pct"] = round(session_loss_pct, 4)
        if session_loss_pct >= self.limits.max_account_loss_pct or self._halted:
            self._halted = True
            violations.append(
                RiskViolation(
                    code="ACCOUNT_LOSS_HALT",
                    message=f"session loss {session_loss_pct:.2%} >= limit "
                    f"{self.limits.max_account_loss_pct:.2%}",
                    severity="block",
                )
            )

        # --- side ---
        if proposal.side == "short" and not self.limits.allow_short:
            violations.append(
                RiskViolation(
                    code="SHORT_NOT_ALLOWED",
                    message="short selling disabled by risk policy",
                    severity="block",
                )
            )

        if proposal.side == "flat":
            decision = RiskDecision(
                approved=True,
                proposal=proposal,
                adjusted=adjusted,
                violations=violations,
                risk_score=0.0,
                metrics=metrics,
                checked_at=now,
            )
            self._last_decision = decision
            return decision

        # --- leverage ---
        lev = max(proposal.leverage, 1.0)
        metrics["leverage"] = lev
        if lev > self.limits.max_leverage:
            violations.append(
                RiskViolation(
                    code="LEVERAGE_EXCEEDED",
                    message=f"leverage {lev} > max {self.limits.max_leverage}",
                    severity="block",
                )
            )
            adjusted.leverage = self.limits.max_leverage

        # --- position size ---
        entry = proposal.entry_price or 0.0
        pos_pct = proposal.position_pct
        if pos_pct is None and proposal.quantity and entry > 0:
            notional = proposal.quantity * entry
            pos_pct = notional / equity
        if pos_pct is None:
            pos_pct = 0.05  # default small
        metrics["requested_position_pct"] = pos_pct

        if pos_pct > self.limits.max_position_pct:
            violations.append(
                RiskViolation(
                    code="MAX_POSITION",
                    message=f"position {pos_pct:.2%} > max {self.limits.max_position_pct:.2%}",
                    severity="block",
                )
            )
            adjusted.position_pct = self.limits.max_position_pct
            if entry > 0:
                adjusted.quantity = (equity * self.limits.max_position_pct) / entry

        # --- portfolio exposure ---
        existing = 0.0
        for p in self.account.open_positions:
            existing += abs(float(p.get("notional") or 0)) / equity
        new_notional_pct = (adjusted.position_pct or pos_pct) * lev
        gross = existing + new_notional_pct
        metrics["gross_exposure_pct"] = round(gross, 4)
        if gross > self.limits.max_portfolio_exposure_pct:
            violations.append(
                RiskViolation(
                    code="PORTFOLIO_EXPOSURE",
                    message=f"gross exposure {gross:.2%} > max "
                    f"{self.limits.max_portfolio_exposure_pct:.2%}",
                    severity="block",
                )
            )

        # --- stop distance ---
        if proposal.stop_price is not None and entry > 0:
            stop_dist = abs(entry - proposal.stop_price) / entry
            metrics["stop_distance_pct"] = round(stop_dist, 4)
            if stop_dist < self.limits.min_stop_distance_pct:
                violations.append(
                    RiskViolation(
                        code="STOP_TOO_TIGHT",
                        message=f"stop {stop_dist:.2%} < min "
                        f"{self.limits.min_stop_distance_pct:.2%}",
                        severity="block",
                    )
                )
            if stop_dist > self.limits.max_stop_distance_pct:
                violations.append(
                    RiskViolation(
                        code="STOP_TOO_WIDE",
                        message=f"stop {stop_dist:.2%} > max "
                        f"{self.limits.max_stop_distance_pct:.2%}",
                        severity="warn",
                    )
                )
                # auto-clip stop
                if proposal.side == "long":
                    adjusted.stop_price = entry * (1 - self.limits.max_stop_distance_pct)
                else:
                    adjusted.stop_price = entry * (1 + self.limits.max_stop_distance_pct)

        # --- risk score heuristic ---
        risk_score = 0.0
        risk_score += min(1.0, (pos_pct / max(self.limits.max_position_pct, 1e-9))) * 0.35
        risk_score += min(1.0, lev / max(self.limits.max_leverage, 1e-9)) * 0.25
        risk_score += min(1.0, gross / max(self.limits.max_portfolio_exposure_pct, 1e-9)) * 0.25
        if session_loss_pct > 0:
            risk_score += min(1.0, session_loss_pct / max(self.limits.max_account_loss_pct, 1e-9)) * 0.15
        risk_score = round(min(1.0, risk_score), 4)
        metrics["risk_score"] = risk_score

        blocks = [v for v in violations if v.severity == "block"]
        approved = len(blocks) == 0

        # if blocked only by size/leverage, still offer adjusted when clipped
        if not approved and adjusted.position_pct and adjusted.position_pct <= self.limits.max_position_pct:
            # re-check if only max_position / leverage were issues — still not auto-approve
            pass

        decision = RiskDecision(
            approved=approved,
            proposal=proposal,
            adjusted=adjusted if not approved else adjusted,
            violations=violations,
            risk_score=risk_score,
            metrics=metrics,
            checked_at=now,
        )
        self._last_decision = decision
        return decision

    async def validate_and_publish(self, proposal: TradeProposal) -> RiskDecision:
        decision = self.validate(proposal)
        if self.bus:
            await self.bus.publish(
                RiskChangedEvent(
                    account_id=self.account.account_id,
                    risk_level="halt" if self._halted else ("high" if decision.risk_score > 0.7 else "normal"),
                    metrics=decision.metrics,
                    changed_at=decision.checked_at,
                )
            )
        return decision

    @property
    def last_decision(self) -> RiskDecision | None:
        return self._last_decision

    @property
    def is_halted(self) -> bool:
        return self._halted
