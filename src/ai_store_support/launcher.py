from __future__ import annotations

import subprocess
import sys
import time


def start_desktop() -> None:
    subprocess.Popen([sys.executable, "-m", "ai_store_support.desktop"])


def health_check(interval: int = 30) -> None:
    while True:
        time.sleep(interval)


if __name__ == "__main__":
    start_desktop()
