"""
Base class for ChaosUI Personas.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from playwright.async_api import Page
from chaosui.core.models import TargetInfo
from chaosui.core.session import ChaosSession


class BasePersona(ABC):
    """Abstract behavioral persona simulating realistic human chaos."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def act(
        self,
        page: Page,
        session: ChaosSession,
        targets: List[TargetInfo],
    ) -> bool:
        """Execute a chaotic behavior turn. Returns True if an action was performed."""
        pass
