from __future__ import annotations

from .config import AppConfig
from .gui import run_app
from .logging_utils import setup_logging


def main() -> None:
    setup_logging()
    run_app(AppConfig())


if __name__ == "__main__":
    main()
