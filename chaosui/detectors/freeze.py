"""
Detector for Main-Thread UI Freezes and Frame Jank.
Monitors browser PerformanceObserver longtask entries and requestAnimationFrame heartbeat deltas.
"""

from __future__ import annotations
from typing import List
from playwright.async_api import Page, BrowserContext
from chaosui.detectors.base import BaseDetector
from chaosui.core.models import FaultRecord, FaultType, Severity
from chaosui.core.session import ChaosSession

# Client-side heartbeat and LongTask observer script injected into page
FREEZE_MONITOR_SCRIPT = """
(() => {
    if (window.__CHAOS_FREEZE_INSTALLED__) return;
    window.__CHAOS_FREEZE_INSTALLED__ = true;
    window.__CHAOS_FREEZES__ = [];

    const FREEZE_THRESHOLD = window.__CHAOS_FREEZE_THRESHOLD__ || 350; // ms
    let lastFrameTime = performance.now();
    let isMonitoring = true;

    // 1. LongTask Performance Observer (native browser capability)
    try {
        const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (entry.duration >= FREEZE_THRESHOLD) {
                    window.__CHAOS_FREEZES__.push({
                        type: 'longtask',
                        durationMs: Math.round(entry.duration),
                        startTime: Math.round(entry.startTime),
                        name: entry.name,
                        attribution: entry.attribution ? entry.attribution.map(a => a.name || a.containerType) : []
                    });
                }
            }
        });
        observer.observe({ entryTypes: ['longtask'] });
    } catch (e) {
        // Fallback for browsers with restricted longtask support
    }

    // 2. High-precision requestAnimationFrame heartbeat
    const checkHeartbeat = () => {
        if (!isMonitoring) return;
        const now = performance.now();
        const delta = now - lastFrameTime;

        if (delta >= FREEZE_THRESHOLD) {
            window.__CHAOS_FREEZES__.push({
                type: 'raf_heartbeat_gap',
                durationMs: Math.round(delta),
                startTime: Math.round(lastFrameTime),
                timestamp: Date.now()
            });
        }

        lastFrameTime = now;
        requestAnimationFrame(checkHeartbeat);
    };

    requestAnimationFrame(checkHeartbeat);

    // Helper to retrieve and drain recorded freezes
    window.__CHAOS_GET_FREEZES__ = () => {
        const events = window.__CHAOS_FREEZES__ || [];
        window.__CHAOS_FREEZES__ = [];
        return events;
    };
})();
"""


class UIFreezeDetector(BaseDetector):
    """Detects when the browser UI main thread is blocked, causing unresponsiveness and jank."""

    def __init__(self, threshold_ms: int = 350):
        super().__init__("ui_freeze_detector")
        self.threshold_ms = threshold_ms

    async def attach(self, page: Page, context: BrowserContext, session: ChaosSession) -> None:
        await super().attach(page, context, session)

        await context.add_init_script(
            f"window.__CHAOS_FREEZE_THRESHOLD__ = {self.threshold_ms};\n{FREEZE_MONITOR_SCRIPT}"
        )
        try:
            await page.evaluate(
                f"window.__CHAOS_FREEZE_THRESHOLD__ = {self.threshold_ms};\n{FREEZE_MONITOR_SCRIPT}"
            )
        except Exception:
            pass

    async def check(self) -> List[FaultRecord]:
        if not self.page or not self.session:
            return []

        try:
            raw_freezes = await self.page.evaluate(
                "typeof window.__CHAOS_GET_FREEZES__ === 'function' ? window.__CHAOS_GET_FREEZES__() : []"
            )
        except Exception:
            return []

        faults: List[FaultRecord] = []
        # Deduplicate simultaneous longtask + raf_heartbeat_gap for the same freeze burst
        seen_buckets: set[int] = set()

        for freeze in raw_freezes:
            duration_ms = freeze.get("durationMs", 0)
            if duration_ms < self.threshold_ms:
                continue

            start_bucket = int(freeze.get("startTime", 0)) // 250
            if start_bucket in seen_buckets:
                continue
            seen_buckets.add(start_bucket)

            if duration_ms >= 1500:
                severity = Severity.CRITICAL
                status_desc = f"Severe UI Freeze! Main thread blocked for {duration_ms}ms (>= 1.5s)"
            elif duration_ms >= 700:
                severity = Severity.HIGH
                status_desc = f"High UI Freeze! Main thread unresponsive for {duration_ms}ms"
            else:
                severity = Severity.MEDIUM
                status_desc = f"Moderate UI Freeze / Jank! Frame delay of {duration_ms}ms"

            action_desc = self.current_action_description

            fault = self.session.record_fault(
                fault_type=FaultType.UI_FREEZE,
                severity=severity,
                title=f"UI Freeze detected ({duration_ms}ms)",
                description=f"{status_desc} triggered after: '{action_desc}'.",
                evidence={
                    "duration_ms": duration_ms,
                    "threshold_ms": self.threshold_ms,
                    "event_type": freeze.get("type"),
                    "attribution": freeze.get("attribution", []),
                    "correlated_action": action_desc,
                },
            )
            faults.append(fault)

        return faults
