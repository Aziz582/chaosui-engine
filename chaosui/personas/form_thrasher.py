"""
FormThrasher Persona ("مخرب النماذج والمدخلات").
Rapidly types, backspaces, enters edge-case characters, and clears fields during validation.
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

CHAOTIC_INPUTS = [
    "a" * 200,  # Long string
    "<script>alert(1)</script>",  # XSS probe
    "test@@invalid..com",  # Malformed email
    "🔥⚡️💀💣🚀",  # Emojis & multi-byte unicode
    "' OR '1'='1",  # SQLi probe
    "   ",  # Whitespace
]


class FormThrasher(BasePersona):
    """Simulates erratic user behavior in text inputs, causing validation race conditions."""

    def __init__(self):
        super().__init__(
            name="form_thrasher",
            description="Rapidly mutates input fields, types long texts, backspaces, and tests validation edges",
        )

    async def act(self, page: Page, session: ChaosSession, targets: List[TargetInfo]) -> bool:
        inputs = TargetFinder.filter_input_targets(targets)
        if not inputs:
            return False

        target = random.choice(inputs)
        payload = random.choice(CHAOTIC_INPUTS)

        session.record_action(
            action_type=ActionType.TYPE_TEXT,
            description=f"Thrashed input '{target.display_name()}' with rapid typing & backspacing",
            selector=target.selector,
        )

        try:
            loc = page.locator(target.selector).first
            await loc.click(timeout=800)

            # Rapid typing
            await loc.fill(payload[:15], timeout=600)
            await asyncio.sleep(0.05)

            # Backspace barrage
            for _ in range(5):
                await page.keyboard.press("Backspace")

            # Paste rest of chaotic string
            await loc.fill(payload, timeout=600)
            return True
        except Exception:
            return False
