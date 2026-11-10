"""
Detector for Duplicate In-Flight Requests, Debounce Failures, and UI Race Conditions.
Intercepts network requests to detect when multiple identical mutations are triggered in close succession.
"""

from __future__ import annotations
import hashlib
import time
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, BrowserContext, Request
from chaosui.detectors.base import BaseDetector
from chaosui.core.models import FaultRecord, FaultType, Severity, ActionRecord
from chaosui.core.session import ChaosSession


class DuplicateRequestDetector(BaseDetector):
    """Detects multiple identical or concurrent state-mutating requests (POST, PUT, PATCH, DELETE)."""

    def __init__(self, window_ms: int = 2500):
        super().__init__("duplicate_request_detector")
        self.window_ms = window_ms
        self.request_history: List[Dict[str, Any]] = []
        self.reported_keys: set[str] = set()
        self.last_action: Optional[ActionRecord] = None

    async def attach(self, page: Page, context: BrowserContext, session: ChaosSession) -> None:
        await super().attach(page, context, session)

        # Hook into page requests
        page.on("request", self._handle_request)

    async def on_action_start(self, action: ActionRecord) -> None:
        self.last_action = action

    def _handle_request(self, request: Request) -> None:
        method = request.method.upper()
        # Only watch state-mutating methods by default
        if method not in ("POST", "PUT", "PATCH", "DELETE"):
            return

        url = request.url
        post_data = request.post_data or ""
        post_hash = hashlib.sha256(post_data.encode("utf-8")).hexdigest()[:12] if post_data else "EMPTY"
        req_time = time.time()

        self.request_history.append(
            {
                "method": method,
                "url": url,
                "post_data": post_data[:200],  # truncated snippet
                "post_hash": post_hash,
                "timestamp": req_time,
                "action": self.last_action.description if self.last_action else "Unknown action",
            }
        )

        if self.session:
            self.session.metrics["total_requests"] += 1

    async def check(self) -> List[FaultRecord]:
        if not self.session:
            return []

        now = time.time()
        window_seconds = self.window_ms / 1000.0
        faults: List[FaultRecord] = []

        # Prune very old history
        self.request_history = [r for r in self.request_history if now - r["timestamp"] <= 30.0]

        # Group requests by (method, url, post_hash)
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for req in self.request_history:
            key = f"{req['method']}:{req['url']}:{req['post_hash']}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(req)

        # Check for groups with multiple occurrences within window_seconds
        for key, reqs in grouped.items():
            if len(reqs) < 2:
                continue

            # Sort by timestamp
            reqs.sort(key=lambda x: x["timestamp"])

            # Check consecutive requests
            for i in range(len(reqs) - 1):
                first = reqs[i]
                second = reqs[i + 1]
                delta_ms = round((second["timestamp"] - first["timestamp"]) * 1000, 1)

                if delta_ms <= self.window_ms:
                    incident_id = f"{key}:{round(first['timestamp'], 2)}"
                    if incident_id in self.reported_keys:
                        continue

                    self.reported_keys.add(incident_id)

                    method = first["method"]
                    url = first["url"]
                    url_lower = url.lower()

                    # Determine severity based on criticality of endpoint
                    critical_keywords = ("pay", "checkout", "order", "charge", "transfer", "subscribe", "buy", "cart")
                    if any(kw in url_lower for kw in critical_keywords):
                        severity = Severity.CRITICAL
                        title = f"CRITICAL: Duplicate Transactional Request to {url}"
                    else:
                        severity = Severity.HIGH
                        title = f"Duplicate {method} Request Detected ({delta_ms}ms gap)"

                    desc = (
                        f"Detected {len(reqs)} duplicate {method} requests dispatched within {delta_ms}ms "
                        f"to '{url}' without debounce or form disabling. "
                        f"Triggered after: '{second.get('action')}'."
                    )

                    fault = self.session.record_fault(
                        fault_type=FaultType.DUPLICATE_REQUEST,
                        severity=severity,
                        title=title,
                        description=desc,
                        evidence={
                            "method": method,
                            "url": url,
                            "gap_ms": delta_ms,
                            "window_ms": self.window_ms,
                            "duplicate_count": len(reqs),
                            "payload_preview": first.get("post_data"),
                            "correlated_action": second.get("action"),
                        },
                    )
                    faults.append(fault)

        return faults
