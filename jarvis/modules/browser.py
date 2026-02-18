from __future__ import annotations

from typing import Dict, Any

from playwright.sync_api import sync_playwright


class BrowserModule:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.headless = config["runtime"]["browser_headless"]

    def execute(self, intent: str, params: Dict[str, Any]) -> str:
        if intent not in {"research_query", "browser_search"}:
            raise ValueError(f"Unsupported browser intent: {intent}")

        query = params["query"]
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto("https://duckduckgo.com")
            page.fill("input[name='q']", query)
            page.keyboard.press("Enter")
            page.wait_for_selector("article h2 a", timeout=15000)
            links = page.locator("article h2 a").all_text_contents()[:5]
            browser.close()

        bullets = "; ".join(links) if links else "No results found"
        return f"Research summary for '{query}': {bullets}"
