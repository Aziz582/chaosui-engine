"""
Command Line Interface for ChaosUI Engine using Typer.
"""

from __future__ import annotations
import asyncio
import os
import socket
import sys
import threading
import time
from typing import List, Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from chaosui import __version__
from chaosui.core.models import ChaosConfig
from chaosui.core.engine import ChaosEngine
from chaosui.core.target_finder import TargetFinder
from chaosui.reporting.console import print_banner, print_summary
from chaosui.reporting.json_export import export_json
from chaosui.reporting.html_report import export_html
from chaosui.demo.app import run_demo_server
from playwright.async_api import async_playwright

app = typer.Typer(
    name="chaosui",
    help="ChaosUI Engine: Simulate the impatient, chaotic customer to uncover UI Freezes, duplicate requests & crashes.",
    add_completion=False,
)
console = Console()

VALID_INTENSITIES = ("low", "medium", "high", "insane")
VALID_BROWSERS = ("chromium", "firefox", "webkit")


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Polls a TCP port until it accepts connections or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def _execute_chaos_run(
    config: ChaosConfig,
    export_html_flag: bool = True,
    export_json_flag: bool = True,
    fail_on_critical: bool = False,
) -> None:
    """Shared implementation for executing a chaos session and exporting reports."""
    engine = ChaosEngine(config)

    print_banner()
    console.print(f"[bold cyan]🎯 Target:[/bold cyan] {config.target_url}")
    console.print(
        f"[bold cyan]⚙️ Intensity:[/bold cyan] {config.intensity.upper()} | "
        f"[bold cyan]Freeze Threshold:[/bold cyan] {config.freeze_threshold_ms}ms | "
        f"[bold cyan]Browser:[/bold cyan] {config.browser}"
    )
    console.print("[dim]Starting chaotic user simulation...[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Unleashing chaotic user turns...", total=config.max_actions)

        def on_progress(curr: int, total: int, desc: str):
            short_desc = desc[:45] + "..." if len(desc) > 45 else desc
            progress.update(task, completed=curr, description=f"[cyan]{short_desc}")

        engine.progress_callback = on_progress
        report = asyncio.run(engine.run())
        progress.update(task, completed=config.max_actions, description="[green]Simulation completed!")

    print_summary(report)

    saved_files: list[tuple[str, str]] = []
    if export_json_flag:
        json_path = os.path.join(config.output_dir, f"chaos_report_{report.session_id}.json")
        export_json(report, json_path)
        saved_files.append(("JSON", json_path))

    if export_html_flag:
        html_path = os.path.join(config.output_dir, f"chaos_report_{report.session_id}.html")
        export_html(report, html_path)
        saved_files.append(("HTML Dashboard", html_path))

    if saved_files:
        console.print("\n[bold green]📁 Reports Saved:[/bold green]")
        for label, path in saved_files:
            console.print(f"  • {label}: [cyan]{path}[/cyan]")

    if fail_on_critical and report.critical_faults_count > 0:
        console.print(
            f"\n[bold red]❌ Exiting with status 1 due to {report.critical_faults_count} critical UI faults.[/bold red]"
        )
        sys.exit(1)


@app.command()
def version():
    """Display ChaosUI version."""
    console.print(f"[bold cyan]ChaosUI Engine[/bold cyan] version [bold white]{__version__}[/bold white]")


