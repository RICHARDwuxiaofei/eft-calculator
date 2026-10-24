from __future__ import annotations

import logging
import os
import platform
import sys
from pathlib import Path

from . import __version__
from .data import DATA_VERSION, Database, default_database_path
from .rulesets import CurrentApproximation

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    log_dir = Path(os.environ["EFT_LOG_DIRECTORY"]) if "EFT_LOG_DIRECTORY" in os.environ else Path.home() / ".tarkov-armor-simulator" / "logs"
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
    database = Database(database_path)
    if database.recovery_backup:
        LOGGER.warning("Unreadable database preserved at %s", database.recovery_backup)
    app, window = create_application(database)
    if "--smoke-test" in sys.argv:
        window.resize(1280, 720)
    window.show()
    if "--smoke-test" in sys.argv:
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
