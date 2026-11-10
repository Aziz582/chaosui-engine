"""
Detector for JavaScript Uncaught Exceptions, Console Errors, White Screens, and Server 5xx.
"""

from __future__ import annotations
import time
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, BrowserContext, Error as PlaywrightError, ConsoleMessage, Response
from chaosui.detectors.base import BaseDetector
from chaosui.core.models import FaultRecord, FaultType, Severity
from chaosui.core.session import ChaosSession


class CrashDetector(BaseDetector):
    """Detects unhandled client-side runtime errors, console exceptions, and white screens."""

    def __init__(self):
        super().__init__("crash_detector")
        self.errors: List[Dict[str, Any]] = []
        self.server_errors: List[Dict[str, Any]] = []
        self.reported_errors: set[str] = set()

    async def attach(self, page: Page, context: BrowserContext, session: ChaosSession) -> None:
        await super().attach(page, context, session)

        page.on("pageerror", self._handle_page_error)
        page.on("console", self._handle_console)
        page.on("crash", self._handle_page_crash)
        page.on("response", self._handle_response)

    async def detach(self) -> None:
        if self.page:
            for event, handler in (
                ("pageerror", self._handle_page_error),
                ("console", self._handle_console),
                ("crash", self._handle_page_crash),
                ("response", self._handle_response),
            ):
                try:
                    self.page.remove_listener(event, handler)
                except Exception:
                    pass
        await super().detach()

    def _handle_page_error(self, error: PlaywrightError) -> None:
        self.errors.append(
            {
                "type": "uncaught_exception",
                "message": str(error),
                "timestamp": time.time(),
                "action": self.current_action_description,
            }
        )

    def _handle_console(self, msg: ConsoleMessage) -> None:
        if msg.type == "error":
            text = msg.text
            self.errors.append(
                {
                    "type": "console_error",
                    "message": text[:300],
                    "timestamp": time.time(),
                    "action": self.current_action_description,
                }
            )

    def _handle_page_crash(self, _page: Optional[Page] = None) -> None:
        self.errors.append(
            {
                "type": "page_crash",
                "message": "Browser page/renderer process crashed completely!",
                "timestamp": time.time(),
                "action": self.current_action_description,
            }
        )

    def _handle_response(self, response: Response) -> None:
        if response.status >= 500:
            self.server_errors.append(
                {
                    "status": response.status,
                    "url": response.url,
                    "timestamp": time.time(),
                    "action": self.current_action_description,
                }
            )
            if self.session:
                self.session.metrics["failed_requests"] += 1

    async def _check_white_screen(self) -> Optional[FaultRecord]:
        """Detects if the page went blank (White Screen of Death)."""
        if not self.page or not self.session:
            return None

        try:
            is_blank = await self.page.evaluate(
                """() => {
                    const body = document.body;
                    if (!body) return true;
                    if (body.children.length === 0) return true;
                    const root = document.getElementById('root') || document.getElementById('app') || document.getElementById('__next');
                    if (root && root.children.length === 0 && root.innerText.trim() === '') return true;
                    return false;
                }"""
            )
            if is_blank:
                ws_key = f"white_screen:{self.page.url}"
                if ws_key in self.reported_errors:
                    return None
                self.reported_errors.add(ws_key)
                action_desc = self.current_action_description
                return self.session.record_fault(
                    fault_type=FaultType.CRASH,
                    severity=Severity.CRITICAL,
                    title="White Screen of Death (Empty DOM Root)",
                    description=f"The application DOM was wiped out or rendered empty after: '{action_desc}'.",
                    evidence={"blank_detected": True, "url": self.page.url, "correlated_action": action_desc},
                )
        except Exception:
            pass
        return None

    async def check(self) -> List[FaultRecord]:
        if not self.session:
            return []

        faults: List[FaultRecord] = []

        # Atomically drain buffered errors to prevent unbounded memory growth
        pending_errors = self.errors[:]
        self.errors.clear()

        pending_server_errors = self.server_errors[:]
        self.server_errors.clear()

        # 1. Uncaught JS & Console Errors
        for err in pending_errors:
            msg = err["message"]
            err_key = f"{err['type']}:{msg[:80]}"
            if err_key in self.reported_errors:
                continue
            self.reported_errors.add(err_key)

            if err["type"] == "page_crash":
                sev = Severity.CRITICAL
                title = "Fatal Tab Crash"
            elif err["type"] == "uncaught_exception":
                sev = Severity.CRITICAL
                title = "Uncaught JavaScript Exception"
            else:
                sev = Severity.HIGH
                title = "Console Error Boundary Incident"

            fault = self.session.record_fault(
                fault_type=FaultType.CRASH,
                severity=sev,
                title=title,
                description=f"{msg} (triggered after: '{err.get('action')}')",
                evidence={
                    "error_type": err["type"],
                    "message": msg,
                    "correlated_action": err.get("action"),
                },
            )
            faults.append(fault)

        # 2. Server 5xx directly provoked by client UI actions
        for srv in pending_server_errors:
            srv_key = f"{srv['status']}:{srv['url']}"
            if srv_key in self.reported_errors:
                continue
            self.reported_errors.add(srv_key)

            fault = self.session.record_fault(
                fault_type=FaultType.CRASH,
                severity=Severity.HIGH,
                title=f"HTTP {srv['status']} Server Fault on UI Action",
                description=f"Request to '{srv['url']}' failed with HTTP {srv['status']} after '{srv.get('action')}'.",
                evidence=srv,
            )
            faults.append(fault)

        # 3. White screen check
        ws_fault = await self._check_white_screen()
        if ws_fault:
            faults.append(ws_fault)

        return faults
