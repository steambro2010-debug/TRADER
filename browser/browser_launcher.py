from dataclasses import dataclass
from threading import Event
from typing import Optional


@dataclass
class BrowserSession:
    page: object
    playwright: object
    browser: object
    context: object


class BrowserLauncher:
    def __init__(self, logger) -> None:
        self.logger = logger
        self.session: Optional[BrowserSession] = None

    def launch(self, url: str, stop_event: Event) -> Optional[BrowserSession]:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            self.logger.error("Playwright unavailable, cannot launch embedded Chromium: %s", exc)
            return None

        self.logger.info("Launching Chromium and opening Quotex...")
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")

        self.session = BrowserSession(page=page, playwright=playwright, browser=browser, context=context)
        self._wait_for_login(page, stop_event)
        return self.session

    def _wait_for_login(self, page: object, stop_event: Event) -> None:
        self.logger.info("Waiting for user login on Quotex...")
        while not stop_event.is_set():
            current_url = page.url.lower()
            if "trade" in current_url or "trader" in current_url:
                self.logger.info("Login detected. Continuing automation flow.")
                return
            try:
                page.wait_for_timeout(1000)
            except Exception:
                return

    def close(self) -> None:
        if not self.session:
            return
        self.logger.info("Closing browser session...")
        try:
            self.session.context.close()
            self.session.browser.close()
            self.session.playwright.stop()
        except Exception:
            pass
        self.session = None
