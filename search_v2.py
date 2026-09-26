#!/usr/bin/env python3
"""Two-round deep-search upgrade built on the existing search_papers engine."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any

from search_papers import (
    DEFAULT_OPENCODE_MODELS,
    LLMManager,
    PaperCandidate,
    SourceIssue,
    balanced_select_candidates,
    build_llm_manager,
    clean_text,
    dedupe_candidates,
    fetch_json,
    infer_permission,
    parse_jsonish,
    reconstruct_openalex_abstract,
    rerank_with_llm,
    sanitize_plan,
    score_candidates,
    search_sources,
    strip_doi,
    translate_abstracts_with_llm,
    truncate,
    write_outputs,
)


PROGRESS_PREFIX = "__PROGRESS__"
OUTPUT_DIR_PREFIX = "__OUTPUT_DIR__"
FEEDBACK_STATES = {"relevant", "irrelevant", "uncertain"}
TOKEN_STOPWORDS = {
    "about", "after", "among", "analysis", "based", "between", "business",
    "effects", "empirical", "from", "have", "into", "large", "models",
    "paper", "performance", "research", "study", "their", "these", "using",
    "with", "worker", "workers",
}


def report_progress(percent: int, stage: str, detail: str = "") -> None:
    payload = {"percent": percent, "stage": stage, "detail": detail}
    print(PROGRESS_PREFIX + json.dumps(payload, ensure_ascii=True), flush=True)


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def candidate_from_row(row: dict[str, Any]) -> PaperCandidate:
    authors = row.get("authors") or []
    if isinstance(authors, str):
        authors = [part.strip() for part in authors.split(";") if part.strip()]

    def optional_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if str(value).lower() in {"true", "1"}:
            return True
        if str(value).lower() in {"false", "0"}:
            return False
        return None

    def optional_int(value: Any) -> int | None:
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    return PaperCandidate(
        id=f"round1:{row.get('doi') or row.get('title', '')}",
        source=str(row.get("source", "Round 1")),
        title=str(row.get("title", "")),
        title_zh=str(row.get("title_zh", "")),
        authors=list(authors),
        year=optional_int(row.get("year")),
        venue=str(row.get("venue", "")),
        abstract=str(row.get("abstract", "")),
        abstract_zh=str(row.get("abstract_zh", "")),
        doi=str(row.get("doi", "")),
        url=str(row.get("url", "")),
        pdf_url=str(row.get("pdf_url", "")),
        citation_count=optional_int(row.get("citation_count")),
        open_access=optional_bool(row.get("open_access")),
        needs_permission=optional_bool(row.get("needs_permission")),
        score=float(row.get("score") or 0),
        reason=str(row.get("reason", "")),
        research_value=str(row.get("research_value", "")),
        risks=str(row.get("risks", "")),
        source_payload={"round": 1},
    )


def feedback_key(value: dict[str, Any] | PaperCandidate) -> str:
    keys = feedback_keys(value)
    return keys[0] if keys else "title:"


def feedback_keys(value: dict[str, Any] | PaperCandidate) -> list[str]:
    if isinstance(value, PaperCandidate):
        doi, title = value.doi, value.title
    else:
        doi, title = str(value.get("doi", "")), str(value.get("title", ""))
    keys = []
    if doi:
        keys.append("doi:" + strip_doi(doi).lower())
    normalized_title = re.sub(r"[^a-z0-9]+", "", title.lower())
    if normalized_title:
        keys.append("title:" + normalized_title)
    return keys


def normalized_feedback(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in payload.get("feedback", []):
        if not isinstance(item, dict):
            continue
        state = str(item.get("state", "uncertain")).lower()
        if state not in FEEDBACK_STATES:
            state = "uncertain"
        result.append(
            {
                "title": clean_text(str(item.get("title", ""))),
                "doi": strip_doi(str(item.get("doi", ""))),
                "state": state,
            }
        )
    return result


def feedback_examples(
    feedback: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    states = {
        key: item["state"]
        for item in feedback
        for key in feedback_keys(item)
    }
    relevant, irrelevant = [], []
    for row in rows:
        state = next(
            (states[key] for key in feedback_keys(row) if key in states),
            "uncertain",
        )
        target = relevant if state == "relevant" else irrelevant if state == "irrelevant" else None
        if target is not None:
            target.append(
                {
                    "title": row.get("title", ""),
                    "venue": row.get("venue", ""),
                    "abstract": truncate(str(row.get("abstract", "")), 700),
                }
            )
    return relevant, irrelevant


def title_tokens(items: list[dict[str, Any]]) -> list[str]:
    counter: Counter[str] = Counter()
    for item in items:
        tokens = {
            token.lower()
            for token in re.findall(r"[A-Za-z][A-Za-z-]{2,}", str(item.get("title", "")))
            if token.lower() not in TOKEN_STOPWORDS
        }
        counter.update(tokens)
    return [token for token, _count in counter.most_common(12)]


def fallback_refined_plan(
    original_query: str,
    base_plan: dict[str, Any],
    relevant: list[dict[str, Any]],
    irrelevant: list[dict[str, Any]],
) -> dict[str, Any]:
    plan = dict(base_plan)
    positive = title_tokens(relevant)
    negative = [token for token in title_tokens(irrelevant) if token not in positive]
    base_query = str(plan.get("english_query", "")).strip()
    refinements = []
    if positive:
        refinements.extend(
            [
                " ".join(positive[:6]),
                f"{base_query} {' '.join(positive[:4])}".strip(),
                f"{' '.join(positive[:5])} field experiment causal evidence",
            ]
        )
    plan["expanded_queries"] = list(dict.fromkeys(refinements + list(plan.get("expanded_queries", []))))[:12]
    plan["must_have_terms"] = list(dict.fromkeys(positive[:8] + list(plan.get("must_have_terms", []))))[:12]
    plan["exclude_terms"] = list(dict.fromkeys(list(plan.get("exclude_terms", [])) + negative[:8]))[:12]
    plan["summary"] = str(plan.get("summary", "")) + " Refined from explicit relevance feedback."
    return sanitize_plan(plan, original_query)


def refine_plan_with_feedback(
    original_query: str,
    base_plan: dict[str, Any],
    feedback: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    llm: LLMManager,
) -> tuple[dict[str, Any], dict[str, int]]:
    relevant, irrelevant = feedback_examples(feedback, rows)
    counts = {
        "relevant": len(relevant),
        "irrelevant": len(irrelevant),
        "uncertain": max(0, len(feedback) - len(relevant) - len(irrelevant)),
    }
    fallback = fallback_refined_plan(original_query, base_plan, relevant, irrelevant)
    prompt = f"""
