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

        self.logger.info("Launching Chromium and opening Quotex/Qxbroker...")
        playwright = sync_playwright().start()

        launch_args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-infobars",
        ]

        try:
            browser = playwright.chromium.launch(headless=False, channel="chrome", args=launch_args)
        except Exception:
            browser = playwright.chromium.launch(headless=False, args=launch_args)

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="UTC",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || { runtime: {} };
            """
        )

        page = context.new_page()

        urls_to_try = [url]
        if "qxbroker.com" not in url:
            urls_to_try.append("https://qxbroker.com/en/sign-in")

        loaded = False
        for candidate in urls_to_try:
            try:
                self.logger.info("Opening %s", candidate)
                page.goto(candidate, wait_until="domcontentloaded", timeout=60_000)
                loaded = True
                break
            except Exception as exc:
                self.logger.warning("Failed to open %s: %s", candidate, exc)

        if not loaded:
            self.logger.error("Unable to open Quotex/Qxbroker login page.")
            try:
                context.close()
                browser.close()
                playwright.stop()
            except Exception:
                pass
            return None

        self.session = BrowserSession(page=page, playwright=playwright, browser=browser, context=context)
        self._wait_for_security_check(page, stop_event)
        self._wait_for_login(page, stop_event)
        return self.session

    def _wait_for_security_check(self, page: object, stop_event: Event) -> None:
        self.logger.info("Checking for anti-bot verification page...")
        while not stop_event.is_set():
            if not self._is_security_check(page):
                return
            self.logger.info("Security verification detected, waiting for challenge completion...")
            try:
                page.wait_for_timeout(2500)
                page.reload(wait_until="domcontentloaded", timeout=30_000)
            except Exception:
                try:
                    page.wait_for_timeout(2500)
                except Exception:
                    return

    def _is_security_check(self, page: object) -> bool:
        try:
            title = (page.title() or "").lower()
        except Exception:
            title = ""
        try:
            body = (page.inner_text("body") or "").lower()
        except Exception:
            body = ""
        try:
            current_url = (page.url or "").lower()
        except Exception:
            current_url = ""

        markers = [
            "performing security verification",
            "verifies you are not a bot",
            "security service",
            "checking your browser",
            "cf-challenge",
        ]
        target = f"{title}\n{body}\n{current_url}"
        return any(m in target for m in markers)

    def _wait_for_login(self, page: object, stop_event: Event) -> None:
        self.logger.info("Waiting for user login on Quotex/Qxbroker...")
        while not stop_event.is_set():
            if self._is_security_check(page):
                self._wait_for_security_check(page, stop_event)

            try:
                current_url = (page.url or "").lower()
            except Exception:
                current_url = ""

            if any(token in current_url for token in ["trade", "trader", "cabinet", "terminal"]):
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
