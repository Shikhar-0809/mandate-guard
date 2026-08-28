"""T2 configuration: enable flag and ambiguous score band for verifier eligibility.

T2Config controls whether the LLM semantic verifier is invoked and defines the
ambiguous score band [tau_low, tau_high] in which T2 is eligible to run. Default
t2_enabled=False reflects the pre-registered kill criterion outcome documented
in D008 and EVAL.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class T2Config:
    t2_enabled: bool = False
    tau_low: float = 0.3
    tau_high: float = 0.7

    def __post_init__(self) -> None:
        if not (0.0 <= self.tau_low <= 1.0):
            raise ValueError("tau_low must be in [0.0, 1.0]")
        if not (0.0 <= self.tau_high <= 1.0):
            raise ValueError("tau_high must be in [0.0, 1.0]")
        if self.tau_low >= self.tau_high:
            raise ValueError("tau_low must be strictly less than tau_high")
