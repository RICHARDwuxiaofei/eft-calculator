from pathlib import Path

from PySide6.QtCore import QTimer

from tarkov_armor_sim.data import Database
from tarkov_armor_sim.ui import create_application

root = Path(__file__).resolve().parents[1]
app, window = create_application(Database(root / ".screenshot-data.sqlite3"))
window.resize(1440, 900)
window.show()


def capture() -> None:
    target = root / "docs" / "screenshot.png"
    if not window.grab().save(str(target), "PNG"):
        raise RuntimeError("Screenshot could not be saved")
    app.quit()


QTimer.singleShot(800, capture)
raise SystemExit(app.exec())

