"""
Detector for Stuck UI States, Infinite Spinners, Zombie Overlays, and Locked Buttons.
"""

from __future__ import annotations
import time
from typing import List, Dict
from playwright.async_api import Page, BrowserContext
from chaosui.detectors.base import BaseDetector
from chaosui.core.models import FaultRecord, FaultType, Severity
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
                selector: el.id ? `#${el.id}` : (el.className || el.tagName.toLowerCase()),
                ariaBusy: el.getAttribute('aria-busy'),
                text: (el.innerText || '').trim().slice(0, 50)
            });
        }
    }

    // 2. Check for blocking modal backdrops without visible modal dialog
    const backdrops = document.querySelectorAll('.modal-backdrop, .overlay, .backdrop');
    for (const el of backdrops) {
        if (isVisible(el)) {
            const style = window.getComputedStyle(el);
            if (style.position === 'fixed' && parseFloat(style.opacity || '1') > 0 && style.pointerEvents !== 'none') {
                const rect = el.getBoundingClientRect();
                if (rect.width >= window.innerWidth * 0.9 && rect.height >= window.innerHeight * 0.9) {
                    const hasVisibleDialog = Array.from(
                        document.querySelectorAll('[role="dialog"], .modal-content, .dialog, dialog[open]')
                    ).some(d => isVisible(d));
                    results.zombieBackdrops.push({
                        selector: el.id ? `#${el.id}` : (el.className || el.tagName.toLowerCase()),
                        hasDialog: hasVisibleDialog
                    });
                }
            }
        }
    }

    // 3. Check for disabled primary/submit buttons
    const buttons = document.querySelectorAll('button:disabled, input[type="submit"]:disabled');
    for (const btn of buttons) {
        if (isVisible(btn)) {
            const label = (btn.innerText || btn.value || '').trim().slice(0, 50);
            results.disabledButtons.push({
                key: btn.id ? `#${btn.id}` : `${btn.tagName.toLowerCase()}:${label}`,
                text: label,
                id: btn.id || null
            });
        }
    }

    return results;
}
"""


class StuckStateDetector(BaseDetector):
    """Detects UI deadlocks, unresolving loading indicators, zombie backdrops, and locked buttons."""

    def __init__(
        self,
        spinner_timeout_seconds: float = 4.0,
        backdrop_timeout_seconds: float = 2.5,
        button_timeout_seconds: float = 5.0,
    ):
        super().__init__("stuck_state_detector")
        self.spinner_timeout_seconds = spinner_timeout_seconds
        self.backdrop_timeout_seconds = backdrop_timeout_seconds
        self.button_timeout_seconds = button_timeout_seconds
        self.spinner_start_times: Dict[str, float] = {}
        self.backdrop_start_times: Dict[str, float] = {}
        self.button_start_times: Dict[str, float] = {}
        self.initial_disabled_buttons: set[str] = set()
        self._baseline_captured: bool = False
        self.reported_stuck: set[str] = set()

    async def attach(self, page: Page, context: BrowserContext, session: ChaosSession) -> None:
        await super().attach(page, context, session)

    async def check(self) -> List[FaultRecord]:
        if not self.page or not self.session:
            return []

        try:
            state = await self.page.evaluate(STUCK_INSPECTION_SCRIPT)
        except Exception:
            return []

        if not self._baseline_captured:
            self._baseline_captured = True
            for btn in state.get("disabledButtons", []):
                self.initial_disabled_buttons.add(btn.get("key", ""))

        faults: List[FaultRecord] = []
        now = time.time()
        action_desc = self.current_action_description

        # 1. Perpetual Spinners
        active_spinners = state.get("spinners", [])
        for spin in active_spinners:
            key = str(spin.get("selector", "spinner"))
            if key not in self.spinner_start_times:
                self.spinner_start_times[key] = now
            else:
                elapsed = now - self.spinner_start_times[key]
                if elapsed >= self.spinner_timeout_seconds:
                    report_key = f"spinner:{key}"
                    if report_key not in self.reported_stuck:
                        self.reported_stuck.add(report_key)
                        faults.append(
                            self.session.record_fault(
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
                        )

        active_spinner_keys = {str(s.get("selector", "spinner")) for s in active_spinners}
        for k in list(self.spinner_start_times.keys()):
            if k not in active_spinner_keys:
                del self.spinner_start_times[k]

        # 2. Zombie Full-Screen Backdrops (blocking UI with no dialog)
        zombie_backdrops = [b for b in state.get("zombieBackdrops", []) if not b.get("hasDialog")]
        for bd in zombie_backdrops:
            key = str(bd.get("selector", "backdrop"))
            if key not in self.backdrop_start_times:
                self.backdrop_start_times[key] = now
            else:
                elapsed = now - self.backdrop_start_times[key]
                if elapsed >= self.backdrop_timeout_seconds:
                    report_key = f"backdrop:{key}"
                    if report_key not in self.reported_stuck:
                        self.reported_stuck.add(report_key)
                        faults.append(
                            self.session.record_fault(
                                fault_type=FaultType.STUCK_STATE,
                                severity=Severity.CRITICAL,
                                title="Zombie Modal Backdrop Blocking UI",
                                description=(
                                    f"Full-screen overlay '{key}' blocked user interaction for {round(elapsed, 1)}s "
                                    f"with no active dialog after: '{action_desc}'."
                                ),
                                evidence={
                                    "backdrop": bd,
                                    "duration_seconds": round(elapsed, 1),
                                    "correlated_action": action_desc,
                                },
                            )
                        )

        active_bd_keys = {str(b.get("selector", "backdrop")) for b in zombie_backdrops}
        for k in list(self.backdrop_start_times.keys()):
            if k not in active_bd_keys:
                del self.backdrop_start_times[k]

        # 3. Permanently Disabled Buttons (that were enabled prior to interaction)
        disabled_buttons = [
            b for b in state.get("disabledButtons", []) if b.get("key", "") not in self.initial_disabled_buttons
        ]
        for btn in disabled_buttons:
            key = str(btn.get("key", "button"))
            if key not in self.button_start_times:
                self.button_start_times[key] = now
            else:
                elapsed = now - self.button_start_times[key]
                if elapsed >= self.button_timeout_seconds:
                    report_key = f"disabled_btn:{key}"
                    if report_key not in self.reported_stuck:
                        self.reported_stuck.add(report_key)
                        faults.append(
                            self.session.record_fault(
                                fault_type=FaultType.STUCK_STATE,
                                severity=Severity.MEDIUM,
                                title=f"Permanently Disabled Button ({key})",
                                description=(
                                    f"Action button '{btn.get('text') or key}' remained disabled for {round(elapsed, 1)}s "
                                    f"without recovering after: '{action_desc}'."
                                ),
                                evidence={
                                    "button": btn,
                                    "duration_seconds": round(elapsed, 1),
                                    "correlated_action": action_desc,
                                },
                            )
                        )

        active_btn_keys = {str(b.get("key", "button")) for b in disabled_buttons}
        for k in list(self.button_start_times.keys()):
            if k not in active_btn_keys:
                del self.button_start_times[k]

        return faults
