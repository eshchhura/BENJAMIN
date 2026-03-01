#!/usr/bin/env python3
"""Repo-standard test runner."""

from __future__ import annotations

import subprocess
import sys


def run(command: list[str]) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    print(f"Python interpreter: {sys.executable}", flush=True)
    try:
        run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"])
        run([sys.executable, "-m", "pytest", "-q"])
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
