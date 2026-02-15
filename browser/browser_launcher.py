from dataclasses import dataclass
from pathlib import Path
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

    def launch(
        self,
        url: str,
        stop_event: Event,
        profile_dir: str = ".browser_profile",
        security_timeout_sec: int = 240,
    ) -> Optional[BrowserSession]:
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
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        user_data_dir = str(Path(profile_dir).resolve())

        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                channel="chrome",
                args=launch_args,
                locale="en-US",
                timezone_id="UTC",
                viewport={"width": 1440, "height": 900},
            )
        except Exception:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=launch_args,
                locale="en-US",
                timezone_id="UTC",
                viewport={"width": 1440, "height": 900},
            )

        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        pages = context.pages
        page = pages[0] if pages else context.new_page()

        urls_to_try = [url]
        if "qxbroker.com" not in (url or "").lower():
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
                playwright.stop()
            except Exception:
                pass
            return None

        self.session = BrowserSession(page=page, playwright=playwright, browser=context.browser, context=context)
        self._wait_for_security_check(page, stop_event, timeout_sec=security_timeout_sec)
        self._wait_for_login(page, stop_event)
        return self.session

    def _wait_for_security_check(self, page: object, stop_event: Event, timeout_sec: int = 240) -> None:
        self.logger.info("Checking for anti-bot verification page...")
        started = 0.0
        try:
            import time

            started = time.time()
        except Exception:
            started = 0.0

        notified = False
        while not stop_event.is_set() and self._is_security_check(page):
            if not notified:
                self.logger.info(
                    "Security verification detected. Complete the check in the opened browser window."
                )
                notified = True
            try:
                page.wait_for_timeout(1000)
            except Exception:
                return

            if started:
                try:
                    import time

                    if time.time() - started > max(30, timeout_sec):
                        self.logger.warning(
                            "Security verification is still active after %ss. Keeping browser open for manual completion.",
                            timeout_sec,
                        )
                        return
                except Exception:
                    pass

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
            "just a moment",
            "cf-challenge",
            "challenge-platform",
        ]
        target = f"{title}\n{body}\n{current_url}"
        return any(marker in target for marker in markers)

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
            self.session.playwright.stop()
        except Exception:
            pass
        self.session = None
