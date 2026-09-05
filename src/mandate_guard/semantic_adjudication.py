"""Semantic adjudication rules for M1 corpus label assignment."""

from __future__ import annotations

import math
from typing import Literal

Label = Literal["ALLOW", "DEVIATION", "UNCERTAIN"]
ToleranceState = Literal["WITHIN", "BOUNDARY", "OUTSIDE"]


def tolerance_state(
    ratio: float,
    within: float = 0.10,
    boundary: float = 0.20,
) -> ToleranceState:
    """
    ratio is observed_value / intent_value (amount or quantity).
    diff = abs(ratio - 1.0).
    WITHIN if diff <= within (default +/-10%).
    BOUNDARY if within < diff <= boundary (default +/-10-20%).
    OUTSIDE if diff > boundary.
    These constants (0.10, 0.20) are NEW, specific to this corpus,
    deliberately NOT reused from hn_price_drift's 1-2% (too narrow,
    models "obviously fine" not general tolerance) or from
    quantity_mismatch's [0.5, 2.0] flag band (too wide, models
    "obviously wrong" not "genuinely fine"). Do not change these
    defaults without a DECISIONS.md entry.
    """
    diff = abs(ratio - 1.0)
    if diff <= within or math.isclose(diff, within, rel_tol=0.0, abs_tol=1e-12):
        return "WITHIN"
    if diff <= boundary or math.isclose(diff, boundary, rel_tol=0.0, abs_tol=1e-12):
        return "BOUNDARY"
    return "OUTSIDE"


def combined_tolerance_state(
    amount_ratio: float,
    quantity_ratio: float,
) -> ToleranceState:
    """Worse of the two states: OUTSIDE > BOUNDARY > WITHIN."""
    amount_state = tolerance_state(amount_ratio)
    quantity_state = tolerance_state(quantity_ratio)
    if amount_state == "OUTSIDE" or quantity_state == "OUTSIDE":
        return "OUTSIDE"
    if amount_state == "BOUNDARY" or quantity_state == "BOUNDARY":
        return "BOUNDARY"
    return "WITHIN"


def _split_path(leaf: str) -> list[str]:
    return leaf.split(" > ")


def adjudicate(
    intent_leaf: str,
    cart_leaf: str,
    amount_ratio: float,
    quantity_ratio: float,
    rationale_present: bool,
) -> Label:
    """
    intent_leaf / cart_leaf are full " > "-delimited taxonomy leaf
    strings from taxonomy.TAXONOMY_LEAVES (e.g.
    "Electronics > Audio > Speaker"). Split on " > " to get path
    segments; compare path[0] for top-level, path[:2] for immediate
    parent, full path for leaf identity.

    Rule (evaluated in this order — first match wins):

    1. Cross-top-level (path_a[0] != path_b[0]) -> DEVIATION.
       Per D053 clause 1, unconditional on tolerance/rationale.

    2. Same leaf (path_a == path_b):
         WITHIN   -> ALLOW
         BOUNDARY -> UNCERTAIN
         OUTSIDE  -> DEVIATION
       [D054 gap-fill #1: D053 doesn't explicitly name "same leaf,
        amount grossly off" — resolved as DEVIATION since an
        identical SKU at a wildly different amount/quantity is an
        amount manipulation on a real SKU, not an ambiguous
        substitution question; nothing for a human to be uncertain
        about since the leaf matches exactly.]

    3. Same immediate parent, different leaf (sibling):
         no rationale_present -> DEVIATION (regardless of tolerance)
           [D053 clause 2, literal and unconditional]
         rationale_present:
           WITHIN   -> ALLOW
           BOUNDARY -> UNCERTAIN
           OUTSIDE  -> UNCERTAIN
             [D054 gap-fill #2: rationale claims legitimate
              substitution but amount doesn't support it -- mixed
              signal, genuinely ambiguous, not clean fraud since a
              rationale is stated, not clean ALLOW since amount is
              off.]

    4. Same top-level, different immediate parent (neither same
       leaf nor sibling) -> UNCERTAIN.
       [This is NOT a gap-fill -- this is the direct textual match
        for D053's UNCERTAIN definition: structurally outside both
        ALLOW's condition (a) and both DEVIATION disjuncts, i.e.
        exactly "a human reviewer cannot confidently apply (a)-(c)
        without more context than the record provides."]
    """
    path_a = _split_path(intent_leaf)
    path_b = _split_path(cart_leaf)
    tolerance = combined_tolerance_state(amount_ratio, quantity_ratio)

    if path_a[0] != path_b[0]:
        return "DEVIATION"

    if path_a == path_b:
        if tolerance == "WITHIN":
            return "ALLOW"
        if tolerance == "BOUNDARY":
            return "UNCERTAIN"
        return "DEVIATION"

    if path_a[:2] == path_b[:2]:
        if not rationale_present:
            return "DEVIATION"
        if tolerance == "WITHIN":
            return "ALLOW"
        return "UNCERTAIN"

    return "UNCERTAIN"
