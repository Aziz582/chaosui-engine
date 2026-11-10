"""
RageClicker Persona ("العميل المستعجل والغاضب").
Fires rapid multi-clicks on buttons to test click debounce and idempotency.
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


class RageClicker(BasePersona):
    """Simulates an impatient user frantically clicking buttons multiple times."""

    def __init__(self, min_clicks: int = 3, max_clicks: int = 7, delay_ms: int = 60):
        super().__init__(
            name="rage_clicker",
            description="Fires rapid repeated clicks on buttons to expose missing debounces and double charges",
        )
        self.min_clicks = min_clicks
        self.max_clicks = max_clicks
        self.delay_ms = delay_ms

    async def act(self, page: Page, session: ChaosSession, targets: List[TargetInfo]) -> bool:
        # Prioritize submit/action buttons, fallback to general buttons
        candidate_targets = TargetFinder.filter_submit_targets(targets)
        if not candidate_targets:
            candidate_targets = TargetFinder.filter_buttons(targets)

        if not candidate_targets:
            return False

        target = random.choice(candidate_targets)
        num_clicks = random.randint(self.min_clicks, self.max_clicks)

        action = session.record_action(
            action_type=ActionType.RAGE_CLICK,
            description=f"Rage-clicked '{target.display_name()}' {num_clicks} times in rapid succession",
            selector=target.selector,
            details={"clicks": num_clicks, "target": target.display_name()},
        )

        try:
            # Locate element
            loc = page.locator(target.selector).first
            if not await loc.is_visible():
                return False

            # Rapid click burst without waiting for network settlement
            for _ in range(num_clicks):
                try:
                    await loc.click(timeout=800, force=True, no_wait_after=True)
                    await asyncio.sleep(self.delay_ms / 1000.0)
                except Exception:
                    break

            return True
        except Exception:
            return False
