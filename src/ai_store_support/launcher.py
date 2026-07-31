from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .application_runtime import ApplicationRuntime
from .desktop import DesktopApp
from .paths import ApplicationPaths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-store-support-launcher")
    parser.add_argument("--data-dir", help="Override the writable application data directory")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Verify packaged imports and exit without opening the desktop window",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke_test:
        # Importing these modules exercises the hidden imports needed by the frozen app.
        from . import admin, backup, bridge, db, operation_log  # noqa: F401

        return 0

    paths = ApplicationPaths.from_env(Path(args.data_dir)) if args.data_dir else None
    runtime = ApplicationRuntime(paths=paths)
    runtime.start()
    try:
        DesktopApp(runtime.admin, runtime.registry, runtime=runtime).mainloop()
    except Exception as exc:
        runtime.status_center.record_error(str(exc))
        runtime.operation_log.record(
            "application", "fatal_error", result="error", summary="Desktop client crashed",
            details={"error": str(exc)},
        )
        raise
    finally:
        runtime.stop()
    return 0


def start_desktop() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    sys.exit(main())
