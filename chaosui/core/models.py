"""
Core data models and type definitions for ChaosUI Engine.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class FaultType(str, Enum):
    UI_FREEZE = "UI_FREEZE"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    CRASH = "CRASH"
    STUCK_STATE = "STUCK_STATE"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    CLICK = "CLICK"
    RAGE_CLICK = "RAGE_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    TYPE_TEXT = "TYPE_TEXT"
    CLEAR_INPUT = "CLEAR_INPUT"
    FORM_SUBMIT = "FORM_SUBMIT"
    NAVIGATE_BACK = "NAVIGATE_BACK"
    NAVIGATE_FORWARD = "NAVIGATE_FORWARD"
    RELOAD = "RELOAD"
    SCROLL_BURST = "SCROLL_BURST"
    NETWORK_BLIP = "NETWORK_BLIP"


@dataclass
class TargetInfo:
    selector: str
    tag_name: str
    text: str = ""
    aria_label: Optional[str] = None
    role: Optional[str] = None
    input_type: Optional[str] = None
    is_submit: bool = False
    is_destructive: bool = False
    bounding_box: Optional[Dict[str, float]] = None

    def display_name(self) -> str:
        label = self.text.strip() or self.aria_label or self.selector
        if len(label) > 30:
            label = label[:27] + "..."
        return f"<{self.tag_name}> '{label}' ({self.selector})"


@dataclass
class ActionRecord:
    action_type: ActionType
    description: str
    timestamp: float = field(default_factory=time.time)
    selector: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FaultRecord:
    fault_type: FaultType
    severity: Severity
    title: str
    description: str
    timestamp: float = field(default_factory=time.time)
    target: Optional[TargetInfo] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    reproduction_steps: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None


@dataclass
class ChaosConfig:
    target_url: str
    max_duration_seconds: int = 40
    max_actions: int = 50
    freeze_threshold_ms: int = 350
    duplicate_window_ms: int = 2500
    personas: List[str] = field(
        default_factory=lambda: [
            "rage_clicker",
            "multi_submitter",
            "form_thrasher",
            "nav_frenzy",
            "scroll_thrasher",
        ]
    )
    intensity: str = "high"  # low, medium, high, insane
    headless: bool = True
    network_chaos: bool = True
    screenshot_on_fault: bool = True
    output_dir: str = "chaos_reports"
    browser: str = "chromium"


@dataclass
class ChaosReport:
    session_id: str
    target_url: str
    start_time: str
    duration_seconds: float
    total_actions: int
    faults: List[FaultRecord] = field(default_factory=list)
    action_history: List[ActionRecord] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_faults(self) -> bool:
        return len(self.faults) > 0

    @property
    def critical_faults_count(self) -> int:
        return sum(1 for f in self.faults if f.severity == Severity.CRITICAL)

    @property
    def high_faults_count(self) -> int:
        return sum(1 for f in self.faults if f.severity == Severity.HIGH)
