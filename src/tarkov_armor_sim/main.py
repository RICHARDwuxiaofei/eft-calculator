from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

from . import __version__
from .data import DATA_VERSION, Database, default_database_path

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
        "community-approx-2026.07-v1",
    )


def main() -> int:
    configure_logging()
    from .ui import create_application

    database = Database(default_database_path())
    app, window = create_application(database)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
