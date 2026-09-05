"""FastAPI demo endpoint for mandate-guard. Local demo only -- not for
production traffic. Reuses the same record-dict shape and conversion
logic (_record_to_t0_args) that the eval pipeline already uses, so the
API is not a second, divergent implementation of contract construction."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from contracts import T2Config
from mandate_guard.cascade import check as cascade_check
from mandate_guard.eval import _record_to_t0_args

MODEL_DIR = PROJECT_ROOT / "models"
DEMO_TAU = 0.220  # full-intent dev tau_star, verified this session

app = FastAPI(title="mandate-guard demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckRequest(BaseModel):
    record: dict[str, Any]
    enable_t2: bool = False


class CheckResponse(BaseModel):
    verdict: str
    reason_code: str
    t0_triggered: bool
    t1_score: float | None
    t2_evidence: str | None
    tau_used: float
    t2_enabled: bool


@app.post("/check", response_model=CheckResponse)
def check_transaction(payload: CheckRequest) -> CheckResponse:
    record = dict(payload.record)
    record.setdefault("delegation_token_id", None)
    try:
        args = _record_to_t0_args(record)
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Malformed record: {exc}") from exc

    args["now"] = datetime.now()
    t2_config = T2Config(t2_enabled=payload.enable_t2)

    verdict = cascade_check(
        intent=args["intent"],
        cart=args["cart"],
        token=args["token"],
        transaction_amount=args["transaction_amount"],
        merchant_id=args["merchant_id"],
        mcc=args["mcc"],
        now=args["now"],
        agent_request_id=str(record.get("record_id", "demo")),
        model_dir=MODEL_DIR,
        tau=DEMO_TAU,
        t2_config=t2_config,
    )

    return CheckResponse(
        verdict=verdict.verdict.value,
        reason_code=verdict.reason_code,
        t0_triggered=verdict.t0_triggered,
        t1_score=verdict.t1_score,
        t2_evidence=verdict.t2_evidence,
        tau_used=DEMO_TAU,
        t2_enabled=payload.enable_t2,
    )


web_dir = PROJECT_ROOT / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
