"""
Unit tests for ChaosUI data models and session.
"""

from chaosui.core.models import (
    ChaosConfig,
    ChaosReport,
    TargetInfo,
    ActionType,
    FaultType,
    Severity,
    ActionRecord,
    FaultRecord,
)
from chaosui.core.session import ChaosSession


def test_target_info_display_name():
    target = TargetInfo(
        selector="#pay-btn",
        tag_name="button",
        text="Pay Now $100",
        is_submit=True,
    )
    assert "Pay Now $100" in target.display_name()
    assert "#pay-btn" in target.display_name()


def test_chaos_session_records_actions_and_faults():
    session = ChaosSession(target_url="https://example.com/checkout")
    action = session.record_action(
        action_type=ActionType.RAGE_CLICK,
        description="Rage clicked Submit button 5 times",
        selector="#submit",
    )
    assert len(session.actions) == 1
    assert action.action_type == ActionType.RAGE_CLICK

    fault = session.record_fault(
        fault_type=FaultType.DUPLICATE_REQUEST,
        severity=Severity.CRITICAL,
        title="Duplicate Order POST",
        description="Duplicate checkout requests detected",
        evidence={"gap_ms": 120},
    )
    assert len(session.faults) == 1
    assert fault.severity == Severity.CRITICAL
    assert session.metrics["duplicate_requests_detected"] == 1
    assert len(fault.reproduction_steps) > 0


def test_chaos_report_stats():
    session = ChaosSession(target_url="https://example.com")
    session.record_fault(
        fault_type=FaultType.UI_FREEZE,
        severity=Severity.HIGH,
        title="UI Freeze",
        description="UI thread blocked",
    )
    session.record_fault(
        fault_type=FaultType.CRASH,
        severity=Severity.CRITICAL,
        title="White Screen",
        description="Blank page",
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
    )

    assert report.has_faults is True
    assert report.critical_faults_count == 1
    assert report.high_faults_count == 1
