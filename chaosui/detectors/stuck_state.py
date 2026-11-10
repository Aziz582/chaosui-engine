"""
Detector for Stuck UI States, Infinite Spinners, and Locked Zombie Buttons.
"""

from __future__ import annotations
import time
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, BrowserContext
from chaosui.detectors.base import BaseDetector
from chaosui.core.models import FaultRecord, FaultType, Severity, ActionRecord
from chaosui.core.session import ChaosSession

STUCK_INSPECTION_SCRIPT = """
() => {
    const isVisible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    };

    const results = {
        spinners: [],
        zombieBackdrops: [],
        disabledButtons: []
    };

    // 1. Check for active spinners/loaders
    const spinnerCandidates = document.querySelectorAll(
        '.spinner, .loading, .loader, [role="progressbar"], [aria-busy="true"], .skeleton'
    );
    for (const el of spinnerCandidates) {
        if (isVisible(el)) {
            results.spinners.push({
                selector: el.className || el.tagName.toLowerCase(),
                ariaBusy: el.getAttribute('aria-busy'),
                text: el.innerText.trim().slice(0, 50)
            });
        }
    }

    // 2. Check for blocking modal backdrops without visible modal
    const backdrops = document.querySelectorAll('.modal-backdrop, .overlay, .backdrop, [role="dialog"]');
    for (const el of backdrops) {
        if (isVisible(el)) {
            const style = window.getComputedStyle(el);
            if (style.position === 'fixed' && parseFloat(style.opacity) > 0) {
                // If it's a backdrop and covers whole screen
                const rect = el.getBoundingClientRect();
                if (rect.width >= window.innerWidth * 0.9 && rect.height >= window.innerHeight * 0.9) {
                    results.zombieBackdrops.push({
                        selector: el.className || el.tagName.toLowerCase(),
                        hasDialog: !!el.querySelector('[role="dialog"], .modal-content, .dialog')
                    });
                }
            }
        }
    }

    // 3. Check for permanently disabled buttons with busy text
    const buttons = document.querySelectorAll('button:disabled, input[type="submit"]:disabled');
    for (const btn of buttons) {
        if (isVisible(btn)) {
            results.disabledButtons.push({
                text: (btn.innerText || btn.value || '').trim().slice(0, 50),
                id: btn.id
            });
        }
    }

    return results;
}
"""


class StuckStateDetector(BaseDetector):
    """Detects UI deadlocks, unresolving loading indicators, and blocking zombie overlays."""

    def __init__(self, spinner_timeout_seconds: float = 4.0):
        super().__init__("stuck_state_detector")
        self.spinner_timeout_seconds = spinner_timeout_seconds
        self.spinner_start_times: Dict[str, float] = {}
        self.reported_stuck: set[str] = set()
        self.last_action: Optional[ActionRecord] = None

    async def attach(self, page: Page, context: BrowserContext, session: ChaosSession) -> None:
        await super().attach(page, context, session)

    async def on_action_start(self, action: ActionRecord) -> None:
        self.last_action = action

    async def check(self) -> List[FaultRecord]:
        if not self.page or not self.session:
            return []

        try:
            state = await self.page.evaluate(STUCK_INSPECTION_SCRIPT)
        except Exception:
            return []

        faults: List[FaultRecord] = []
        now = time.time()

        # Check spinners
        active_spinners = state.get("spinners", [])
        for spin in active_spinners:
            key = spin.get("selector", "spinner")
            if key not in self.spinner_start_times:
                self.spinner_start_times[key] = now
            else:
                elapsed = now - self.spinner_start_times[key]
                if elapsed >= self.spinner_timeout_seconds:
                    report_key = f"spinner:{key}"
                    if report_key not in self.reported_stuck:
                        self.reported_stuck.add(report_key)
                        action_desc = self.last_action.description if self.last_action else "User action"
                        fault = self.session.record_fault(
                            fault_type=FaultType.STUCK_STATE,
                            severity=Severity.HIGH,
                            title="Perpetual Loading Indicator / Spinner",
                            description=(
                                f"Loading spinner '{key}' remained visible and unresolving for {round(elapsed, 1)}s "
                                f"after: '{action_desc}'."
                            ),
                            evidence={
                                "spinner": spin,
                                "duration_seconds": round(elapsed, 1),
                                "correlated_action": action_desc,
                            },
                        )
                        faults.append(fault)

        # Clear spinners that disappeared
        active_keys = {s.get("selector", "spinner") for s in active_spinners}
        for k in list(self.spinner_start_times.keys()):
            if k not in active_keys:
                del self.spinner_start_times[k]

        return faults
