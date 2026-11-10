"""
Interactive HTML Dashboard Report Generator for ChaosUI Engine.
"""

from __future__ import annotations
import os
import json
from jinja2 import Template
from chaosui.core.models import ChaosReport

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChaosUI Report - {{ report.target_url }}</title>
    <style>
        :root {
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --border: #334155;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --red: #f43f5e;
            --orange: #fb923c;
            --yellow: #facc15;
            --green: #4ade80;
            --purple: #c084fc;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            padding: 2rem 1rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 2rem;
        }
        .brand { display: flex; align-items: center; gap: 0.75rem; }
        .brand h1 { font-size: 1.75rem; font-weight: 800; color: var(--accent); }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .badge-CRITICAL { background: rgba(244, 63, 94, 0.2); color: var(--red); border: 1px solid var(--red); }
        .badge-HIGH { background: rgba(251, 146, 60, 0.2); color: var(--orange); border: 1px solid var(--orange); }
        .badge-MEDIUM { background: rgba(250, 204, 21, 0.2); color: var(--yellow); border: 1px solid var(--yellow); }
        .badge-LOW { background: rgba(56, 189, 248, 0.2); color: var(--accent); border: 1px solid var(--accent); }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2.5rem;
        }
        .metric-card {
            background: var(--surface);
            padding: 1.25rem;
            border-radius: 0.75rem;
            border: 1px solid var(--border);
        }
        .metric-card .title { font-size: 0.85rem; color: var(--text-muted); font-weight: 600; }
        .metric-card .value { font-size: 2rem; font-weight: 800; margin-top: 0.5rem; }

        .section-title {
            font-size: 1.35rem;
            font-weight: 700;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .fault-card {
            background: var(--surface);
            border-radius: 0.75rem;
            border: 1px solid var(--border);
            padding: 1.25rem;
            margin-bottom: 1.25rem;
            transition: border-color 0.2s;
        }
        .fault-card:hover { border-color: var(--accent); }
        .fault-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
        }
        .fault-title { font-size: 1.15rem; font-weight: 700; }
        .fault-desc { color: var(--text-muted); margin-bottom: 1rem; }
        
        .evidence-box {
            background: rgba(15, 23, 42, 0.7);
            border-radius: 0.5rem;
            padding: 0.75rem 1rem;
            font-family: monospace;
            font-size: 0.85rem;
            margin-bottom: 1rem;
            overflow-x: auto;
            border-left: 3px solid var(--accent);
        }

        .repro-steps {
            background: rgba(15, 23, 42, 0.5);
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            font-size: 0.9rem;
        }
        .repro-steps ol { margin-left: 1.5rem; }
        .repro-steps li { margin-bottom: 0.35rem; }

        .timeline {
            background: var(--surface);
            border-radius: 0.75rem;
            border: 1px solid var(--border);
            padding: 1.5rem;
            margin-top: 2rem;
            max-height: 400px;
            overflow-y: auto;
        }
        .timeline-item {
            display: flex;
            gap: 1rem;
            padding-bottom: 0.75rem;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.9rem;
        }
        .timeline-time { color: var(--text-muted); font-family: monospace; min-width: 65px; }
        .timeline-act { font-weight: 600; color: var(--accent); min-width: 120px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <span>⚡</span>
                <div>
                    <h1>ChaosUI Engine Report</h1>
                    <p style="color: var(--text-muted); font-size: 0.9rem;">Target: {{ report.target_url }} | Session: {{ report.session_id }}</p>
                </div>
            </div>
            <div>
                <span class="badge badge-{% if report.critical_faults_count > 0 %}CRITICAL{% elif report.has_faults %}HIGH{% else %}LOW{% endif %}">
                    {% if report.has_faults %}{{ report.faults | length }} Faults Detected{% else %}ALL INVARIANTS PASSED{% endif %}
                </span>
            </div>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="title">Total Actions</div>
                <div class="value" style="color: var(--accent);">{{ report.total_actions }}</div>
            </div>
            <div class="metric-card">
                <div class="title">Execution Duration</div>
                <div class="value">{{ report.duration_seconds }}s</div>
            </div>
            <div class="metric-card">
                <div class="title">Critical Faults</div>
                <div class="value" style="color: var(--red);">{{ report.critical_faults_count }}</div>
            </div>
            <div class="metric-card">
                <div class="title">UI Freezes</div>
                <div class="value" style="color: var(--purple);">{{ report.metrics.freeze_events }}</div>
            </div>
            <div class="metric-card">
                <div class="title">Duplicate Mutations</div>
                <div class="value" style="color: var(--orange);">{{ report.metrics.duplicate_requests_detected }}</div>
            </div>
        </div>

        <div class="section-title">🚨 Detected Faults & Invariant Breaches</div>
        {% if not report.has_faults %}
            <div class="fault-card" style="border-color: var(--green);">
                <div class="fault-title" style="color: var(--green);">✨ Clean Bill of Health!</div>
                <div class="fault-desc">No UI freezes, un-debounced duplicate requests, or unhandled crashes were triggered by the chaotic user.</div>
            </div>
        {% endif %}

        {% for fault in report.faults %}
            <div class="fault-card">
                <div class="fault-header">
                    <div>
                        <span class="badge badge-{{ fault.severity.value }}">{{ fault.severity.value }}</span>
                        <span class="badge" style="background: rgba(255,255,255,0.1); margin-left: 0.5rem;">{{ fault.fault_type.value }}</span>
                        <div class="fault-title" style="margin-top: 0.5rem;">{{ fault.title }}</div>
                    </div>
                </div>
                <div class="fault-desc">{{ fault.description }}</div>

                {% if fault.evidence %}
                <div class="evidence-box">
                    <strong>Evidence Telemetry:</strong>
                    <pre>{{ fault.evidence | tojson(indent=2) }}</pre>
                </div>
                {% endif %}

                {% if fault.reproduction_steps %}
                <div class="repro-steps">
                    <strong>Reproduction Steps Trail:</strong>
                    <ol>
                        {% for step in fault.reproduction_steps %}
                        <li>{{ step }}</li>
                        {% endfor %}
                    </ol>
                </div>
                {% endif %}
            </div>
        {% endfor %}

        <div class="section-title" style="margin-top: 2.5rem;">📜 Action Replay Log (Last 20 Actions)</div>
        <div class="timeline">
            {% for act in report.action_history[-20:] %}
            <div class="timeline-item">
                <span class="timeline-time">+{{ loop.index }}</span>
                <span class="timeline-act">{{ act.action_type.value }}</span>
                <span>{{ act.description }}</span>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""


def export_html(report: ChaosReport, output_path: str) -> str:
    """Renders and writes standalone HTML dashboard report."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    template = Template(HTML_TEMPLATE)
    html_content = template.render(report=report)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path
