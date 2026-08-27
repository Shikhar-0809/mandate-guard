"""Loopback Razorpay Checkout harness to capture a test-mode payment fixture.

Test card: 5267 3181 8797 5449 (OTP 1111). Do not use 4111 1111 1111 1111 —
classified international on this account.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import razorpay
from dotenv import load_dotenv
from razorpay.errors import SignatureVerificationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DIR = PROJECT_ROOT / ".local"
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
HOST = "127.0.0.1"
PORT = 5000
TIMEOUT_SECONDS = 900
ORDER_AMOUNT = 123456

_REDACT_SPEC = importlib.util.spec_from_file_location(
    "fixture_redact", Path(__file__).resolve().parent / "fixture_redact.py"
)
assert _REDACT_SPEC is not None and _REDACT_SPEC.loader is not None
_fixture_redact = importlib.util.module_from_spec(_REDACT_SPEC)
_REDACT_SPEC.loader.exec_module(_fixture_redact)
redact_payment = _fixture_redact.redact_payment


@dataclass
class CheckoutState:
    client: razorpay.Client
    key_id: str
    order_id: str
    order_amount: int
    finished: bool = False
    exit_code: int = 1


STATE: CheckoutState | None = None


def load_client() -> tuple[razorpay.Client, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise SystemExit("Missing RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET in .env")
    return razorpay.Client(auth=(key_id, key_secret)), key_id


def checkout_html(key_id: str, order: dict[str, Any]) -> str:
    order_id = order["id"]
    amount = order["amount"]
    currency = order["currency"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>mandate-guard checkout</title></head>
<body>
<p>Order {order_id} — INR {amount / 100:.2f}</p>
<button id="pay" type="button">Pay with Razorpay</button>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
const options = {{
  key: {json.dumps(key_id)},
  amount: {json.dumps(amount)},
  currency: {json.dumps(currency)},
  order_id: {json.dumps(order_id)},
  // Deliberately fake test-harness prefill; contact/email land on the payment
  // object and are dropped by redact_payment().
  prefill: {{
    name: "Test Buyer",
    email: "buyer@example.invalid",
    contact: "9000090000",
  }},
  handler: function (response) {{
    fetch("/callback", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify(response),
    }}).then(function (res) {{ return res.text(); }}).then(function (text) {{
      document.body.insertAdjacentHTML("beforeend", "<pre>" + text + "</pre>");
    }});
  }},
}};
const rzp = new Razorpay(options);
rzp.on("payment.failed", function (response) {{
  fetch("/failed", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(response.error),
  }});
}});
document.getElementById("pay").addEventListener("click", function () {{
  rzp.open();
}});
</script>
</body>
</html>"""


class CheckoutHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("expected JSON object")
        return payload

    def do_GET(self) -> None:
        if urlparse(self.path).path != "/":
            self.send_error(404)
            return
        assert STATE is not None
        body = checkout_html(
            STATE.key_id,
            {
                "id": STATE.order_id,
                "amount": STATE.order_amount,
                "currency": "INR",
            },
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        assert STATE is not None
        path = urlparse(self.path).path
        if path == "/callback":
            self._handle_callback()
            return
        if path == "/failed":
            self._handle_failed()
            return
        self.send_error(404)

    def _handle_callback(self) -> None:
        assert STATE is not None
        try:
            payload = self._read_json_body()
            STATE.client.utility.verify_payment_signature(payload)
        except (SignatureVerificationError, KeyError, TypeError):
            print("FAIL signature")
            STATE.finished = True
            STATE.exit_code = 1
            self._respond(400, "FAIL signature\n")
            return

        print("signature: VERIFIED")
        payment_id = str(payload["razorpay_payment_id"])
        payment = STATE.client.payment.fetch(payment_id)
        if payment["status"] == "authorized":
            print("capture: performed")
            STATE.client.payment.capture(payment_id, STATE.order_amount)
            payment = STATE.client.payment.fetch(payment_id)
        else:
            print("capture: skipped (already captured)")

        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = LOCAL_DIR / "payment_raw.json"
        raw_path.write_text(json.dumps(payment, indent=2) + "\n", encoding="utf-8")

        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        redacted = redact_payment(payment)
        fixture_path = FIXTURES_DIR / "payment_success.json"
        fixture_path.write_text(json.dumps(redacted, indent=2) + "\n", encoding="utf-8")

        print(
            "PASS payment: "
            f"{payment['id']} status={payment['status']} "
            f"amount={payment['amount']} order={payment['order_id']}"
        )
        STATE.finished = True
        STATE.exit_code = 0
        self._respond(200, "payment captured\n")

    def _handle_failed(self) -> None:
        assert STATE is not None
        try:
            error = self._read_json_body()
            code = error.get("code", "<unknown>")
            description = error.get("description", "<unknown>")
        except (json.JSONDecodeError, TypeError):
            code = "<unknown>"
            description = "<unknown>"
        print(f"payment failed (retryable): {code} {description}")
        print("server still listening — retry in the browser")
        self._respond(200, "payment failed (retryable)\n")

    def _respond(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    global STATE
    client, key_id = load_client()
    receipt = f"mg-step5-{int(datetime.now(UTC).timestamp())}"
    order = client.order.create(
        data={
            "amount": ORDER_AMOUNT,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
        }
    )
    print(order["id"])

    STATE = CheckoutState(
        client=client,
        key_id=key_id,
        order_id=order["id"],
        order_amount=ORDER_AMOUNT,
    )

    server = HTTPServer((HOST, PORT), CheckoutHandler)
    server.timeout = 1
    deadline = time.monotonic() + TIMEOUT_SECONDS
    print(f"checkout: http://{HOST}:{PORT}/ (timeout {TIMEOUT_SECONDS}s)")

    try:
        while not STATE.finished and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()

    if not STATE.finished:
        print(f"FAIL timeout: no payment within {TIMEOUT_SECONDS} seconds")
        raise SystemExit(1)

    raise SystemExit(STATE.exit_code)


if __name__ == "__main__":
    main()
