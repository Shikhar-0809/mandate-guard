"""T1 scorer output: calibrated probability or explicit intent-absent sentinel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class T1Result:
    score: float | None
    intent_present: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.intent_present:
            if self.score is None:
                raise ValueError("score must not be None when intent_present is True")
            if not (0.0 <= self.score <= 1.0):
                raise ValueError("score must be in [0.0, 1.0]")
            if self.reason is not None:
                raise ValueError("reason must be None when intent_present is True")
        else:
            if self.score is not None:
                raise ValueError("score must be None when intent_present is False")
            if self.reason != "INTENT_ABSENT":
                raise ValueError('reason must be "INTENT_ABSENT" when intent_present is False')
