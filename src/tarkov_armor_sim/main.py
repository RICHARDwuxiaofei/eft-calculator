from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

from . import __version__
from .data import DATA_VERSION, Database, default_database_path
from .legacy_db import repair_legacy_ammo_payloads
from .rulesets import CurrentApproximation

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    log_dir = Path.home() / ".tarkov-armor-simulator" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "application.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOGGER.info(
        "start app=%s python=%s os=%s data=%s ruleset=%s",
        __version__,
        sys.version.split()[0],
        platform.platform(),
        DATA_VERSION,
        CurrentApproximation.metadata.version,
    )


def main() -> int:
    configure_logging()
    from .ui import create_application

    database_path = default_database_path()
    repaired_rows = repair_legacy_ammo_payloads(database_path)
    if repaired_rows:
        LOGGER.warning("repaired %d legacy ammo payload(s) before startup", repaired_rows)
    database = Database(database_path)
    app, window = create_application(database)
    window.show()
    if "--smoke-test" in sys.argv:
        import os

        from PySide6.QtCore import QTimer

        from .engine import analyze

        window.shots.setValue(1)
        window._choose_preset(0)
        result = analyze(window._scenario(), CurrentApproximation())
        assert 0 <= result.final_penetration_probability <= 1
        window.current_scenario = window._scenario()
        window._show_result(result)

        def finish_smoke() -> None:
            screenshot = os.getenv("EFT_SMOKE_SCREENSHOT")
            if screenshot and not window.grab().save(screenshot):
                app.exit(2)
                return
            window.close()
            app.quit()

        QTimer.singleShot(1500, finish_smoke)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
