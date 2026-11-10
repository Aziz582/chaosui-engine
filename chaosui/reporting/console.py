"""
Terminal output formatting using Rich for ChaosUI Engine.
"""

from __future__ import annotations
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from chaosui.core.models import ChaosReport, Severity, FaultType

console = Console()

SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "bold magenta",
    Severity.MEDIUM: "bold yellow",
    Severity.LOW: "bold cyan",
}

FAULT_ICONS = {
    FaultType.UI_FREEZE: "❄️ [UI Freeze]",
    FaultType.DUPLICATE_REQUEST: "🔁 [Duplicate Request]",
    FaultType.CRASH: "💥 [Crash / Error]",
    FaultType.STUCK_STATE: "⏳ [Stuck State]",
}


def print_banner():
    banner_text = Text()
    banner_text.append("⚡ ChaosUI Engine ⚡\n", style="bold cyan")
    banner_text.append("Intelligent UI Chaos Testing for Modern Web Applications\n", style="bold white")
    banner_text.append("Simulating the Impatient, Chaotic Customer (العميل المشاغب والمستعجل)", style="dim italic")
    console.print(Panel(banner_text, box=box.ROUNDED, border_style="cyan"))


def print_summary(report: ChaosReport):
    console.print("\n")
    print_banner()

    # Metrics Summary Table
    table = Table(title="Execution Summary", box=box.ROUNDED, header_style="bold blue")
    table.add_column("Target URL", style="cyan")
    table.add_column("Duration", justify="right")
    table.add_column("Actions", justify="right")
    table.add_column("Total Faults", justify="right")
    table.add_column("Critical", justify="right", style="bold red")
    table.add_column("High", justify="right", style="bold magenta")

    table.add_row(
        report.target_url,
        f"{report.duration_seconds}s",
        str(report.total_actions),
        str(len(report.faults)),
        str(report.critical_faults_count),
        str(report.high_faults_count),
    )
    console.print(table)

    if not report.has_faults:
        console.print(
            Panel("✨ [bold green]PASSED[/bold green]: No UI Freezes, Crashes, or Duplicate Requests detected!", style="green")
        )
        return

    # Faults Breakdown Table
    fault_table = Table(title="🚨 Detected UI Faults & Invariant Breaches", box=box.ROUNDED, header_style="bold red")
    fault_table.add_column("#", justify="right", width=4)
    fault_table.add_column("Severity", justify="center", width=12)
    fault_table.add_column("Type", width=24)
    fault_table.add_column("Incident Title", style="white")
    fault_table.add_column("Key Evidence", style="dim")

    for idx, fault in enumerate(report.faults, 1):
        sev_style = SEVERITY_COLORS.get(fault.severity, "white")
        icon = FAULT_ICONS.get(fault.fault_type, str(fault.fault_type))
        evidence_str = ""
        if "duration_ms" in fault.evidence:
            evidence_str = f"Freeze: {fault.evidence['duration_ms']}ms"
        elif "gap_ms" in fault.evidence:
            evidence_str = f"Gap: {fault.evidence['gap_ms']}ms ({fault.evidence.get('duplicate_count', 2)}x)"
        elif "message" in fault.evidence:
            evidence_str = fault.evidence["message"][:40] + "..."

        fault_table.add_row(
            str(idx),
            Text(fault.severity.value, style=sev_style),
            icon,
            fault.title,
            evidence_str,
        )

    console.print(fault_table)

    # Incident Details and Reproduction
    console.print("\n[bold yellow]🔍 Top Incident Diagnostic Details:[/bold yellow]")
    for idx, fault in enumerate(report.faults[:3], 1):
        content = Text()
        content.append(f"Title: {fault.title}\n", style="bold white")
        content.append(f"Description: {fault.description}\n", style="dim")
        if fault.screenshot_path:
            content.append(f"Screenshot: {fault.screenshot_path}\n", style="cyan")
        if fault.reproduction_steps:
            content.append("\nReproduction Trail:\n", style="bold green")
            for step in fault.reproduction_steps:
                content.append(f"  • {step}\n", style="green")

        console.print(Panel(content, title=f"Incident #{idx} [{fault.severity.value}]", border_style=SEVERITY_COLORS.get(fault.severity, "white")))
