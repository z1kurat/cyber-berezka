"""Tests for generate_xray_outbounds.py modes."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_xray_outbounds.py"


def run(stdin: str, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_ipv4_only_mode_emits_single_freedom_outbound():
    """ipv4-only mode generates one freedom outbound, no IPv6, no balancer."""
    cfg = run("", "--mode", "ipv4-only")
    assert "outbounds" in cfg
    assert "routing" in cfg

    tags = [o["tag"] for o in cfg["outbounds"]]
    assert "v4-direct" in tags
    assert "direct" in tags
    assert "block" in tags
    assert not any(t.startswith("v6-") for t in tags), f"unexpected v6 outbound: {tags}"

    assert cfg["routing"].get("balancers") in (None, [])
    rules = cfg["routing"]["rules"]
    catchall = next((r for r in rules if r.get("ip") == ["0.0.0.0/0"]), None)
    assert catchall is not None
    assert catchall["outboundTag"] == "v4-direct"


def test_ipv6_pool_mode_unchanged_behavior():
    """ipv6-pool mode (current default) preserves random balancer."""
    pool = "2a03:6f02::8316\n2a03:6f02::c8af\n"
    cfg = run(pool, "--mode", "ipv6-pool")
    tags = [o["tag"] for o in cfg["outbounds"]]
    assert "v6-0000" in tags
    assert "v6-0001" in tags
    assert "v4-fallback" in tags
    assert cfg["routing"]["balancers"][0]["tag"] == "v6-pool"


def test_default_mode_is_ipv6_pool_for_back_compat():
    """Without --mode flag, behavior matches old script (ipv6-pool)."""
    pool = "2a03:6f02::8316\n"
    cfg = run(pool)
    tags = [o["tag"] for o in cfg["outbounds"]]
    assert any(t.startswith("v6-") for t in tags)


def test_ipv4_only_mode_ignores_stdin():
    """ipv4-only mode does not require IPv6 pool on stdin."""
    cfg = run("# ignored\n2a03:6f02::8316\n", "--mode", "ipv4-only")
    tags = [o["tag"] for o in cfg["outbounds"]]
    assert not any(t.startswith("v6-") for t in tags)
