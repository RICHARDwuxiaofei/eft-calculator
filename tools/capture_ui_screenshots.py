"""Capture deterministic UI screenshots at the desktop acceptance sizes."""

from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import QTimer

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.ui import create_application

SIZES = ((1280, 720), (1920, 1080), (2560, 1440))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("before", "after"))
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = root / "docs" / "screenshots" / args.phase
    output_dir.mkdir(parents=True, exist_ok=True)
    app, window = create_application(Database(root / ".screenshot-data.sqlite3"))
    index = 0

    def capture_next() -> None:
        nonlocal index
        if index >= len(SIZES):
            app.quit()
            return
        width, height = SIZES[index]
        window.resize(width, height)
        window.show()
        app.processEvents()
        target = output_dir / f"{width}x{height}.png"
        if not window.grab().save(str(target), "PNG"):
            raise RuntimeError(f"Screenshot could not be saved: {target}")
        index += 1
        QTimer.singleShot(250, capture_next)

    QTimer.singleShot(800, capture_next)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
