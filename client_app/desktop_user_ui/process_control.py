from __future__ import annotations

import os
import signal
import subprocess


def pids_for_port(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return sorted(set(pids))


def terminate_pids(pids: list[int], *, force: bool = False) -> list[int]:
    signal_type = signal.SIGKILL if force else signal.SIGTERM
    current_pid = os.getpid()
    stopped: list[int] = []
    for pid in pids:
        if pid == current_pid:
            continue
        try:
            os.kill(pid, signal_type)
        except ProcessLookupError:
            continue
        stopped.append(pid)
    return stopped