@app.command()
def inspect(
    url: str = typer.Argument(..., help="The target URL to inspect for interactive targets"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
):
    """Scan and analyze interactive UI targets on a page without mutating state."""
    async def _inspect():
        console.print(f"[dim]Launching browser to inspect:[/dim] [cyan]{url}[/cyan]")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                targets = await TargetFinder.scan_page(page)
            finally:
                await browser.close()

        console.print(f"\n[bold green]Found {len(targets)} interactive targets:[/bold green]\n")
        from rich.table import Table
        t = Table(title=f"Targets on {url}")
        t.add_column("#", justify="right", width=4)
        t.add_column("Tag", width=10)
        t.add_column("Text / Label", style="cyan")
        t.add_column("Selector", style="dim")
        t.add_column("Classification", style="bold")

        for idx, target in enumerate(targets, 1):
            cl = []
            if target.is_submit:
                cl.append("[red]SUBMIT/TRANSACTION[/red]")
            if target.is_destructive:
                cl.append("[magenta]DESTRUCTIVE[/magenta]")
            if target.tag_name in ("input", "textarea", "select"):
                cl.append("[yellow]INPUT[/yellow]")
            if not cl:
                cl.append("[blue]BUTTON/CLICKABLE[/blue]")

            t.add_row(
                str(idx),
                target.tag_name,
                target.text[:40] or target.aria_label or "",
                target.selector,
                " | ".join(cl),
            )

        console.print(t)

    asyncio.run(_inspect())


@app.command()
def run(
    url: str = typer.Argument(..., help="Target URL of the web application"),
    duration: int = typer.Option(30, "--duration", "-d", help="Max duration in seconds"),
    actions: int = typer.Option(35, "--actions", "-a", help="Max chaos actions to execute"),
    intensity: str = typer.Option("high", "--intensity", "-i", help="Chaos intensity: low, medium, high, insane"),
    persona: Optional[List[str]] = typer.Option(
        None,
        "--persona",
        "-P",
        help="Filter specific personas (rage_clicker, multi_submitter, form_thrasher, nav_frenzy, scroll_thrasher)",
    ),
    browser: str = typer.Option("chromium", "--browser", "-b", help="Browser engine: chromium, firefox, webkit"),
    freeze_threshold: int = typer.Option(350, "--freeze-threshold", help="UI freeze threshold in milliseconds"),
    duplicate_window: int = typer.Option(2500, "--duplicate-window", help="Duplicate request window in milliseconds"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headless"),
    network_chaos: bool = typer.Option(True, "--network-chaos/--no-network-chaos", help="Inject artificial latency/blips"),
    html: bool = typer.Option(True, "--html/--no-html", help="Export interactive HTML report"),
    json_report: bool = typer.Option(True, "--json/--no-json", help="Export machine-readable JSON report"),
    output_dir: str = typer.Option("chaos_reports", "--output", "-o", help="Directory to save reports & screenshots"),
    fail_on_critical: bool = typer.Option(False, "--fail-on-critical", help="Exit with code 1 if critical faults are found (CI/CD)"),
):
    """Run a ChaosUI test session against a web application."""
    intensity_norm = intensity.lower()
    if intensity_norm not in VALID_INTENSITIES:
        console.print(f"[bold red]Invalid intensity '{intensity}'. Choose from: {', '.join(VALID_INTENSITIES)}[/bold red]")
        raise typer.Exit(code=2)

    browser_norm = browser.lower()
    if browser_norm not in VALID_BROWSERS:
        console.print(f"[bold red]Invalid browser '{browser}'. Choose from: {', '.join(VALID_BROWSERS)}[/bold red]")
        raise typer.Exit(code=2)

    config_kwargs = dict(
        target_url=url,
        max_duration_seconds=duration,
        max_actions=actions,
        intensity=intensity_norm,
        freeze_threshold_ms=freeze_threshold,
        duplicate_window_ms=duplicate_window,
        headless=headless,
        network_chaos=network_chaos,
        output_dir=output_dir,
        browser=browser_norm,
    )
    if persona:
        config_kwargs["personas"] = list(persona)

    config = ChaosConfig(**config_kwargs)  # type: ignore[arg-type]
    _execute_chaos_run(
        config=config,
        export_html_flag=html,
        export_json_flag=json_report,
        fail_on_critical=fail_on_critical,
    )


@app.command()
def demo(
    port: int = typer.Option(8080, "--port", "-p", help="Port for the demo server"),
    duration: int = typer.Option(15, "--duration", "-d", help="Duration for the demo run in seconds"),
    actions: int = typer.Option(25, "--actions", "-a", help="Actions to perform on demo app"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
):
    """Launch the built-in vulnerable playground server and run ChaosUI against it."""
    console.print(f"[bold cyan]🚀 Starting ChaosUI Vulnerable Playground on http://127.0.0.1:{port}[/bold cyan]")

    if not _wait_for_port("127.0.0.1", port, timeout=0.2):
        server_thread = threading.Thread(
            target=run_demo_server,
            kwargs={"host": "127.0.0.1", "port": port},
            daemon=True,
        )
        server_thread.start()
        if not _wait_for_port("127.0.0.1", port, timeout=5.0):
            console.print(f"[bold red]❌ Demo server failed to bind on port {port} within 5s.[/bold red]")
            raise typer.Exit(code=1)

    target_url = f"http://127.0.0.1:{port}"
    console.print(f"[bold green]✔ Server ready at {target_url}[/bold green]")

    demo_config = ChaosConfig(
        target_url=target_url,
        max_duration_seconds=duration,
        max_actions=actions,
        intensity="high",
        freeze_threshold_ms=350,
        duplicate_window_ms=2500,
        headless=headless,
        network_chaos=False,
        output_dir="chaos_demo_reports",
    )
    _execute_chaos_run(config=demo_config)


def main():
    app()


if __name__ == "__main__":
    main()
