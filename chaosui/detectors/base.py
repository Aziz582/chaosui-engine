"""
Base class for ChaosUI Fault Detectors.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from playwright.async_api import Page, BrowserContext
from chaosui.core.models import FaultRecord, ActionRecord
from chaosui.core.session import ChaosSession


class BaseDetector(ABC):
    """Abstract base class for all invariant detectors."""

    def __init__(self, name: str):
        self.name = name
        self.session: Optional[ChaosSession] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None

    @abstractmethod
    async def attach(self, page: Page, context: BrowserContext, session: ChaosSession) -> None:
        """Attach detector hooks to the browser page/context."""
        self.page = page
        self.context = context
        self.session = session

    @abstractmethod
    async def check(self) -> List[FaultRecord]:
        """Poll or evaluate current state for faults and return new discoveries."""
        pass

    async def on_action_start(self, action: ActionRecord) -> None:
        """Invoked immediately before an action is executed."""
        pass

    async def on_action_end(self, action: ActionRecord) -> None:
        """Invoked immediately after an action is executed."""
        pass

    async def detach(self) -> None:
        """Clean up detector listeners or scripts."""
        self.page = None
        self.context = None
        self.session = None
