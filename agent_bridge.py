"""Prepare native-agent translation batches and render a fully translated report.

This module never calls an LLM or reads an API key. Codex/Claude Code translate the
prepared source text in their own sessions, then this module checks coverage and
renders a separate, auditable report beside the original search output.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

from search_papers import LLMManager, SourceIssue, csv_safe_row, render_html, render_markdown
from search_v2 import candidate_from_row


class BridgeError(ValueError):
    """Invalid source report, translation batch, or output destination."""


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BridgeError(f"Cannot read {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BridgeError(f"{label} must be a JSON object: {path}")
    return value


def report_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("results")
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise BridgeError("Report must contain a nonempty results array of paper objects")
    if any(not str(row.get("title", "")).strip() for row in rows):
        raise BridgeError("Every result needs an original title")
    return rows


def batch_dir_for(report_path: Path) -> Path:
    return report_path.parent / f"{report_path.stem}-translation-batches"


def prepare(report_path: Path, batch_size: int) -> dict[str, Any]:
    if not 1 <= batch_size <= 20:
        raise BridgeError("--batch-size must be between 1 and 20")
    report = read_object(report_path, "report")
    rows = report_rows(report)
    batch_dir = batch_dir_for(report_path)
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_paths = [
        batch_dir / f"batch_{number:03d}.input.json"
        for number in range(1, (len(rows) + batch_size - 1) // batch_size + 1)
    ]
    existing = [str(path) for path in batch_paths if path.exists()]
    if existing:
        raise BridgeError("Input batches already exist; no files were overwritten: " + ", ".join(existing))
    paths: list[str] = []
    for start in range(0, len(rows), batch_size):
        number = start // batch_size + 1
        path = batch_dir / f"batch_{number:03d}.input.json"
        papers = [
            {
                "index": index + 1,
                "source_title": str(rows[index]["title"]),
                "source_abstract": str(rows[index].get("abstract") or ""),
            }
            for index in range(start, min(start + batch_size, len(rows)))
        ]
        path.write_text(
            json.dumps({"papers": papers}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        paths.append(str(path))
    return {"batch_dir": str(batch_dir), "paper_count": len(rows), "input_files": paths}


def load_translations(batch_dir: Path, rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    files = sorted(batch_dir.glob("batch_*.translated.json"))
    if not files:
        raise BridgeError(f"No batch_*.translated.json files in {batch_dir}")
    translations: dict[int, dict[str, Any]] = {}
    for path in files:
        input_path = path.with_name(path.name.replace(".translated.json", ".input.json"))
        source_batch = read_object(input_path, "matching input batch")
        source_papers = source_batch.get("papers")
        if not isinstance(source_papers, list):
            raise BridgeError(f"papers must be an array in {input_path}")
        for paper in source_papers:
            if not isinstance(paper, dict) or not isinstance(paper.get("index"), int):
                raise BridgeError(f"Invalid source paper in {input_path}")
            index = paper["index"]
            if not 1 <= index <= len(rows):
                raise BridgeError(f"Source batch has an unexpected paper index {index}")
            row = rows[index - 1]
            if (
                paper.get("source_title") != str(row.get("title") or "")
                or paper.get("source_abstract") != str(row.get("abstract") or "")
            ):
                raise BridgeError(f"Paper {index} changed since translation batches were prepared")
        data = read_object(path, "translated batch")
        items = data.get("translations")
        if not isinstance(items, list):
            raise BridgeError(f"translations must be an array in {path}")
        source_indices = {paper["index"] for paper in source_papers}
        translated_indices = {item.get("index") for item in items if isinstance(item, dict)}
        if translated_indices != source_indices:
            raise BridgeError(f"Translated indices do not match source batch {input_path}")
        for item in items:
            if not isinstance(item, dict):
                raise BridgeError(f"Every translation must be an object in {path}")
            index = item.get("index")
            if isinstance(index, bool) or not isinstance(index, int) or index < 1:
                raise BridgeError(f"Every translation needs a positive integer index in {path}")
            if index in translations:
                raise BridgeError(f"Duplicate translation for paper {index}")
            translations[index] = item
    return translations


def apply(report_path: Path, agent_name: str) -> dict[str, Any]:
    report = read_object(report_path, "report")
    rows = report_rows(report)
    batch_dir = batch_dir_for(report_path)
    translations = load_translations(batch_dir, rows)
    expected = set(range(1, len(rows) + 1))
    actual = set(translations)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise BridgeError(f"Translation coverage incomplete: missing={missing}, unexpected={extra}")

    enriched_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        translated = translations[index]
        source_title = str(row["title"])
        if translated.get("source_title") != source_title:
            raise BridgeError(f"Paper {index} source_title does not match the report")
        title_zh = str(translated.get("title_zh") or "").strip()
        abstract_zh = str(translated.get("abstract_zh") or "").strip()
        if not title_zh:
            raise BridgeError(f"Paper {index} has no Chinese title")
        has_abstract = bool(str(row.get("abstract") or "").strip())
        if has_abstract and not abstract_zh:
            raise BridgeError(f"Paper {index} has an original abstract but no Chinese abstract")
        if not has_abstract and abstract_zh:
            raise BridgeError(f"Paper {index} has no original abstract; Chinese abstract must be empty")
        updated = dict(row)
        updated["title_zh"] = title_zh
        updated["abstract_zh"] = abstract_zh
        enriched_rows.append(updated)

    output_base = report_path.with_name(report_path.stem + "-agent")
    targets = {
        "json": output_base.with_suffix(".json"),
        "html": output_base.with_suffix(".html"),
        "md": output_base.with_suffix(".md"),
        "csv": output_base.with_suffix(".csv"),
    }
    existing = [str(path) for path in targets.values() if path.exists()]
    if existing:
        raise BridgeError("Agent report already exists; no files were overwritten: " + ", ".join(existing))

    enriched = dict(report)
    enriched["results"] = enriched_rows
    enriched["agent_enrichment"] = {
        "provider": agent_name,
        "source_report": report_path.name,
        "translated_titles": len(rows),
        "translated_abstracts": sum(bool(str(row.get("abstract") or "").strip()) for row in rows),
        "missing_source_abstracts": sum(not bool(str(row.get("abstract") or "").strip()) for row in rows),
        "scope": "original titles and available metadata abstracts only",
    }
    years = report.get("years")
    if not isinstance(years, list) or len(years) != 2:
        raise BridgeError("Report years must contain [start_year, end_year]")
    try:
        start_year, end_year = int(years[0]), int(years[1])
    except (TypeError, ValueError) as exc:
        raise BridgeError("Report years must be integers") from exc
    query = str(report.get("query") or "")
    plan = report.get("plan") or {}
    if not isinstance(plan, dict):
        raise BridgeError("Report plan must be a JSON object")
    issue_rows = report.get("issues") or []
    if not isinstance(issue_rows, list):
        raise BridgeError("Report issues must be an array")
    issues = [
        SourceIssue(
            source=str(item.get("source") or ""),
            kind=str(item.get("kind") or ""),
            detail=str(item.get("detail") or ""),
        )
        for item in issue_rows
        if isinstance(item, dict)
    ]
    candidates = [candidate_from_row(row) for row in enriched_rows]
    llm = LLMManager([], budget_calls=0, timeout=0)
    events = report.get("llm_events") or []
    if isinstance(events, list):
        llm.events.extend(str(event) for event in events)
    llm.events.append(f"All available metadata titles and abstracts translated by {agent_name} native session.")
    enriched["llm_events"] = llm.events

    rendered = {
        "json": json.dumps(enriched, ensure_ascii=False, indent=2),
        "html": render_html(query, plan, candidates, issues, llm, start_year, end_year),
        "md": render_markdown(query, plan, candidates, issues, llm, start_year, end_year),
    }
    csv_text = io.StringIO(newline="")
    fieldnames = list(dict.fromkeys(key for row in enriched_rows for key in row))
    writer = csv.DictWriter(csv_text, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_safe_row(row) for row in enriched_rows)
    rendered["csv"] = csv_text.getvalue()
    for key, value in rendered.items():
        targets[key].write_text(value, encoding="utf-8-sig" if key == "csv" else "utf-8")
    return {"paper_count": len(rows), "files": {key: str(value) for key, value in targets.items()}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Native-agent translation bridge; no API key is used.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="Make per-paper source-text batches")
    prepare_parser.add_argument("--report-json", type=Path, required=True)
    prepare_parser.add_argument("--batch-size", type=int, default=6)
    apply_parser = subparsers.add_parser("apply", help="Validate full translation coverage and render report")
    apply_parser.add_argument("--report-json", type=Path, required=True)
    apply_parser.add_argument("--agent-name", choices=["codex", "claude"], required=True)
    args = parser.parse_args(argv)
    try:
        report_path = args.report_json.resolve(strict=True)
        result = prepare(report_path, args.batch_size) if args.command == "prepare" else apply(report_path, args.agent_name)
    except (BridgeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
