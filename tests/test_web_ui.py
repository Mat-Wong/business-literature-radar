"""Optional browser smoke test (requires Playwright and installed Chrome)."""

from __future__ import annotations

import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

import app
from search_papers import LLMManager, PaperCandidate, render_html, rule_query_plan


CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class BackendConfigTests(unittest.TestCase):
    def test_advanced_cli_is_explicit_and_cannot_be_selected_as_api(self) -> None:
        controller = app.Controller.__new__(app.Controller)
        controller.lock = threading.RLock()
        controller.settings = {"provider": "openai", "api_key": "", "llm_backend": "rules"}
        with patch("app_settings.save_settings"):
            with self.assertRaises(ValueError):
                controller.save_config({"llm_backend": "api", "provider": "opencode"})
            result = controller.save_config({"llm_backend": "advanced", "provider": "opencode", "api_models": "auto"})
        self.assertEqual(result["llm_backend"], "advanced")
        self.assertIn("opencode", controller._provider_args())


@unittest.skipUnless(CHROME.exists() and sync_playwright is not None, "Chrome or optional Playwright not installed")
class WebUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_responsive_bilingual_plan_workflow(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
            try:
                for width in (320, 375, 414, 768, 1440):
                    context = browser.new_context(viewport={"width": width, "height": 900})
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    self.assertEqual(page.goto(self.base + "/").status, 200)
                    page.locator("#discipline-options input").first.wait_for()
                    self.assertLessEqual(
                        page.evaluate("document.documentElement.scrollWidth"), width + 1,
                        f"horizontal overflow at {width}px",
                    )
                    if width in (375, 1440):
                        shot = app.OUTPUT_DIR / f"qa-{width}.png"
                        shot.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(shot), full_page=True)
                    page.locator("#language-button").click()
                    self.assertIn("Research question", page.locator('label[for="query-input"]').inner_text())
                    page.locator("#query-input").fill("digital platform governance and innovation")
                    page.locator("#plan-button").click()
                    page.locator("#plan-panel").wait_for(state="visible", timeout=10000)
                    self.assertIn("platform governance", page.locator("#plan-english").input_value())
                    self.assertNotIn("IPO", page.locator("#plan-english").input_value())
                    page.locator("#settings-button").click()
                    page.locator('input[name="llm-backend"][value="codex"]').check()
                    self.assertTrue(page.locator("#api-fields").is_hidden())
                    self.assertIn("Codex CLI", page.locator("#backend-note").inner_text())
                    page.locator('input[name="llm-backend"][value="api"]').check()
                    self.assertTrue(page.locator("#api-fields").is_visible())
                    self.assertIn("https://api.openai.com", page.locator("#api-endpoint-input").input_value())
                    page.locator('input[name="llm-backend"][value="advanced"]').check()
                    self.assertTrue(page.locator("#api-fields").is_visible())
                    self.assertTrue(page.locator("#api-key-field").is_hidden())
                    self.assertTrue(page.locator("#api-endpoint-field").is_hidden())
                    self.assertEqual(page.locator("#provider-select option").count(), 2)
                    self.assertIn("OpenCode", page.locator("#provider-select").inner_text())
                    page.locator("#settings-cancel").click()
                    self.assertFalse(errors, errors)
                    context.close()
            finally:
                browser.close()

    def test_report_language_switch_and_layout(self) -> None:
        paper = PaperCandidate(
            id="sample", source="OpenAlex", title="Platform Governance and Innovation",
            title_zh="平台治理与创新", year=2024, venue="Information Systems Research",
            abstract="This paper examines platform governance and innovation.",
            abstract_zh="本文研究平台治理与创新。", doi="10.1234/sample", score=86,
        )
        markup = render_html(
            "platform governance", rule_query_plan("platform governance", ["is"]),
            [paper], [], LLMManager([], budget_calls=0, timeout=1), 2020, 2026,
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
            try:
                for width in (320, 375, 414, 768, 1440):
                    context = browser.new_context(viewport={"width": width, "height": 900})
                    page = context.new_page()
                    page.set_content(markup)
                    self.assertTrue(page.locator('h1 [data-lang="zh"]').is_visible())
                    page.locator("#language-toggle").click()
                    self.assertTrue(page.locator('h1 [data-lang="en"]').is_visible())
                    self.assertFalse(page.locator('h1 [data-lang="zh"]').is_visible())
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width + 1)
                    if width == 1440:
                        shot = app.OUTPUT_DIR / "qa-report.png"
                        shot.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(shot), full_page=True)
                    context.close()
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
