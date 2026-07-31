from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tarkov_armor_sim.sync import SnapshotStore, run_sync


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("build/sync-cache"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    report = run_sync(SnapshotStore(args.output), force=args.force)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
