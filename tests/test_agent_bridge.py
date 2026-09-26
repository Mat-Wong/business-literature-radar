"""Behavioral checks for native-agent translation coverage and report rendering."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_bridge
import search_papers


class AgentBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.report_path = Path(self.temp.name) / "round_two.json"
        self.report_path.write_text(
            json.dumps(
                {
                    "query": "How do digital platforms affect firms?",
                    "years": [2020, 2026],
                    "plan": {"summary": "Digital platforms and firms", "expanded_queries": ["digital platforms firms"]},
                    "llm_events": [],
                    "issues": [],
                    "results": [
                        {
                            "title": "Platform Governance and Innovation",
                            "abstract": "We study governance choices in online platforms.",
                            "source": "OpenAlex",
                            "authors": "A. Author; B. Author",
                            "year": 2023,
                            "doi": "10.1234/example",
                            "url": "https://example.org/one",
                            "score": 80,
                        },
                        {
                            "title": "Research Note Without Abstract",
                            "abstract": "",
                            "source": "Crossref",
                            "authors": "C. Author",
                            "year": 2022,
                            "score": 60,
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def write_translations(self, second_abstract: str = "") -> None:
        batch_dir = agent_bridge.batch_dir_for(self.report_path)
        if not list(batch_dir.glob("batch_*.input.json")):
            agent_bridge.prepare(self.report_path, batch_size=2)
        prepared = {
            1: ("平台治理与创新", "我们研究在线平台中的治理选择。"),
            2: ("无摘要研究札记", second_abstract),
        }
        for input_path in batch_dir.glob("batch_*.input.json"):
            source = json.loads(input_path.read_text(encoding="utf-8"))
            translations = [
                {
                    "index": paper["index"],
                    "source_title": paper["source_title"],
                    "title_zh": prepared[paper["index"]][0],
                    "abstract_zh": prepared[paper["index"]][1],
                }
                for paper in source["papers"]
            ]
            output_path = input_path.with_name(input_path.name.replace(".input.json", ".translated.json"))
            output_path.write_text(
                json.dumps({"translations": translations}, ensure_ascii=False),
                encoding="utf-8",
            )

    def test_prepare_and_apply_preserve_source_and_render_all_formats(self) -> None:
        prepared = agent_bridge.prepare(self.report_path, batch_size=1)
        self.assertEqual(prepared["paper_count"], 2)
        self.assertEqual(len(prepared["input_files"]), 2)
        first_batch = json.loads(Path(prepared["input_files"][0]).read_text(encoding="utf-8"))
        self.assertEqual(first_batch["papers"][0]["source_abstract"], "We study governance choices in online platforms.")
        self.write_translations()
        result = agent_bridge.apply(self.report_path, "codex")
        derived = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
        self.assertEqual(derived["results"][0]["title_zh"], "平台治理与创新")
        self.assertEqual(derived["results"][0]["abstract"], "We study governance choices in online platforms.")
        self.assertEqual(derived["results"][1]["abstract_zh"], "")
        self.assertEqual(derived["agent_enrichment"]["translated_abstracts"], 1)
        self.assertIn("平台治理与创新", Path(result["files"]["html"]).read_text(encoding="utf-8"))
        self.assertIn("我们研究在线平台中的治理选择", Path(result["files"]["md"]).read_text(encoding="utf-8"))
        self.assertTrue(Path(result["files"]["csv"]).exists())
        original = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertNotIn("title_zh", original["results"][0])

    def test_missing_translation_rejected_before_output(self) -> None:
        self.write_translations()
        path = agent_bridge.batch_dir_for(self.report_path) / "batch_001.translated.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["translations"].pop()
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(agent_bridge.BridgeError, "Translated indices"):
            agent_bridge.apply(self.report_path, "claude")
        self.assertFalse(self.report_path.with_name("round_two-agent.html").exists())

    def test_cannot_invent_abstract_for_missing_source(self) -> None:
        self.write_translations(second_abstract="这是一段原文不存在的摘要")
        with self.assertRaisesRegex(agent_bridge.BridgeError, "no original abstract"):
            agent_bridge.apply(self.report_path, "codex")

    def test_source_title_mismatch_rejected(self) -> None:
        self.write_translations()
        path = agent_bridge.batch_dir_for(self.report_path) / "batch_001.translated.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["translations"][0]["source_title"] = "Different paper"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(agent_bridge.BridgeError, "source_title"):
            agent_bridge.apply(self.report_path, "codex")

    def test_stale_batch_rejected_when_source_abstract_changes(self) -> None:
        self.write_translations()
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        report["results"][0]["abstract"] = "A corrected source abstract."
        self.report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(agent_bridge.BridgeError, "changed since translation batches"):
            agent_bridge.apply(self.report_path, "claude")

    def test_existing_agent_report_not_overwritten(self) -> None:
        self.write_translations()
        prior = self.report_path.with_name("round_two-agent.html")
        prior.write_text("keep this", encoding="utf-8")
        with self.assertRaisesRegex(agent_bridge.BridgeError, "no files were overwritten"):
            agent_bridge.apply(self.report_path, "codex")
        self.assertEqual(prior.read_text(encoding="utf-8"), "keep this")

    def test_agent_csv_escapes_formula_metadata_but_json_keeps_original(self) -> None:
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        report["results"][0]["title"] = "=WEBSERVICE(\"https://example.org\")"
        self.report_path.write_text(json.dumps(report), encoding="utf-8")
        self.write_translations()
        result = agent_bridge.apply(self.report_path, "codex")
        with Path(result["files"]["csv"]).open(newline="", encoding="utf-8-sig") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["title"], "'" + report["results"][0]["title"])
        saved = json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["results"][0]["title"], report["results"][0]["title"])

    def test_search_csv_escapes_formula_metadata_but_json_keeps_original(self) -> None:
        title = "=WEBSERVICE(\"https://example.org\")"
        paper = search_papers.PaperCandidate(
            id="unsafe-metadata", source="OpenAlex", title=title,
            abstract="  +SUM(1,2)", authors=["@author"],
        )
        *_, csv_path, json_path = search_papers.write_outputs(
            "safe CSV test", {"summary": "test"}, [paper], [],
            search_papers.LLMManager([], budget_calls=0, timeout=0),
            Path(self.temp.name), 2020, 2026,
        )
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["title"], "'" + title)
        self.assertEqual(row["abstract"], "'  +SUM(1,2)")
        self.assertEqual(row["authors"], "'@author")
        saved = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["results"][0]["title"], title)


if __name__ == "__main__":
    unittest.main()
