"""
Detector for Duplicate In-Flight Requests, Debounce Failures, and UI Race Conditions.
Intercepts network requests to detect when multiple identical mutations are triggered in close succession.
"""

from __future__ import annotations
from collections import deque
import hashlib
import time
from typing import Deque, List, Dict, Any
from playwright.async_api import Page, BrowserContext, Request
from chaosui.detectors.base import BaseDetector
from chaosui.core.models import FaultRecord, FaultType, Severity
from chaosui.core.session import ChaosSession


class DuplicateRequestDetector(BaseDetector):
    """Detects multiple identical or concurrent state-mutating requests (POST, PUT, PATCH, DELETE)."""

    def __init__(self, window_ms: int = 2500, max_history: int = 500):
        super().__init__("duplicate_request_detector")
        self.window_ms = window_ms
        self.request_history: Deque[Dict[str, Any]] = deque(maxlen=max_history)
        self.reported_keys: set[str] = set()

    async def attach(self, page: Page, context: BrowserContext, session: ChaosSession) -> None:
        await super().attach(page, context, session)
        page.on("request", self._handle_request)

    async def detach(self) -> None:
        if self.page:
            try:
                self.page.remove_listener("request", self._handle_request)
            except Exception:
                pass
        await super().detach()

    def _extract_payload_info(self, request: Request) -> tuple[str, str]:
        """Safely extracts a preview string and hash even for binary payloads."""
        try:
            post_data = request.post_data or ""
            post_hash = hashlib.sha256(post_data.encode("utf-8", errors="replace")).hexdigest()[:12] if post_data else "EMPTY"
            return post_data[:200], post_hash
        except Exception:
            try:
                buf = request.post_data_buffer or b""
                post_hash = hashlib.sha256(buf).hexdigest()[:12] if buf else "EMPTY"
                return f"<binary {len(buf)} bytes>", post_hash
            except Exception:
                return "", "EMPTY"

    def _handle_request(self, request: Request) -> None:
        method = request.method.upper()
        # Only watch state-mutating methods by default
        if method not in ("POST", "PUT", "PATCH", "DELETE"):
            return

        url = request.url
        preview, post_hash = self._extract_payload_info(request)
        req_time = time.time()

        self.request_history.append(
            {
                "method": method,
                "url": url,
                "post_data": preview,
                "post_hash": post_hash,
                "timestamp": req_time,
                "action": self.current_action_description,
            }
        )

        if self.session:
            self.session.metrics["total_requests"] += 1

    async def check(self) -> List[FaultRecord]:
        if not self.session:
            return []

        now = time.time()
        faults: List[FaultRecord] = []

        # Prune stale entries older than 30s from the left of the deque
        while self.request_history and (now - self.request_history[0]["timestamp"]) > 30.0:
            self.request_history.popleft()

        # Group requests by (method, url, post_hash)
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for req in list(self.request_history):
            key = f"{req['method']}:{req['url']}:{req['post_hash']}"
            grouped.setdefault(key, []).append(req)

        # Check for groups with multiple occurrences within window_ms
        for key, reqs in grouped.items():
            if len(reqs) < 2:
                continue

            reqs.sort(key=lambda x: x["timestamp"])

            # Cluster requests whose consecutive gaps fall within window_ms
            cluster: List[Dict[str, Any]] = [reqs[0]]
            for req in reqs[1:]:
                gap_ms = round((req["timestamp"] - cluster[-1]["timestamp"]) * 1000, 1)
                if gap_ms <= self.window_ms:
                    cluster.append(req)
                else:
                    if len(cluster) >= 2:
                        self._maybe_report_cluster(key, cluster, faults)
                    cluster = [req]

            if len(cluster) >= 2:
                self._maybe_report_cluster(key, cluster, faults)

        return faults

    def _maybe_report_cluster(
        self,
        key: str,
        cluster: List[Dict[str, Any]],
        faults: List[FaultRecord],
    ) -> None:
        if not self.session:
            return

        first = cluster[0]
        second = cluster[1]
        last = cluster[-1]
        delta_ms = round((second["timestamp"] - first["timestamp"]) * 1000, 1)

        # Deduplicate per burst based on the first request timestamp in the cluster
        incident_id = f"{key}:{round(first['timestamp'], 2)}:{len(cluster)}"
        base_id = f"{key}:{round(first['timestamp'], 2)}"
        if base_id in self.reported_keys:
            return
        self.reported_keys.add(base_id)
        self.reported_keys.add(incident_id)

        method = first["method"]
        url = first["url"]
        url_lower = url.lower()

        critical_keywords = ("pay", "checkout", "order", "charge", "transfer", "subscribe", "buy", "cart")
        if any(kw in url_lower for kw in critical_keywords):
            severity = Severity.CRITICAL
            title = f"CRITICAL: Duplicate Transactional Request to {url}"
        else:
            severity = Severity.HIGH
            title = f"Duplicate {method} Request Detected ({delta_ms}ms gap)"

        desc = (
            f"Detected {len(cluster)} duplicate {method} requests dispatched within {delta_ms}ms "
            f"to '{url}' without debounce or form disabling. "
            f"Triggered after: '{last.get('action')}'."
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
                "duplicate_count": len(cluster),
                "payload_preview": first.get("post_data"),
                "correlated_action": last.get("action"),
            },
        )
        faults.append(fault)
