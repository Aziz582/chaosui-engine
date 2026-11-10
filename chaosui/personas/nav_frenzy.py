"""
NavFrenzy Persona ("المتنقل السريع والمتقلب").
Performs rapid back/forward navigation, reloads, and tab shifts during pending operations.
"""

from __future__ import annotations
import asyncio
import random
from typing import List
from playwright.async_api import Page
from chaosui.personas.base import BasePersona
from chaosui.core.models import TargetInfo, ActionType
from chaosui.core.session import ChaosSession


class NavFrenzy(BasePersona):
    """Simulates an impatient user abruptly navigating back/forward or reloading during async operations."""

    def __init__(self):
        super().__init__(
            name="nav_frenzy",
            description="Abruptly navigates back/forward or reloads while operations are in flight",
        )

    async def act(self, page: Page, session: ChaosSession, targets: List[TargetInfo]) -> bool:
        choice = random.choice(["reload", "back_forward", "rapid_hash"])

        if choice == "reload":
            session.record_action(
                action_type=ActionType.RELOAD,
                description="Triggered abrupt page reload during interaction",
            )
            try:
                await page.reload(timeout=3000, wait_until="domcontentloaded")
                return True
            except Exception:
                return False

        elif choice == "back_forward":
            session.record_action(
                action_type=ActionType.NAVIGATE_BACK,
                description="Navigated Back and immediately Forward",
            )
            try:
                await page.go_back(timeout=2000)
                await asyncio.sleep(0.1)
                await page.go_forward(timeout=2000)
                return True
            except Exception:
                return False

        elif choice == "rapid_hash":
            session.record_action(
                action_type=ActionType.NAVIGATE_FORWARD,
                description="Toggled URL hash anchor rapidly",
            )
            try:
                await page.evaluate("window.location.hash = '#chaos-' + Date.now();")
                await asyncio.sleep(0.05)
                await page.evaluate("window.location.hash = '';")
                return True
            except Exception:
                return False

        return False
