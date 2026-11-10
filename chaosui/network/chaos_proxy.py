"""
Network Chaos Fault Injector for ChaosUI Engine.
Injects latency, transient failures, and blips to stress test UI resiliency.
"""

from __future__ import annotations
import asyncio
import random
from typing import Optional
from playwright.async_api import Page, Route, Request
from chaosui.core.session import ChaosSession
from chaosui.core.models import ActionType


class NetworkChaosInjector:
    """Intercepts browser network routes to inject latency and transient network faults."""

    def __init__(
        self,
        enabled: bool = True,
        latency_prob: float = 0.35,
        min_latency_ms: int = 500,
        max_latency_ms: int = 1500,
        failure_prob: float = 0.05,
    ):
        self.enabled = enabled
        self.latency_prob = latency_prob
        self.min_latency_ms = min_latency_ms
        self.max_latency_ms = max_latency_ms
        self.failure_prob = failure_prob
        self.session: Optional[ChaosSession] = None

    async def attach(self, page: Page, session: ChaosSession) -> None:
        self.session = session
        if not self.enabled:
            return

        await page.route("**/*", self._intercept_route)

    async def detach(self, page: Page) -> None:
        if not self.enabled:
            return
        try:
            await page.unroute("**/*", self._intercept_route)
        except Exception:
            pass

    async def _intercept_route(self, route: Route, request: Request) -> None:
        url = request.url
        resource_type = request.resource_type

        # Focus chaos on API / fetch / xhr requests
        if resource_type in ("fetch", "xhr") or "/api/" in url:
            # 1. Random failure injection (transient network abort)
            if random.random() < self.failure_prob:
                if self.session:
                    self.session.record_action(
                        action_type=ActionType.NETWORK_BLIP,
                        description=f"Injected transient network abort to: {url}",
                    )
                try:
                    await route.abort("failed")
                except Exception:
                    pass
                return

            # 2. Random latency injection (simulates sluggish mobile network or server load)
            if random.random() < self.latency_prob:
                delay = random.randint(self.min_latency_ms, self.max_latency_ms) / 1000.0
                await asyncio.sleep(delay)

        try:
            await route.continue_()
        except Exception:
            pass
