"""One dry-run tick of the Hermes research lead. HERMES-AUTONOMOUS-RESEARCH-002.

This shell owns everything the pure package may not: the clock, the port observation, the process
observation, the git observation and the test run. It calls ``tick`` exactly once and exits. It
contains no loop, installs nothing, and registers nothing anywhere -- keeping an unattended loop
running is an owner act this script cannot perform.

The only mode is DRY_RUN and the parser enforces it: ``--mode`` accepts one choice. A live mode is
not a hidden flag away; it does not exist.

Invocation (from the repository root, which supplies the import path)::

    python scripts/hermes_research_tick.py --lead-root <the lead's own directory>

The port observation is a client connect to 127.0.0.1:8644 -- observing whether something listens,
never listening. ``--skip-tests`` records ``tests_passing=False``, not ``True``: an unverified
suite is a failing suite as far as a governance gate is concerned.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PROTECTED_PREFIXES = ("evolith_core", "integrations", "tests", "scripts", "docs", "pyproject.toml")
"""Dirty paths under these refuse a tick. Untracked scratch elsewhere in the tree does not."""

FOCUSED_TESTS = ("tests/hermes_research_orchestrator",)
"""The declared test selection a tick verifies. Focused on purpose: the tick gate asks whether the
lead's own guarantees hold on this working tree."""

GATEWAY_PORT = 8644


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One dry-run tick of the Hermes research lead. Runs once and exits.")
    parser.add_argument("--lead-root", required=True,
                        help="The directory the research lead owns. Never defaulted.")
    parser.add_argument("--mode", choices=[m.value for m in _runner().RunnerMode],
                        default="DRY_RUN",
                        help="DRY_RUN is the only mode that exists.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT),
                        help="The Evolith checkout to observe (git status, tests).")
    parser.add_argument("--skip-tests", action="store_true",
                        help="Record tests_passing=False without running them. Fails closed: "
                             "an unverified suite gates exactly like a failing one.")
    return parser


def _runner():
    from integrations.hermes_research_orchestrator import runner
    return runner


def observe_port_open(port: int = GATEWAY_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def observe_gateway_running() -> bool:
    """Whether a hermes gateway process exists, judged by command line, not by a state file.

    ``gateway_state.json`` has read ``running`` after a clean stop before; the process table is the
    only liveness source this script trusts.
    """
    query = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'hermes' "
             "-and $_.CommandLine -match 'gateway' -and $_.CommandLine -notmatch 'CimInstance' } "
             "| Measure-Object | Select-Object -ExpandProperty Count")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", query],
                                capture_output=True, text=True, timeout=30)
        return int(result.stdout.strip() or 0) > 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return True     # an observation that failed is not an observation of absence


def observe_git_dirty(repo_root: str) -> tuple:
    try:
        result = subprocess.run(["git", "-C", repo_root, "status", "--porcelain"],
                                capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ("git status unavailable",)      # unobservable is not clean
    dirty = []
    for line in result.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if path.startswith(PROTECTED_PREFIXES):
            dirty.append(path)
    return tuple(dirty)


def observe_tests_passing(repo_root: str, skip: bool) -> bool:
    if skip:
        return False
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *FOCUSED_TESTS, "-q", "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=repo_root, timeout=600)
    return result.returncode == 0


def main(argv: list | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    runner = _runner()
    observations = runner.TickObservations(
        observed_at=datetime.now(timezone.utc).isoformat(),
        tests_passing=observe_tests_passing(arguments.repo_root, arguments.skip_tests),
        native_gateway_running=observe_gateway_running(),
        gateway_port_open=observe_port_open(),
        git_dirty_protected_paths=observe_git_dirty(arguments.repo_root))
    summary = runner.tick(
        lead_root=arguments.lead_root,
        observations=observations,
        pid=os.getpid(),
        start_token=uuid.uuid4().hex)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
