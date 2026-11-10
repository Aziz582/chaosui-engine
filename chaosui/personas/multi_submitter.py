"""
MultiSubmitter Persona ("مكرر إرسال النماذج والطلبات").
Simulates a customer double-submitting forms via clicks and Enter keystrokes while requests are in flight.
"""

from __future__ import annotations
import asyncio
import random
from typing import List
from playwright.async_api import Page
from chaosui.personas.base import BasePersona
from chaosui.core.models import TargetInfo, ActionType
from chaosui.core.session import ChaosSession
from chaosui.core.target_finder import TargetFinder


class MultiSubmitter(BasePersona):
    """Simulates an impatient user submitting forms multiple times simultaneously."""

    def __init__(self):
        super().__init__(
            name="multi_submitter",
            description="Submits forms multiple times via repeated clicks and Enter keys before response returns",
        )

    async def act(self, page: Page, session: ChaosSession, targets: List[TargetInfo]) -> bool:
        submit_targets = TargetFinder.filter_submit_targets(targets)
        if not submit_targets:
            return False

        target = random.choice(submit_targets)
        inputs = TargetFinder.filter_input_targets(targets)

        # If inputs are empty, quickly populate them so submission is valid
        for inp in inputs[:3]:
            try:
                loc = page.locator(inp.selector).first
                val = await loc.input_value()
                if not val:
                    sample_text = "test_user@example.com" if "email" in (inp.input_type or "") else "ChaosUser123"
                    await loc.fill(sample_text, timeout=500)
            except Exception:
                pass

        session.record_action(
            action_type=ActionType.FORM_SUBMIT,
            description=f"Double-submitted form using '{target.display_name()}' via Click + Enter + Click",
            selector=target.selector,
        )

        try:
            loc = page.locator(target.selector).first
            # 1. First submit click
            await loc.click(timeout=800, no_wait_after=True, force=True)
            await asyncio.sleep(0.08)

            # 2. Impatient Enter key press
            await page.keyboard.press("Enter")
            await asyncio.sleep(0.08)

            # 3. Second submit click while in-flight
            await loc.click(timeout=800, no_wait_after=True, force=True)
            return True
        except Exception:
            return False
