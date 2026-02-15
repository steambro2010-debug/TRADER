from __future__ import annotations

import asyncio

from core.orchestrator import TradingOrchestrator
from utils.config import load_config
from utils.logger import setup_logging


def main() -> None:
    config = load_config()
    setup_logging(config.runtime.debug)
    orchestrator = TradingOrchestrator(config)
    asyncio.run(orchestrator.run())


if __name__ == "__main__":
    main()
