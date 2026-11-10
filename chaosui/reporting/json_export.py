"""
JSON serialization and export for ChaosUI reports.
"""

from __future__ import annotations
import json
import os
from dataclasses import asdict
from chaosui.core.models import ChaosReport


def export_json(report: ChaosReport, output_path: str) -> str:
    """Exports a ChaosReport to a JSON file."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    data = {
        "session_id": report.session_id,
        "target_url": report.target_url,
        "start_time": report.start_time,
        "duration_seconds": report.duration_seconds,
        "total_actions": report.total_actions,
        "metrics": report.metrics,
        "critical_count": report.critical_faults_count,
        "high_count": report.high_faults_count,
        "faults": [
            {
                "fault_type": f.fault_type.value,
                "severity": f.severity.value,
                "title": f.title,
                "description": f.description,
                "timestamp": f.timestamp,
                "evidence": f.evidence,
                "reproduction_steps": f.reproduction_steps,
                "screenshot_path": f.screenshot_path,
            }
            for f in report.faults
        ],
        "action_history": [
            {
                "action_type": a.action_type.value,
                "description": a.description,
                "timestamp": a.timestamp,
                "selector": a.selector,
            }
            for a in report.action_history
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path
