"""
ChaosUI Fault Detectors package.
"""

from chaosui.detectors.base import BaseDetector
from chaosui.detectors.freeze import UIFreezeDetector
from chaosui.detectors.duplicate_requests import DuplicateRequestDetector
from chaosui.detectors.crashes import CrashDetector
from chaosui.detectors.stuck_state import StuckStateDetector

__all__ = [
    "BaseDetector",
    "UIFreezeDetector",
    "DuplicateRequestDetector",
    "CrashDetector",
    "StuckStateDetector",
]
