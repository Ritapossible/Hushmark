"""The GitHub App's webhook server (ADR-0010).

    python -m hushmark.server

Standard library only. Each delivery's `X-Hub-Signature-256` is checked before the body is
parsed (`webhook_invalid` is answered with 401). GitHub waits at most 10 seconds for an
answer, and a review can take minutes, so the server answers 202 at once and one background
worker runs the reviews in order. A pull request already waiting in the queue is not queued
twice: when its turn comes, the review reads the latest head anyway.

Logs are one JSON object per line with the delivery ID, never diff content or finding text
(AGENTS.md rule 3).

Environment:
    HUSHMARK_APP_ID            the App's ID
    HUSHMARK_APP_PRIVATE_KEY   the App's private key (PEM; "\\n" escapes are accepted)
    HUSHMARK_WEBHOOK_SECRET    the webhook secret set on the App
    NEARAI_API_KEY             NEAR AI Cloud key (without it: `tee_unavailable`)
    NEAR_ANCHOR_ACCOUNT, NEAR_ANCHOR_KEY   optional NEAR testnet anchor
    HUSHMARK_DAILY_REVIEWS     model-calling reviews per repository per day (default 50)
    HUSHMARK_TOTAL_DAILY_REVIEWS   the same across all repositories (default 100)
    PORT, HOST                 default 8000 on every interface
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from hushmark.app import HushmarkApp, Job, route
from hushmark.github import GitHubApp, verify_webhook
from hushmark.pipeline import Reviewed
from hushmark.refusal import Refused

HOME = (
    "Hushmark GitHub App webhook server.\n"
    "GitHub sends pull request events to /webhook; /healthz says ok.\n"
    "About Hushmark: https://tryhushmark.vercel.app\n"
)
MAX_BODY = 25 * 1024 * 1024  # GitHub caps webhook payloads at 25 MB
SEEN_DELIVERIES = 10_000


def log(**fields: Any) -> None:
    """One JSON line. Callers pass IDs and codes only, never content."""
    print(json.dumps({"ts": int(time.time()), **fields}, sort_keys=True), flush=True)


class Deliveries:
    """Remembers recent delivery IDs, so a redelivered webhook is not reviewed twice."""

    def __init__(self, size: int = SEEN_DELIVERIES) -> None:
        self.size = size
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def first_time(self, delivery_id: str) -> bool:
        with self._lock:
            if delivery_id in self._seen:
                return False
            self._seen[delivery_id] = None
            if len(self._seen) > self.size:
                self._seen.popitem(last=False)
            return True


class Worker:
    """Runs reviews one at a time, off the request thread."""

    def __init__(self, handle: Callable[[Job], Any]) -> None:
        self.handle = handle
        self.jobs: queue.Queue[tuple[Job, str]] = queue.Queue()
        self._pending: set[tuple[int, int]] = set()
        self._lock = threading.Lock()

    def submit(self, job: Job, delivery_id: str) -> bool:
        """Queue a review. False when this pull request is already waiting."""
        with self._lock:
            if job.key in self._pending:
                return False
            self._pending.add(job.key)
        self.jobs.put((job, delivery_id))
        return True

    def run_one(self) -> None:
        job, delivery_id = self.jobs.get()
        with self._lock:
            self._pending.discard(job.key)
        ids = {"delivery_id": delivery_id, "repo_id": job.repo_id, "pr": job.number}
        try:
            result = self.handle(job)
        except Exception as e:  # keep serving; the check itself was closed by run_check
            log(event="review_failed", error=type(e).__name__, **ids)
            return
        if result is None:
            log(event="rerun_refused", code="not_maintainer", **ids)
            return
        outcome = result.outcome
        receipt_id = outcome.receipt.receipt_id if isinstance(outcome, Reviewed) else None
        log(
            event="reviewed",
            conclusion=result.output.conclusion,
            refusal=getattr(outcome, "code", None),
            refusal_detail=getattr(outcome, "detail", None),
            receipt_id=receipt_id,
            **ids,
        )

    def forever(self) -> None:
        while True:
            self.run_one()


def make_handler(
    secret: bytes, worker: Worker, deliveries: Deliveries
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "Hushmark"
        sys_version = ""

        def _reply(self, status: int, body: str, head: bool = False) -> None:
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not head:
                self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # our own JSON log instead; the default one would print request lines

        def _get(self, head: bool) -> None:
            if self.path == "/healthz":
                self._reply(200, "ok\n", head)
            elif self.path == "/":
                self._reply(200, HOME, head)
            else:
                self._reply(404, "not found\n", head)

        def do_GET(self) -> None:
            self._get(head=False)

        def do_HEAD(self) -> None:
            # Uptime monitors (UptimeRobot's free plan) check with HEAD; without this the
            # standard library answers 501 and the monitor reports the server as down.
            self._get(head=True)

        def do_POST(self) -> None:
            if self.path != "/webhook":
                self._reply(404, "not found\n")
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                self._reply(413 if length > MAX_BODY else 400, "bad length\n")
                return
            body = self.rfile.read(length)
            delivery_id = self.headers.get("X-GitHub-Delivery") or ""
            try:
                verify_webhook(secret, body, self.headers.get("X-Hub-Signature-256"))
            except Refused as e:
                log(event="webhook_refused", code=e.code, delivery_id=delivery_id)
                self._reply(401, f"{e.code}\n")
                return
            event = self.headers.get("X-GitHub-Event") or ""
            if delivery_id and not deliveries.first_time(delivery_id):
                self._reply(200, "duplicate\n")
                return
            try:
                job = route(event, json.loads(body))
            except (ValueError, KeyError, TypeError):
                log(event="payload_invalid", gh_event=event, delivery_id=delivery_id)
                self._reply(400, "payload_invalid\n")
                return
            if job is None:
                self._reply(200, "ignored\n")
                return
            queued = worker.submit(job, delivery_id)
            log(
                event="queued" if queued else "already_queued",
                trigger=job.trigger,
                delivery_id=delivery_id,
                repo_id=job.repo_id,
                pr=job.number,
            )
            self._reply(202, "queued\n" if queued else "already queued\n")

    return Handler


def private_key(env: Mapping[str, str]) -> str:
    return env["HUSHMARK_APP_PRIVATE_KEY"].replace("\\n", "\n")


def main() -> int:
    env = os.environ
    app = HushmarkApp(GitHubApp(env["HUSHMARK_APP_ID"], private_key(env)), env)
    worker = Worker(app.handle)
    threading.Thread(target=worker.forever, name="reviews", daemon=True).start()
    handler = make_handler(env["HUSHMARK_WEBHOOK_SECRET"].encode(), worker, Deliveries())
    port = int(env.get("PORT") or 8000)
    log(event="started", port=port, model=app.model, anchor=app.anchor is not None)
    # A hosted webhook server must listen on every interface; HOST narrows it if needed.
    host = env.get("HOST") or "0.0.0.0"  # noqa: S104
    ThreadingHTTPServer((host, port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
