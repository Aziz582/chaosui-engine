"""
Smart Chaotic User Persona ("العميل المشاغب والمستعجل").
Dynamically adapts tactics based on current page elements.
"""

from __future__ import annotations
import random
from typing import List, Dict
from playwright.async_api import Page
from chaosui.personas.base import BasePersona
from chaosui.personas.rage_clicker import RageClicker
from chaosui.personas.multi_submitter import MultiSubmitter
from chaosui.personas.form_thrasher import FormThrasher
from chaosui.personas.nav_frenzy import NavFrenzy
from chaosui.personas.scroll_thrasher import ScrollThrasher
from chaosui.core.models import TargetInfo
from chaosui.core.session import ChaosSession
from chaosui.core.target_finder import TargetFinder


class ImpulsiveUserPersona(BasePersona):
    """The flagship smart chaotic persona mimicking an impatient, unpredictable real user."""

    def __init__(self):
        super().__init__(
            name="impulsive_user",
            description="Smart impatient user persona dynamically selecting tactics based on page DOM",
        )
        self.rage_clicker = RageClicker()
        self.multi_submitter = MultiSubmitter()
        self.form_thrasher = FormThrasher()
        self.nav_frenzy = NavFrenzy()
        self.scroll_thrasher = ScrollThrasher()

    async def act(self, page: Page, session: ChaosSession, targets: List[TargetInfo]) -> bool:
        if not targets:
            # If no targets, fallback to navigation or scroll frenzy
            return await random.choice([self.nav_frenzy, self.scroll_thrasher]).act(page, session, targets)

        submits = TargetFinder.filter_submit_targets(targets)
        inputs = TargetFinder.filter_input_targets(targets)

        # Dynamic weights based on page content
        weights: Dict[BasePersona, float] = {
            self.rage_clicker: 4.0 if submits else 1.5,
            self.multi_submitter: 3.5 if submits else 0.5,
            self.form_thrasher: 3.0 if inputs else 0.5,
            self.scroll_thrasher: 1.0,
            self.nav_frenzy: 0.8,
        }

        personas = list(weights.keys())
        probabilities = list(weights.values())

        chosen = random.choices(personas, weights=probabilities, k=1)[0]
        return await chosen.act(page, session, targets)
