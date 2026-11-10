"""
End-to-end integration test running ChaosEngine against the local vulnerable playground.
"""

import pytest
import threading
import time
from chaosui.core.models import ChaosConfig
from chaosui.core.engine import ChaosEngine
from chaosui.demo.app import run_demo_server


@pytest.fixture(scope="module")
def demo_server():
    port = 8899
    thread = threading.Thread(
        target=run_demo_server,
        kwargs={"host": "127.0.0.1", "port": port},
        daemon=True,
    )
    thread.start()
    time.sleep(1.0)
    yield f"http://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_chaos_engine_detects_demo_vulnerabilities(demo_server, tmp_path):
    config = ChaosConfig(
        target_url=demo_server,
        max_duration_seconds=10,
        max_actions=18,
        intensity="high",
        freeze_threshold_ms=300,
        duplicate_window_ms=2000,
        headless=True,
        network_chaos=False,
        output_dir=str(tmp_path / "reports"),
    )

    engine = ChaosEngine(config)
    report = await engine.run()

    # Verify that the engine ran actions
    assert report.total_actions > 0
    assert report.duration_seconds > 0

    # Verify that real-world faults were caught by the Impatient User simulation
    fault_types = {f.fault_type for f in report.faults}
    print("Caught Fault Types:", fault_types)
    assert len(report.faults) > 0
