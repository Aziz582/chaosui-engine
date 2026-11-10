"""
Interactive HTML Dashboard Report Generator for ChaosUI Engine.
"""

from __future__ import annotations
import json
import os
from jinja2 import Environment
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
            flex-wrap: wrap;
            gap: 1rem;
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
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .section-title {
            font-size: 1.35rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .filter-bar { display: flex; gap: 0.5rem; flex-wrap: wrap; }
        .filter-btn {
            background: var(--surface);
            color: var(--text-muted);
            border: 1px solid var(--border);
            padding: 0.35rem 0.75rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .filter-btn.active, .filter-btn:hover {
            border-color: var(--accent);
            color: var(--accent);
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
            margin-bottom: 1rem;
        }
        .repro-steps ol { margin-left: 1.5rem; margin-top: 0.35rem; }
        .repro-steps li { margin-bottom: 0.35rem; }

        .screenshot-details summary {
            cursor: pointer;
            color: var(--accent);
            font-size: 0.9rem;
            font-weight: 600;
            margin-top: 0.5rem;
        }
        .screenshot-img {
            max-width: 100%;
            border-radius: 0.5rem;
            border: 1px solid var(--border);
            margin-top: 0.75rem;
        }

        .timeline {
            background: var(--surface);
            border-radius: 0.75rem;
            border: 1px solid var(--border);
            padding: 1.5rem;
            margin-top: 1rem;
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
        .timeline-act { font-weight: 600; color: var(--accent); min-width: 140px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <span style="font-size: 2rem;">⚡</span>
                <div>
                    <h1>ChaosUI Engine Report</h1>
                    <p style="color: var(--text-muted); font-size: 0.9rem;">Target: {{ report.target_url }} | Session: {{ report.session_id }} | Started: {{ report.start_time }}</p>
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

        <div class="section-header">
            <div class="section-title">🚨 Detected Faults &amp; Invariant Breaches</div>
            {% if report.has_faults %}
            <div class="filter-bar">
                <button class="filter-btn active" onclick="filterFaults('ALL', this)">All ({{ report.faults | length }})</button>
                <button class="filter-btn" onclick="filterFaults('UI_FREEZE', this)">UI Freezes</button>
                <button class="filter-btn" onclick="filterFaults('DUPLICATE_REQUEST', this)">Duplicate Requests</button>
                <button class="filter-btn" onclick="filterFaults('CRASH', this)">Crashes</button>
                <button class="filter-btn" onclick="filterFaults('STUCK_STATE', this)">Stuck States</button>
            </div>
            {% endif %}
        </div>

        {% if not report.has_faults %}
            <div class="fault-card" style="border-color: var(--green);">
                <div class="fault-title" style="color: var(--green);">✨ Clean Bill of Health!</div>
                <div class="fault-desc">No UI freezes, un-debounced duplicate requests, or unhandled crashes were triggered by the chaotic user.</div>
            </div>
        {% endif %}

        {% for item in fault_items %}
            <div class="fault-card" data-fault-type="{{ item.fault.fault_type.value }}">
                <div class="fault-header">
                    <div>
                        <span class="badge badge-{{ item.fault.severity.value }}">{{ item.fault.severity.value }}</span>
                        <span class="badge" style="background: rgba(255,255,255,0.1); margin-left: 0.5rem;">{{ item.fault.fault_type.value }}</span>
                        <div class="fault-title" style="margin-top: 0.5rem;">{{ item.fault.title }}</div>
                    </div>
                </div>
                <div class="fault-desc">{{ item.fault.description }}</div>

                {% if item.evidence_json %}
                <div class="evidence-box">
                    <strong>Evidence Telemetry:</strong>
                    <pre>{{ item.evidence_json }}</pre>
                </div>
                {% endif %}

                {% if item.fault.reproduction_steps %}
                <div class="repro-steps">
                    <strong>Reproduction Steps Trail:</strong>
                    <ol>
                        {% for step in item.fault.reproduction_steps %}
                        <li>{{ step }}</li>
                        {% endfor %}
                    </ol>
                </div>
                {% endif %}

                {% if item.rel_screenshot %}
                <details class="screenshot-details">
                    <summary>📸 View Captured Fault Screenshot</summary>
                    <img class="screenshot-img" src="{{ item.rel_screenshot }}" alt="Screenshot for {{ item.fault.title }}" loading="lazy" />
                </details>
                {% endif %}
            </div>
        {% endfor %}

        <div class="section-title" style="margin-top: 2.5rem;">📜 Action Replay Log (Last 30 Actions)</div>
        <div class="timeline">
            {% for act in report.action_history[-30:] %}
            <div class="timeline-item">
                <span class="timeline-time">#{{ loop.index }}</span>
                <span class="timeline-act">{{ act.action_type.value }}</span>
                <span>{{ act.description }}</span>
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
        function filterFaults(type, btn) {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.fault-card[data-fault-type]').forEach(card => {
                card.style.display = (type === 'ALL' || card.dataset.faultType === type) ? 'block' : 'none';
            });
        }
    </script>
</body>
</html>
"""


def export_html(report: ChaosReport, output_path: str) -> str:
    """Renders and writes standalone HTML dashboard report with auto-escaping enabled."""
    abs_output = os.path.abspath(output_path)
    report_dir = os.path.dirname(abs_output)
    os.makedirs(report_dir, exist_ok=True)

    fault_items = []
    for fault in report.faults:
        rel_shot = None
        if fault.screenshot_path and os.path.exists(fault.screenshot_path):
            try:
                rel_shot = os.path.relpath(os.path.abspath(fault.screenshot_path), report_dir)
            except ValueError:
                rel_shot = fault.screenshot_path

        evidence_json = json.dumps(fault.evidence, indent=2, ensure_ascii=False) if fault.evidence else ""
        fault_items.append(
            {
                "fault": fault,
                "rel_screenshot": rel_shot,
                "evidence_json": evidence_json,
            }
        )

    env = Environment(autoescape=True)
    template = env.from_string(HTML_TEMPLATE)
    html_content = template.render(report=report, fault_items=fault_items)
    with open(abs_output, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path
