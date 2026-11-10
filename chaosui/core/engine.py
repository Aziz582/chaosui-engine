"""
Core Orchestration Engine for ChaosUI.
Manages browser lifecycle, runs chaos test loop, coordinates personas and detectors.
"""

from __future__ import annotations
import asyncio
import os
import time
from typing import List, Optional, Callable
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from chaosui.core.models import ChaosConfig, ChaosReport, FaultRecord
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


class ChaosEngine:
    """The central orchestrator of ChaosUI execution."""

    def __init__(self, config: ChaosConfig):
        self.config = config
        self.session = ChaosSession(target_url=config.target_url)
        self.detectors: List[BaseDetector] = []
        self.persona: BasePersona = ImpulsiveUserPersona()
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

    async def run(self) -> ChaosReport:
        """Executes the chaos testing session and returns the completed ChaosReport."""
        self._init_detectors()

        async with async_playwright() as p:
            browser_type = getattr(p, self.config.browser, p.chromium)
            browser: Browser = await browser_type.launch(
                headless=self.config.headless,
                args=["--disable-web-security", "--allow-running-insecure-content"],
            )

            context: BrowserContext = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (ChaosUI-Engine/1.0 ImpatientCustomerBot)",
            )

            page: Page = await context.new_page()

            # Attach network chaos
            await self.network_chaos.attach(page, self.session)

            # Attach all detectors
            for detector in self.detectors:
                await detector.attach(page, context, self.session)

            # Navigate to target
            try:
                await page.goto(self.config.target_url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                # If initial navigation fails, still check for fatal crashes
                self.session.record_fault(
                    fault_type=self.detectors[2].session.faults[0].fault_type if self.detectors else None,  # type: ignore
                    severity=self.detectors[2].session.faults[0].severity if self.detectors else None,  # type: ignore
                    title=f"Navigation Error to {self.config.target_url}",
                    description=str(e),
                )

            # Main Chaos Loop
            action_count = 0
            start_time = time.time()

            # Determine loop delay based on intensity
            delay_map = {"low": 0.5, "medium": 0.25, "high": 0.1, "insane": 0.02}
            tick_delay = delay_map.get(self.config.intensity.lower(), 0.1)

            while (
                action_count < self.config.max_actions
                and (time.time() - start_time) < self.config.max_duration_seconds
            ):
                action_count += 1

                # 1. Scan for actionable targets
                targets = await TargetFinder.scan_page(page)

                # 2. Inform detectors of action start
                for d in self.detectors:
                    if self.session.actions:
                        await d.on_action_start(self.session.actions[-1])

                # 3. Persona executes an action turn
                try:
                    acted = await self.persona.act(page, self.session, targets)
                except Exception:
                    acted = False

                if self.progress_callback and self.session.actions:
                    last_act = self.session.actions[-1]
                    self.progress_callback(action_count, self.config.max_actions, last_act.description)

                # 4. Check detectors for newly triggered faults
                for d in self.detectors:
                    new_faults: List[FaultRecord] = await d.check()
                    for fault in new_faults:
                        if self.config.screenshot_on_fault and not fault.screenshot_path:
                            try:
                                screenshot_file = os.path.join(
                                    self.screenshots_dir,
                                    f"fault_{fault.fault_type.value}_{int(fault.timestamp * 1000)}.png",
                                )
                                await page.screenshot(path=screenshot_file, full_page=False)
                                fault.screenshot_path = screenshot_file
                            except Exception:
                                pass

                await asyncio.sleep(tick_delay)

            # Final check before teardown
            await asyncio.sleep(0.5)
            for d in self.detectors:
                await d.check()

            # Close browser
            await context.close()
            await browser.close()

        self.session.close()

        report = ChaosReport(
            session_id=self.session.session_id,
            target_url=self.config.target_url,
            start_time=self.session.start_time_iso,
            duration_seconds=self.session.duration_seconds,
            total_actions=len(self.session.actions),
            faults=self.session.faults,
            action_history=self.session.actions,
            metrics=self.session.metrics,
        )

        return report
