"""Intent mandate: signed authorization to act within a scope."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contracts.scope import Scope


@dataclass(frozen=True)
class IntentMandate:
    mandate_id: str
    principal_id: str
    scope: Scope
    issued_at: datetime
    expires_at: datetime
    cart_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.mandate_id:
            raise ValueError("mandate_id must not be empty")
        if not self.principal_id:
            raise ValueError("principal_id must not be empty")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")
