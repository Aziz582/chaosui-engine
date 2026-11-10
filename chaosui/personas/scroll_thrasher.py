"""
ScrollThrasher Persona ("المتصفح العنيف").
Simulates violent, rapid scrolling up and down to stress test lazy-loaders and scroll listeners.
"""

from __future__ import annotations
import asyncio
from typing import List
from playwright.async_api import Page
from chaosui.personas.base import BasePersona
from chaosui.core.models import TargetInfo, ActionType
from chaosui.core.session import ChaosSession


class ScrollThrasher(BasePersona):
    """Simulates an impatient user frantically flicking scroll wheels or mobile touch scrolls."""

    def __init__(self):
        super().__init__(
            name="scroll_thrasher",
            description="Performs rapid scroll bursts up and down to trigger layout thrashing",
        )

    async def act(self, page: Page, session: ChaosSession, targets: List[TargetInfo]) -> bool:
        session.record_action(
            action_type=ActionType.SCROLL_BURST,
            description="Executed rapid scroll oscillations (top-bottom-top)",
        )

        try:
            # Rapid scroll to bottom, then middle, then top
            await page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'instant'});")
            await asyncio.sleep(0.05)
            await page.evaluate("window.scrollTo({top: document.body.scrollHeight / 2, behavior: 'instant'});")
            await asyncio.sleep(0.05)
            await page.evaluate("window.scrollTo({top: 0, behavior: 'instant'});")
            return True
        except Exception:
            return False
