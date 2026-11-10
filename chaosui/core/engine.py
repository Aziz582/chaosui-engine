"""
Core Orchestration Engine for ChaosUI.
Manages browser lifecycle, runs chaos test loop, coordinates personas and detectors.
"""

from __future__ import annotations
import asyncio
import logging
import os
import time
from typing import List, Optional, Callable
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from chaosui.core.models import ChaosConfig, ChaosReport, FaultRecord, FaultType, Severity
from chaosui.core.session import ChaosSession
from chaosui.core.target_finder import TargetFinder
from chaosui.detectors.base import BaseDetector
from chaosui.detectors.freeze import UIFreezeDetector
from chaosui.detectors.duplicate_requests import DuplicateRequestDetector
from chaosui.detectors.crashes import CrashDetector
from chaosui.detectors.stuck_state import StuckStateDetector
from chaosui.network.chaos_proxy import NetworkChaosInjector
from chaosui.personas.base import BasePersona
from chaosui.personas.chaos_monkey import ImpulsiveUserPersona

logger = logging.getLogger(__name__)


class ChaosEngine:
    """The central orchestrator of ChaosUI execution."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self.session = ChaosSession(target_url=config.target_url)
        self.detectors: List[BaseDetector] = []
        self.persona: BasePersona = ImpulsiveUserPersona(allowed_personas=config.personas)
        self.network_chaos = NetworkChaosInjector(enabled=config.network_chaos)
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None

        # Prepare output directory
        os.makedirs(self.config.output_dir, exist_ok=True)
        self.screenshots_dir = os.path.join(self.config.output_dir, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)

    def _init_detectors(self) -> None:
        self.detectors = [
            UIFreezeDetector(threshold_ms=self.config.freeze_threshold_ms),
            DuplicateRequestDetector(window_ms=self.config.duplicate_window_ms),
            CrashDetector(),
            StuckStateDetector(),
        ]

    async def _capture_fault_screenshot(self, page: Page, fault: FaultRecord) -> None:
        if not self.config.screenshot_on_fault or fault.screenshot_path:
            return
        try:
            screenshot_file = os.path.join(
                self.screenshots_dir,
                f"fault_{fault.fault_type.value}_{int(fault.timestamp * 1000)}.png",
            )
            await page.screenshot(path=screenshot_file, full_page=False)
            fault.screenshot_path = screenshot_file
        except Exception as exc:
            logger.debug("Could not capture screenshot for fault '%s': %s", fault.title, exc)

    async def run(self) -> ChaosReport:
        """Executes the chaos testing session and returns the completed ChaosReport."""
        self._init_detectors()

        async with async_playwright() as p:
            browser_type = getattr(p, self.config.browser, p.chromium)
            browser: Browser = await browser_type.launch(
                headless=self.config.headless,
                args=["--disable-web-security", "--allow-running-insecure-content"],
            )
            context: Optional[BrowserContext] = None
            page: Optional[Page] = None

            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (ChaosUI-Engine/1.0 ImpatientCustomerBot)",
                )

                page = await context.new_page()

                # Attach network chaos
                await self.network_chaos.attach(page, self.session)

                # Attach all detectors
                for detector in self.detectors:
                    await detector.attach(page, context, self.session)

                # Navigate to target
                nav_ok = True
                try:
                    await page.goto(self.config.target_url, wait_until="domcontentloaded", timeout=15000)
                except Exception as exc:
                    nav_ok = False
                    nav_fault = self.session.record_fault(
                        fault_type=FaultType.CRASH,
                        severity=Severity.CRITICAL,
                        title=f"Navigation Error to {self.config.target_url}",
                        description=f"Failed to load target URL '{self.config.target_url}': {exc}",
                        evidence={"target_url": self.config.target_url, "error": str(exc)},
                    )
                    await self._capture_fault_screenshot(page, nav_fault)

                if nav_ok:
                    action_count = 0
                    start_time = time.time()

                    delay_map = {"low": 0.5, "medium": 0.25, "high": 0.1, "insane": 0.02}
                    tick_delay = delay_map.get(self.config.intensity.lower(), 0.1)

                    while (
                        action_count < self.config.max_actions
                        and (time.time() - start_time) < self.config.max_duration_seconds
                    ):
                        action_count += 1
                        prev_actions_len = len(self.session.actions)

                        # 1. Scan for actionable targets
                        targets = await TargetFinder.scan_page(page)

                        # 2. Persona executes an action turn
                        try:
                            await self.persona.act(page, self.session, targets)
                        except Exception as exc:
                            logger.debug("Persona turn encountered error: %s", exc)

                        # 3. Notify detectors & progress callback of newly executed action
                        if len(self.session.actions) > prev_actions_len:
                            latest_action = self.session.actions[-1]
                            for d in self.detectors:
                                await d.on_action_end(latest_action)
                            if self.progress_callback:
                                self.progress_callback(
                                    action_count, self.config.max_actions, latest_action.description
                                )
                        elif self.progress_callback:
                            self.progress_callback(action_count, self.config.max_actions, "Scanning page state...")

                        # 4. Check detectors for newly triggered faults
                        for d in self.detectors:
                            new_faults: List[FaultRecord] = await d.check()
                            for fault in new_faults:
                                await self._capture_fault_screenshot(page, fault)

                        await asyncio.sleep(tick_delay)

                    # Final settle check before teardown
                    await asyncio.sleep(0.5)
                    for d in self.detectors:
                        final_faults = await d.check()
                        for fault in final_faults:
                            await self._capture_fault_screenshot(page, fault)
            finally:
                for d in self.detectors:
                    try:
                        await d.detach()
                    except Exception:
                        pass
                if page is not None:
                    try:
                        await self.network_chaos.detach(page)
                    except Exception:
                        pass
                if context is not None:
                    try:
                        await context.close()
                    except Exception:
                        pass
                try:
                    await browser.close()
                except Exception:
                    pass

        self.session.close()

        return ChaosReport(
            session_id=self.session.session_id,
            target_url=self.config.target_url,
            start_time=self.session.start_time_iso,
            duration_seconds=self.session.duration_seconds,
            total_actions=len(self.session.actions),
            faults=self.session.faults,
            action_history=self.session.actions,
            metrics=self.session.metrics,
        )
