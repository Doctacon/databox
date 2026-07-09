#!/usr/bin/env python3
"""Run the loopback FastAPI and Vite development servers together."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "databox.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT,
            env=env,
        ),
        subprocess.Popen(["npm", "run", "dev"], cwd=ROOT / "app", env=env),
    ]
    print("Birding Trip Copilot: http://127.0.0.1:5173", flush=True)
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    return next((process.returncode or 0 for process in processes if process.returncode), 0)


if __name__ == "__main__":
    raise SystemExit(main())
