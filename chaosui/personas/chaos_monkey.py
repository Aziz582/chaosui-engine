"""
Smart Chaotic User Persona ("العميل المشاغب والمستعجل").
Dynamically adapts tactics based on current page elements and enabled personas.
"""

from __future__ import annotations
import random
from typing import List, Dict, Optional
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

    def __init__(self, allowed_personas: Optional[List[str]] = None):
        super().__init__(
            name="impulsive_user",
            description="Smart impatient user persona dynamically selecting tactics based on page DOM",
        )
        self.rage_clicker = RageClicker()
        self.multi_submitter = MultiSubmitter()
        self.form_thrasher = FormThrasher()
        self.nav_frenzy = NavFrenzy()
        self.scroll_thrasher = ScrollThrasher()

        self._registry: Dict[str, BasePersona] = {
            self.rage_clicker.name: self.rage_clicker,
            self.multi_submitter.name: self.multi_submitter,
            self.form_thrasher.name: self.form_thrasher,
            self.nav_frenzy.name: self.nav_frenzy,
            self.scroll_thrasher.name: self.scroll_thrasher,
        }

        if allowed_personas and "all" not in allowed_personas and "impulsive_user" not in allowed_personas:
            valid = {p for p in allowed_personas if p in self._registry}
            self.enabled_names: set[str] = valid if valid else set(self._registry.keys())
        else:
            self.enabled_names = set(self._registry.keys())

    async def act(self, page: Page, session: ChaosSession, targets: List[TargetInfo]) -> bool:
        if not targets:
            fallbacks = [
                p for name, p in (("nav_frenzy", self.nav_frenzy), ("scroll_thrasher", self.scroll_thrasher))
                if name in self.enabled_names
            ] or [self.scroll_thrasher]
            return await random.choice(fallbacks).act(page, session, targets)

        submits = TargetFinder.filter_submit_targets(targets)
        inputs = TargetFinder.filter_input_targets(targets)

        base_weights: Dict[BasePersona, float] = {
            self.rage_clicker: 4.0 if submits else 1.5,
            self.multi_submitter: 3.5 if submits else 0.5,
            self.form_thrasher: 3.0 if inputs else 0.5,
            self.scroll_thrasher: 1.0,
            self.nav_frenzy: 0.8,
        }

        active_weights = {
            persona: weight
            for persona, weight in base_weights.items()
            if persona.name in self.enabled_names
        }
        if not active_weights:
            active_weights = base_weights

        personas = list(active_weights.keys())
        probabilities = list(active_weights.values())

        chosen = random.choices(personas, weights=probabilities, k=1)[0]
        return await chosen.act(page, session, targets)
