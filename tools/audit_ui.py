"""Render real Qt controls with isolated settings/databases and no visible windows."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("EFT_CALCULATOR_LANG", "zh_CN")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.ui import create_application


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="after")
    args = parser.parse_args()
    target = Path("artifacts/audit-2026-10-25/ui") / args.label
    target.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    evidence = []
    with tempfile.TemporaryDirectory() as folder:
        os.environ["LOCALAPPDATA"] = folder
        os.environ["EFT_TEST_SETTINGS_DIRECTORY"] = folder
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, folder)
        database = Database(Path(folder)/"ui.sqlite3")
        app, window = create_application(database)
        window.shots.setValue(1)
        window._choose_preset(0)
        window._analyze()
        window.show()
        for width, height in ((1280,720), (1920,1080), (2560,1440), (390,844), (360,640)):
            window.resize(width, height)
            for _ in range(6):
                app.processEvents()
                time.sleep(.04)
            assert window.grab().save(str(target/f"{width}x{height}.png"))
            evidence.append({"width": window.width(), "height": window.height(),
                             "input_minimum_width": window.input_panel.minimumSizeHint().width()})
        window._open_armor_editor()
        app.processEvents()
        window.armor_dialog.grab().save(str(target/"armor-editor.png"))
        window.armor_dialog.close()
        window.close()
        window.thread_pool.waitForDone(10000)
        app.processEvents()
        database.connection.close()
    (target/"checks.json").write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
