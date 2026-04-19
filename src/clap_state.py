from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClapDecision(str, Enum):
    NONE = "none"
    ACCEPTED = "accepted"
    DOUBLE_CLAP = "double_clap"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ClapEvent:
    decision: ClapDecision
    clap_count: int
    state: str
    reason: str | None = None


class DoubleClapStateMachine:
    """
    Pure clap state logic, independent from audio I/O.

    Rules:
    - ignore hits inside min_interval cooldown
    - reset first clap when gap exceeds max_interval
    - emit DOUBLE_CLAP on second valid clap
    """

    def __init__(self, min_interval: float, max_interval: float):
        self.min_interval = float(min_interval)
        self.max_interval = float(max_interval)
        self.reset()

    def reset(self) -> None:
        self.last_clap_at = -float("inf")
        self.clap_count = 0
        self.state = "IDLE"

    def on_tick(self, now: float) -> ClapEvent:
        if self.clap_count > 0 and (now - self.last_clap_at) > self.max_interval:
            self.reset()
        return ClapEvent(ClapDecision.NONE, self.clap_count, self.state)

    def reject(self, reason: str) -> ClapEvent:
        self.state = "REJECTED"
        return ClapEvent(ClapDecision.REJECTED, self.clap_count, self.state, reason=reason)

    def register_clap(self, now: float) -> ClapEvent:
        if (now - self.last_clap_at) < self.min_interval:
            return ClapEvent(ClapDecision.NONE, self.clap_count, self.state, reason="min_interval")

        if (now - self.last_clap_at) > self.max_interval:
            self.clap_count = 1
        else:
            self.clap_count += 1

        self.last_clap_at = now

        if self.clap_count >= 2:
            self.reset()
            return ClapEvent(ClapDecision.DOUBLE_CLAP, 0, "IDLE")

        self.state = "WAITING"
        return ClapEvent(ClapDecision.ACCEPTED, self.clap_count, self.state)
