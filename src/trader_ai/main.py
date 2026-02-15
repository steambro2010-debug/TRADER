from __future__ import annotations

from .config import AppConfig
from .pipeline import RealtimePipeline
from .ui import TradingSignalUI


def main() -> None:
    config = AppConfig()
    pipeline = RealtimePipeline(config)
    ui = TradingSignalUI(pipeline)
    ui.run()


if __name__ == "__main__":
    main()
