"""Focused public-release checks for cancellation and exported links."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
import search_papers


class PublicSafetyTests(unittest.TestCase):
    def test_stop_before_worker_starts_never_runs_task(self) -> None:
        controller = app.Controller()
        controller.job = {"id": "queued-test", "status": "queued"}
        invoked: list[str] = []
        controller.stop()
        controller._run("queued-test", lambda job_id: invoked.append(job_id))
        self.assertEqual(invoked, [])
        self.assertEqual(controller.job["status"], "stopped")

    def test_markdown_links_reject_non_web_schemes_and_quote_punctuation(self) -> None:
        paper = search_papers.PaperCandidate(
            id="link-test", source="OpenAlex", title="Metadata link test",
            url="javascript:alert(1)",
            pdf_url="https://example.org/a(b) c.pdf",
        )
        report = "\n".join(search_papers.render_candidate(1, paper))
        self.assertNotIn("javascript:", report)
        self.assertNotIn("[landing page]", report)
        self.assertIn("[PDF](<https://example.org/a(b)%20c.pdf>)", report)

    def test_html_links_reject_non_web_and_malformed_destinations(self) -> None:
        self.assertEqual(search_papers.html_link_button("paper", "javascript:alert(1)", ""), "")
        self.assertEqual(search_papers.html_link_button("paper", "https://user:pass@example.org/", ""), "")
        self.assertEqual(search_papers.html_link_button("paper", "https://[bad", ""), "")
        self.assertIn('href="https://example.org/paper"', search_papers.html_link_button("paper", "https://example.org/paper", ""))


if __name__ == "__main__":
    unittest.main()
