#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from benjamin.core.ops.doctor import run_doctor


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BENJAMIN state files")
    parser.add_argument("--state-dir", default=None, help="State directory (defaults to BENJAMIN_STATE_DIR)")
    parser.add_argument("--repair", action="store_true", help="Repair corrupt JSONL lines safely with backup")
    parser.add_argument("--compact", action="store_true", help="Compact JSONL files with conservative retention")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON report")
    return parser.parse_args()


def _print_human(report) -> None:
    print(f"Ops Doctor report @ {report.ts_iso}")
    print(f"State dir: {report.state_dir}")
    print(f"Overall: {'OK' if report.ok else 'ATTENTION NEEDED'}")
    print()
    for item in report.files:
        status = "missing" if not item.exists else ("ok" if (item.invalid_count or 0) == 0 else "invalid")
        print(f"- {item.name}: {status}")
        print(f"  path={item.path}")
        print(f"  size={item.size_bytes}B format={item.format}")
        if item.record_count is not None:
            print(
                "  records="
                f"{item.record_count} valid={item.valid_count or 0} invalid={item.invalid_count or 0}"
            )
        if item.last_ts_iso:
            print(f"  last_ts={item.last_ts_iso}")
        for note in item.notes:
            print(f"  note: {note}")
    print()
    print(
        "Summary: "
        f"files={report.summary.total_files} missing={report.summary.missing} "
        f"invalid_lines={report.summary.invalid_lines} total_bytes={report.summary.total_bytes}"
    )


def main() -> int:
    args = _parse_args()
    report = run_doctor(state_dir=args.state_dir, repair=args.repair, compact=args.compact)

    if args.json:
        print(json.dumps(report.model_dump(), indent=2), flush=True)
    else:
        _print_human(report)

    if not report.ok and not args.repair:
        return 2
    if report.summary.missing > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
