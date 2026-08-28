"""Delegation token: narrowed scope derived from a parent mandate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contracts.scope import Scope


@dataclass(frozen=True)
class DelegationToken:
    token_id: str
    parent_mandate_id: str
    delegated_scope: Scope
    parent_scope: Scope
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not self.token_id:
            raise ValueError("token_id must not be empty")
        if not self.parent_mandate_id:
            raise ValueError("parent_mandate_id must not be empty")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")

    def is_valid_delegation(self) -> bool:
        return self.parent_scope.contains(self.delegated_scope)
