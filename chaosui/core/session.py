"""
Session tracking and state management for ChaosUI executions.
"""

from __future__ import annotations
import uuid
import time
from typing import List, Dict, Any, Optional
from chaosui.core.models import ActionRecord, FaultRecord, TargetInfo, ActionType, FaultType, Severity


class ChaosSession:
    """Manages the lifecycle, action timeline, and fault records of a chaos test session."""

    def __init__(self, target_url: str, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.target_url = target_url
        self.start_time = time.time()
        self.start_time_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time))
        self.end_time: Optional[float] = None
        self.actions: List[ActionRecord] = []
        self.faults: List[FaultRecord] = []
        self.metrics: Dict[str, Any] = {
            "total_requests": 0,
            "failed_requests": 0,
            "console_errors": 0,
            "freeze_events": 0,
            "duplicate_requests_detected": 0,
        }

    def record_action(
        self,
        action_type: ActionType,
        description: str,
        selector: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ActionRecord:
        record = ActionRecord(
            action_type=action_type,
            description=description,
            timestamp=time.time(),
            selector=selector,
            details=details or {},
        )
        self.actions.append(record)
        return record

    def record_fault(
        self,
        fault_type: FaultType,
        severity: Severity,
        title: str,
        description: str,
        target: Optional[TargetInfo] = None,
        evidence: Optional[Dict[str, Any]] = None,
        screenshot_path: Optional[str] = None,
    ) -> FaultRecord:
        # Build reproduction steps from recent actions (last 5 actions)
        recent_actions = self.actions[-5:] if self.actions else []
        repro_steps = [f"Step {idx + 1}: {act.description}" for idx, act in enumerate(recent_actions)]
        if not repro_steps:
            repro_steps = ["1. Open target URL", f"2. Trigger fault: {title}"]

        fault = FaultRecord(
            fault_type=fault_type,
            severity=severity,
            title=title,
            description=description,
            timestamp=time.time(),
            target=target,
            evidence=evidence or {},
            reproduction_steps=repro_steps,
            screenshot_path=screenshot_path,
        )
        self.faults.append(fault)

        # Update metrics
        if fault_type == FaultType.UI_FREEZE:
            self.metrics["freeze_events"] += 1
        elif fault_type == FaultType.DUPLICATE_REQUEST:
            self.metrics["duplicate_requests_detected"] += 1
        elif fault_type == FaultType.CRASH:
            self.metrics["console_errors"] += 1

        return fault

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 2)

    def close(self):
        self.end_time = time.time()
