"""
Unit tests for fault detectors.
"""

import pytest
import time
from unittest.mock import MagicMock
from chaosui.core.session import ChaosSession
from chaosui.detectors.duplicate_requests import DuplicateRequestDetector
from chaosui.detectors.freeze import UIFreezeDetector
from chaosui.core.models import Severity, FaultType


@pytest.mark.asyncio
async def test_duplicate_request_detector():
    session = ChaosSession(target_url="https://shop.local/checkout")
    detector = DuplicateRequestDetector(window_ms=2000)
    detector.session = session

    # Simulate two duplicate checkout requests dispatched 100ms apart
    now = time.time()
    detector.request_history = [
        {
            "method": "POST",
            "url": "https://shop.local/api/checkout",
            "post_data": '{"item":"Pro","qty":1}',
            "post_hash": "abc12345",
            "timestamp": now,
            "action": "Rage clicked Pay button",
        },
        {
            "method": "POST",
            "url": "https://shop.local/api/checkout",
            "post_data": '{"item":"Pro","qty":1}',
            "post_hash": "abc12345",
            "timestamp": now + 0.1,  # 100ms later
            "action": "Rage clicked Pay button",
        },
    ]

    faults = await detector.check()
    assert len(faults) == 1
    fault = faults[0]
    assert fault.fault_type == FaultType.DUPLICATE_REQUEST
    assert fault.severity == Severity.CRITICAL  # Because of 'checkout' in URL
    assert fault.evidence["duplicate_count"] == 2
    assert fault.evidence["gap_ms"] == 100.0


@pytest.mark.asyncio
async def test_freeze_detector_severity_scaling():
    session = ChaosSession(target_url="https://app.local")
    detector = UIFreezeDetector(threshold_ms=350)
    detector.session = session

    # Mock page evaluation returning two freeze events (750ms and 1600ms)
    mock_page = MagicMock()
    async def mock_eval(script):
        return [
            {"type": "longtask", "durationMs": 750, "startTime": 1000},
            {"type": "raf_heartbeat_gap", "durationMs": 1600, "startTime": 2000},
        ]
    mock_page.evaluate = mock_eval
    detector.page = mock_page

    faults = await detector.check()
    assert len(faults) == 2
    assert faults[0].severity == Severity.HIGH  # 750ms
    assert faults[1].severity == Severity.CRITICAL  # 1600ms
