from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from core.orchestrator import TradingOrchestrator
from utils.config import load_config
from utils.logger import setup_logging


def main() -> None:
    config = load_config()
    setup_logging(config.runtime.debug)

    app = QApplication(sys.argv)
    orchestrator = TradingOrchestrator(app, config)
    orchestrator.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
