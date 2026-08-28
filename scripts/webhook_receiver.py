"""Capture Razorpay webhook payloads as raw bytes after signature verification.

This receiver captures ONE event type by design — ``payment.captured`` — and
does not filter by event type itself. That filtering happens at the Razorpay
dashboard subscription config, which is a manual step outside this repo.
``payment.failed`` and other events are out of scope for this step and
unhandled if they arrive; they will still verify and be captured if the
dashboard sends them. This script does not discriminate by payload content,
only by signature validity. That is a real limitation.

Captured payloads in ``captures/`` are NOT redacted and NOT fixture material.
They must never be committed. Producing a committable fixture from a capture is
a separate, not-yet-built step — ``redact_payment()`` in ``fixture_redact.py``
operates on a flat Payment entity, not a webhook envelope, and cannot be called
on a capture file directly.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_VERIFY_SPEC = importlib.util.spec_from_file_location(
    "webhook_verify", Path(__file__).resolve().parent / "webhook_verify.py"
)
assert _VERIFY_SPEC is not None and _VERIFY_SPEC.loader is not None
_webhook_verify = importlib.util.module_from_spec(_VERIFY_SPEC)
_VERIFY_SPEC.loader.exec_module(_webhook_verify)
verify_webhook_signature = _webhook_verify.verify_webhook_signature


def handle_capture(
    raw_body: bytes,
    signature: str,
    secret: str,
    captures_dir: Path,
) -> tuple[int, Path | None]:
    """Verify signature and persist raw bytes plus a header sidecar on success."""
    if not secret:
        raise ValueError("secret must not be empty")

    captures_dir.mkdir(parents=True, exist_ok=True)

    if not verify_webhook_signature(raw_body, signature, secret):
        return (400, None)

    timestamp = int(time.time())
    raw_path = captures_dir / f"{timestamp}.raw"
    headers_path = captures_dir / f"{timestamp}.headers.json"

    raw_path.write_bytes(raw_body)
    headers_path.write_text(
        json.dumps(
            {
                "X-Razorpay-Signature": signature,
                "Content-Length": len(raw_body),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return (200, raw_path)


def make_handler(
    captures_dir: Path,
    secret: str,
) -> type[WebhookHandler]:
    class ConfiguredWebhookHandler(WebhookHandler):
        pass

    ConfiguredWebhookHandler.captures_dir = captures_dir
    ConfiguredWebhookHandler.secret = secret
    return ConfiguredWebhookHandler


class WebhookHandler(BaseHTTPRequestHandler):
    captures_dir: Path
    secret: str

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        signature = self.headers.get("X-Razorpay-Signature", "")

        status, _raw_path = handle_capture(
            raw_body,
            signature,
            self.secret,
            self.captures_dir,
        )
        body = "OK" if status == 200 else "REJECTED"

        # NEVER log raw_body, the signature header value, or the secret.
        print(f"{datetime.now(UTC).isoformat()} status={status} bytes={len(raw_body)}")

        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture Razorpay webhook payloads.")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--captures-dir",
        type=Path,
        default=PROJECT_ROOT / "captures",
        help="Directory for raw capture files (default: captures/ under repo root).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        print(
            "Missing or empty RAZORPAY_WEBHOOK_SECRET; refusing to start.",
            file=sys.stderr,
        )
        sys.exit(1)

    args = parse_args(argv)
    handler_class = make_handler(args.captures_dir.resolve(), secret)
    server = HTTPServer(("", args.port), handler_class)
    print(
        f"webhook receiver listening on port {args.port}, "
        f"captures_dir={args.captures_dir.resolve()}",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", file=sys.stderr)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