You refine a business-school literature search after explicit user feedback.

Original research need:
{original_query}

Current plan:
{json.dumps(base_plan, ensure_ascii=False, indent=2)}

Relevant examples:
{json.dumps(relevant[:10], ensure_ascii=False, indent=2)}

Irrelevant examples:
{json.dumps(irrelevant[:10], ensure_ascii=False, indent=2)}

Return ONLY a JSON object containing these fields:
english_query, expanded_queries, must_have_terms, nice_to_have_terms,
exclude_terms, arxiv_queries, summary.

Generate 4 to 8 genuinely new queries. Generalize from the relevant examples,
do not merely concatenate titles. Use irrelevant examples to sharpen exclusions.
Keep all search values in English ASCII.
""".strip()
    text, _backend = llm.complete(prompt, "feedback query refinement")
    if not text:
        return fallback, counts
    parsed = parse_jsonish(text)
    if not isinstance(parsed, dict):
        llm.events.append("feedback query refinement: invalid JSON; used deterministic fallback")
        return fallback, counts
    merged = dict(fallback)
    for key in [
        "english_query", "expanded_queries", "must_have_terms", "nice_to_have_terms",
        "exclude_terms", "arxiv_queries", "summary",
    ]:
        if parsed.get(key):
            merged[key] = parsed[key]
    return sanitize_plan(merged, original_query), counts


def openalex_candidate(item: dict[str, Any], relation: str, seed_title: str) -> PaperCandidate | None:
    title = clean_text(str(item.get("title", "")))
    if not title:
        return None
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    oa = item.get("open_access") or {}
    pdf_url = (
        location.get("pdf_url")
        or oa.get("oa_url")
        or ((item.get("best_oa_location") or {}).get("pdf_url"))
        or ""
    )
    authors = [
        clean_text(str((authorship.get("author") or {}).get("display_name", "")))
        for authorship in item.get("authorships", [])
        if (authorship.get("author") or {}).get("display_name")
    ]
    return PaperCandidate(
        id=f"openalex-{relation}:{item.get('id', title)}",
        source=f"OpenAlex {relation}",
        title=title,
        authors=authors,
        year=item.get("publication_year"),
        venue=clean_text(str(source.get("display_name", ""))),
        abstract=reconstruct_openalex_abstract(item.get("abstract_inverted_index")),
        doi=strip_doi(item.get("doi", "")),
        url=location.get("landing_page_url") or item.get("id", ""),
        pdf_url=pdf_url,
        citation_count=item.get("cited_by_count"),
        open_access=bool(oa.get("is_oa")) if oa else None,
        needs_permission=infer_permission(pdf_url, bool(oa.get("is_oa"))),
        source_payload={"round": 2, "relation": relation, "seed_title": seed_title},
    )


def fetch_openalex_work(seed: dict[str, Any], issues: list[SourceIssue]) -> dict[str, Any] | None:
    doi = strip_doi(str(seed.get("doi", "")))
    if doi:
        params = {"filter": f"doi:https://doi.org/{doi}", "per-page": "1"}
    else:
        params = {"search": str(seed.get("title", "")), "per-page": "1"}
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    data = fetch_json(url, "OpenAlex citation lookup", issues)
    results = (data or {}).get("results", [])
    return results[0] if results else None


def expand_citations(
    seeds: list[dict[str, Any]],
    start_year: int,
    end_year: int,
    per_seed: int,
    issues: list[SourceIssue],
) -> list[PaperCandidate]:
    candidates: list[PaperCandidate] = []
    for seed in seeds[:5]:
        work = fetch_openalex_work(seed, issues)
        if not work:
            continue
        work_id = str(work.get("id", "")).rsplit("/", 1)[-1]
        seed_title = str(seed.get("title", ""))
        # OpenAlex does not guarantee that referenced_works is relevance-sorted.
        # Fetch a wider pool first, then keep the strongest in-range records.
        reference_ids = [
            str(value).rsplit("/", 1)[-1]
            for value in work.get("referenced_works", [])[:50]
        ]
        requests: list[tuple[str, dict[str, str]]] = []
        if reference_ids:
            requests.append(
                (
                    "reference",
                    {
                        "filter": "openalex_id:" + "|".join(reference_ids),
                        "per-page": str(min(50, len(reference_ids))),
                        "sort": "cited_by_count:desc",
                    },
                )
            )
        if work_id:
            requests.append(
                (
                    "cited-by",
                    {
                        "filter": (
                            f"cites:{work_id},from_publication_date:{start_year}-01-01,"
                            f"to_publication_date:{end_year}-12-31"
                        ),
                        "per-page": str(per_seed),
                        "sort": "cited_by_count:desc",
                    },
                )
            )
        for relation, params in requests:
            url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
            data = fetch_json(url, f"OpenAlex {relation}", issues)
            added = 0
            for item in (data or {}).get("results", []):
                year = item.get("publication_year")
                if year:
                    year_value = int(year)
                    if relation == "reference":
                        # Backward citation chasing deliberately reaches older
                        # foundations; forward citations still obey the range.
                        if year_value > end_year:
                            continue
                    elif not start_year <= year_value <= end_year:
                        continue
                candidate = openalex_candidate(item, relation, seed_title)
                if candidate:
                    if relation == "reference" and candidate.year and candidate.year < start_year:
                        candidate.source = "OpenAlex reference · 年份放宽"
                        candidate.risks = (
                            f"Backward citation expansion: published before the requested {start_year} start year."
                        )
                    candidates.append(candidate)
                    added += 1
                    if added >= per_seed:
                        break
    return candidates


def candidate_identity(candidate: PaperCandidate) -> str:
    return feedback_key(candidate)


def apply_feedback_scores(
    candidates: list[PaperCandidate],
    feedback: list[dict[str, Any]],
) -> None:
    states = {
        key: item["state"]
        for item in feedback
        for key in feedback_keys(item)
    }
    for candidate in candidates:
        state = next(
            (states[key] for key in feedback_keys(candidate) if key in states),
            None,
        )
        if state == "relevant":
            candidate.score = min(100.0, candidate.score + 25.0)
            candidate.reason = "explicitly marked relevant; " + candidate.reason
        elif state == "irrelevant":
            candidate.score = max(0.0, candidate.score - 60.0)
            candidate.reason = "explicitly marked irrelevant; " + candidate.reason


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Search V2 feedback refinement and citation expansion.")
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--feedback-json", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sources", default="openalex,crossref,semantic_scholar")
    parser.add_argument("--citation-per-seed", type=int, default=5)
    parser.add_argument("--api-provider", default="rules")
    parser.add_argument("--api-endpoint", default="")
    parser.add_argument("--api-models", default="")
    parser.add_argument("--llm-backend", default="rules")
    parser.add_argument("--llm-budget-calls", type=int, default=4)
    parser.add_argument("--llm-timeout", type=int, default=90)
    parser.add_argument("--llm-max-candidates", type=int, default=25)
    parser.add_argument("--opencode-models", default=",".join(DEFAULT_OPENCODE_MODELS))
    parser.add_argument("--no-opencode-fallback", action="store_true")
    parser.add_argument("--translate-abstracts", action="store_true")
    parser.add_argument("--translation-batch-size", type=int, default=5)
    parser.add_argument("--translation-retry-rounds", type=int, default=6)
    parser.add_argument("--translation-retry-delay", type=float, default=2.0)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--progress", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report_path = Path(args.report_json).resolve()
    feedback_path = Path(args.feedback_json).resolve()
    try:
        report = load_json_object(report_path, "round-one report")
        feedback_payload = load_json_object(feedback_path, "feedback")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rows = [row for row in report.get("results", []) if isinstance(row, dict)]
    if not rows:
        print("ERROR: round-one report has no results", file=sys.stderr)
        return 2
    feedback = normalized_feedback(feedback_payload)
    if not any(item["state"] in {"relevant", "irrelevant"} for item in feedback):
        print("ERROR: mark at least one paper relevant or irrelevant before deep search", file=sys.stderr)
        return 2

    query = str(report.get("query", ""))
    years = report.get("years") or [2018, dt.datetime.now().year]
    start_year, end_year = int(years[0]), int(years[1])
    base_plan = dict(report.get("plan") or {})
    llm = build_llm_manager(args)
    report_progress(5, "整理反馈", "根据相关、不相关和不确定标记更新检索意图")
    refined_plan, feedback_counts = refine_plan_with_feedback(
        query, base_plan, feedback, rows, llm
    )

    source_names = [value.strip() for value in args.sources.split(",") if value.strip()]
    limit = args.limit or len(rows)
    report_progress(18, "第二轮检索", "执行反馈驱动的新查询")
    second_raw, issues = search_sources(
        plan=refined_plan,
        start_year=start_year,
        end_year=end_year,
        limit=max(limit, 20),
        source_names=source_names,
    )

    relevant_seeds = [item for item in feedback if item["state"] == "relevant"]
    report_progress(58, "引用扩展", f"扩展 {min(5, len(relevant_seeds))} 篇相关种子论文")
    citation_candidates = expand_citations(
        relevant_seeds,
        start_year,
        end_year,
        max(1, min(args.citation_per_seed, 10)),
        issues,
    )

    round_one = [candidate_from_row(row) for row in rows]
    before_keys = {candidate_identity(candidate) for candidate in round_one}
    second_unique = {
        candidate_identity(candidate)
        for candidate in dedupe_candidates(second_raw)
        if candidate_identity(candidate) not in before_keys
    }
    citation_unique = {
        candidate_identity(candidate)
        for candidate in dedupe_candidates(citation_candidates)
        if candidate_identity(candidate) not in before_keys
    }

    report_progress(72, "合并与重排", "合并两轮结果、引用网络和显式反馈")
    candidates = dedupe_candidates(round_one + second_raw + citation_candidates)
    score_candidates(candidates, refined_plan)
    rerank_with_llm(query, refined_plan, candidates, llm, args.llm_max_candidates)
    apply_feedback_scores(candidates, feedback)
    candidates = balanced_select_candidates(
        sorted(candidates, key=lambda value: value.score, reverse=True),
        limit=limit,
        group_min=0,
    )

    translation_coverage: tuple[int, int] | None = None
    if args.translate_abstracts:
        report_progress(85, "翻译全部结果", "为两轮深搜最终展示的每篇文献补齐中文译文")

        def translation_progress(done: int, total: int, round_number: int) -> None:
            report_progress(
                85 + round(6 * done / max(total, 1)),
                "翻译全部结果",
                f"第 {round_number} 轮：已完成 {done}/{total} 篇",
            )

        translation_coverage = translate_abstracts_with_llm(
            candidates=candidates,
            llm=llm,
            max_items=len(candidates),
            char_limit=1800,
            batch_size=args.translation_batch_size,
            retry_rounds=args.translation_retry_rounds,
            retry_delay=args.translation_retry_delay,
            progress_callback=translation_progress,
        )

    new_in_final = sum(
        1
        for candidate in candidates
        if candidate_identity(candidate) not in before_keys
    )
    high_relevance_new = sum(
        1
        for candidate in candidates
        if candidate_identity(candidate) not in before_keys and candidate.score >= 60
    )
    audit = {
        "version": 1,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source_report": str(report_path),
        "feedback_file": str(feedback_path),
        "feedback_counts": feedback_counts,
        "rounds": [
            {"round": 1, "final_results": len(round_one)},
            {
                "round": 2,
                "raw_candidates": len(second_raw),
                "new_unique_candidates": len(second_unique),
                "queries": refined_plan.get("expanded_queries", []),
            },
            {
                "round": "citation-expansion",
                "seed_count": min(5, len(relevant_seeds)),
                "raw_candidates": len(citation_candidates),
                "new_unique_candidates": len(citation_unique),
            },
        ],
        "discovery_curve": [len(round_one), len(second_unique), len(citation_unique)],
        "citation_year_policy": (
            "Backward references may predate the requested start year; "
            "forward citations obey the requested range."
        ),
        "new_in_final": new_in_final,
        "high_relevance_new_in_final": high_relevance_new,
        "stopping_reason": "Search V2 MVP completed the configured two rounds and one citation layer.",
        "issues": [dataclasses.asdict(issue) for issue in issues],
        "llm_events": llm.events,
    }
    refined_plan["search_v2_audit"] = {
        "feedback_counts": feedback_counts,
        "discovery_curve": audit["discovery_curve"],
        "new_in_final": new_in_final,
        "high_relevance_new_in_final": high_relevance_new,
        "citation_year_policy": audit["citation_year_policy"],
        "stopping_reason": audit["stopping_reason"],
    }

    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        base_dir = report_path.parent / "deep-search"
        output_dir = base_dir
        suffix = 2
        while output_dir.exists():
            output_dir = report_path.parent / f"deep-search-{suffix}"
            suffix += 1
    print(OUTPUT_DIR_PREFIX + json.dumps({"path": str(output_dir)}, ensure_ascii=True), flush=True)
    report_progress(92, "生成深搜报告", "保存最终结果和两轮审计记录")
    html_path, md_path, csv_path, json_path = write_outputs(
        query=query,
        plan=refined_plan,
        candidates=candidates,
        issues=issues,
        llm=llm,
        output_dir=output_dir,
        start_year=start_year,
        end_year=end_year,
    )
    audit_path = output_dir / "search_v2_session.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"HTML:     {html_path}")
    print(f"Markdown: {md_path}")
    print(f"CSV:      {csv_path}")
    print(f"JSON:     {json_path}")
    print(f"Audit:    {audit_path}")
    if translation_coverage and translation_coverage[0] < translation_coverage[1]:
        translated, total = translation_coverage
        print(f"ERROR: translation incomplete after model rotation: {translated}/{total}", file=sys.stderr)
        report_progress(100, "翻译未完成", f"已翻译 {translated}/{total} 篇；报告已保留")
        return 3
    report_progress(
        100,
        "深搜完成",
        f"最终新增 {new_in_final} 篇，其中高相关 {high_relevance_new} 篇",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
