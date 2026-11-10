"""
Unit tests for fault detectors, reporting safety, and persona filtering.
"""

from collections import deque
import time
from unittest.mock import MagicMock
import pytest

from chaosui.core.models import ActionType, ChaosReport, FaultType, Severity
from chaosui.core.session import ChaosSession
from chaosui.detectors.crashes import CrashDetector
from chaosui.detectors.duplicate_requests import DuplicateRequestDetector
from chaosui.detectors.freeze import UIFreezeDetector
from chaosui.detectors.stuck_state import StuckStateDetector
from chaosui.personas.chaos_monkey import ImpulsiveUserPersona
from chaosui.reporting.html_report import export_html


@pytest.mark.asyncio
async def test_duplicate_request_detector():
    session = ChaosSession(target_url="https://shop.local/checkout")
    detector = DuplicateRequestDetector(window_ms=2000)
    detector.session = session

    now = time.time()
    detector.request_history = deque(
        [
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
                "timestamp": now + 0.1,
                "action": "Rage clicked Pay button",
            },
        ]
    )

    faults = await detector.check()
    assert len(faults) == 1
    fault = faults[0]
    assert fault.fault_type == FaultType.DUPLICATE_REQUEST
    assert fault.severity == Severity.CRITICAL
    assert fault.evidence["duplicate_count"] == 2
    assert fault.evidence["gap_ms"] == 100.0


@pytest.mark.asyncio
async def test_freeze_detector_severity_and_deduplication():
    session = ChaosSession(target_url="https://app.local")
    detector = UIFreezeDetector(threshold_ms=350)
    detector.session = session

    mock_page = MagicMock()

    async def mock_eval(_script):
        # First two share the same 250ms bucket (longtask + raf_heartbeat_gap for the same freeze)
        return [
            {"type": "longtask", "durationMs": 750, "startTime": 1000},
            {"type": "raf_heartbeat_gap", "durationMs": 760, "startTime": 1020},
            {"type": "raf_heartbeat_gap", "durationMs": 1600, "startTime": 3000},
        ]

    mock_page.evaluate = mock_eval
    detector.page = mock_page

    faults = await detector.check()
    assert len(faults) == 2
    assert faults[0].severity == Severity.HIGH
    assert faults[1].severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_crash_detector_accepts_page_arg_and_drains_buffers():
    session = ChaosSession(target_url="https://app.local")
    session.record_action(ActionType.CLICK, "Clicked Submit Order")
    detector = CrashDetector()
    detector.session = session

    # Playwright passes the Page instance to crash callbacks
    mock_page = MagicMock()
    detector._handle_page_crash(mock_page)
    assert len(detector.errors) == 1

    faults = await detector.check()
    assert len(faults) == 1
    assert faults[0].severity == Severity.CRITICAL
    assert "Clicked Submit Order" in faults[0].description
    # Buffer must be drained after check()
    assert len(detector.errors) == 0


@pytest.mark.asyncio
async def test_stuck_state_detector_catches_zombie_backdrop_and_disabled_button():
    session = ChaosSession(target_url="https://app.local")
    detector = StuckStateDetector(
        spinner_timeout_seconds=0.05,
        backdrop_timeout_seconds=0.05,
        button_timeout_seconds=0.05,
    )
    detector.session = session

    state_payload = {"spinners": [], "zombieBackdrops": [], "disabledButtons": []}
    mock_page = MagicMock()

    async def mock_eval(_script):
        return state_payload

    mock_page.evaluate = mock_eval
    detector.page = mock_page

    # Baseline scan (no initially disabled buttons)
    await detector.check()

    # Now simulate zombie backdrop + newly disabled button
    state_payload = {
        "spinners": [],
        "zombieBackdrops": [{"selector": ".modal-backdrop", "hasDialog": False}],
        "disabledButtons": [{"key": "#btn-pay", "text": "Pay Now", "id": "btn-pay"}],
    }
    await detector.check()
    time.sleep(0.06)
    faults = await detector.check()

    titles = [f.title for f in faults]
    assert any("Zombie Modal Backdrop" in t for t in titles)
    assert any("Permanently Disabled Button" in t for t in titles)


def test_html_report_autoescapes_xss_and_links_screenshots(tmp_path):
    session = ChaosSession(target_url="https://example.com/<script>alert(1)</script>")
    session.record_action(ActionType.TYPE_TEXT, "Typed <script>alert('xss')</script>")

    shots_dir = tmp_path / "screenshots"
    shots_dir.mkdir()
    shot_file = shots_dir / "fault_1.png"
    shot_file.write_bytes(b"PNG_PLACEHOLDER")

    session.record_fault(
        fault_type=FaultType.CRASH,
        severity=Severity.HIGH,
        title="XSS payload <img src=x onerror=alert(1)>",
        description="Triggered by <script>evil()</script>",
        screenshot_path=str(shot_file),
    )
    session.close()

    report = ChaosReport(
        session_id=session.session_id,
        target_url=session.target_url,
        start_time=session.start_time_iso,
        duration_seconds=session.duration_seconds,
        total_actions=len(session.actions),
        faults=session.faults,
        action_history=session.actions,
        metrics=session.metrics,
    )

    out_html = tmp_path / "report.html"
    export_html(report, str(out_html))
    rendered = out_html.read_text(encoding="utf-8")

    # Verify dangerous tags are HTML-escaped
    assert "<script>evil()</script>" not in rendered
    assert "&lt;script&gt;evil()&lt;/script&gt;" in rendered
    assert "screenshots/fault_1.png" in rendered


def test_impulsive_persona_respects_allowed_personas():
    persona = ImpulsiveUserPersona(allowed_personas=["rage_clicker"])
    assert persona.enabled_names == {"rage_clicker"}
