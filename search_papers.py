#!/usr/bin/env python3
"""
Literature search helper for business/CS/FinNLP papers.

The tool accepts a natural-language research need, expands it into search
queries, collects metadata from open indexes, deduplicates candidates, and
generates Markdown/CSV/JSON reading lists.

LLM usage is optional. Public builds use the researcher's own API or an
explicitly selected local CLI; the default is deterministic rule mode.

No API key is written to disk by this script.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import ssl
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "output"
DEFAULT_OPENCODE_MODELS = [
    "auto",
]

USER_AGENT = (
    "BusinessLiteratureRadar/0.1 (public academic metadata client)"
)

BUSINESS_CONTEXT_TERMS = [
    "corporate",
    "company",
    "companies",
    "firm",
    "firms",
    "financial",
    "finance",
    "accounting",
    "stock",
    "market",
    "investor",
    "investors",
    "ipo",
    "earnings",
    "disclosure",
    "sec",
    "analyst",
    "analysts",
    "bankruptcy",
    "default",
    "risk management",
    "business",
]

DISCIPLINE_LABELS = {
    "is": "Information Systems / 信息系统",
    "qm": "Quantitative Methods & Analytics / 数量方法",
    "om": "Operations Management / 运营管理",
    "strategy": "Strategy / 战略",
    "finance": "Finance / 金融",
    "accounting": "Accounting / 会计",
    "management": "Management & OB / 管理与组织行为",
    "marketing": "Marketing / 市场营销",
    "economics": "Business Economics / 商业经济学",
    "stats": "Econometrics, Statistics & Data Science / 计量统计与数据科学",
    "behavioral": "Behavioral Science / 行为科学",
    "political_economy": "Political Economy & Public Policy / 政治经济与公共政策",
    "healthcare": "Health Care Management / 医疗管理",
    "ethics": "Ethics & Legal Studies / 商业伦理与法律",
}

BUSINESS_JOURNALS: dict[str, dict[str, Any]] = {
    "MIS Quarterly": {
        "aliases": ["MISQ", "MIS Quarterly", "Management Information Systems Quarterly"],
        "issns": ["0276-7783", "2162-9730"],
        "priority": 24,
        "disciplines": ["is"],
    },
    "Information Systems Research": {
        "aliases": ["ISR", "Information Systems Research"],
        "issns": ["1047-7047", "1526-5536"],
        "priority": 24,
        "disciplines": ["is"],
    },
    "Management Science": {
        "aliases": ["MS", "Management Science"],
        "issns": ["0025-1909", "1526-5501"],
        "priority": 24,
        "disciplines": ["is", "qm", "om", "strategy", "stats", "behavioral", "healthcare"],
    },
    "Operations Research": {
        "aliases": ["Operations Research"], "issns": ["0030-364X"],
        "priority": 23, "disciplines": ["qm", "om", "stats"],
    },
    "Manufacturing & Service Operations Management": {
        "aliases": ["M&SOM", "MSOM", "Manufacturing & Service Operations Management"],
        "issns": ["1523-4614"], "priority": 23, "disciplines": ["om"],
    },
    "Production and Operations Management": {
        "aliases": ["POM", "Production and Operations Management"],
        "issns": ["1059-1478"], "priority": 21, "disciplines": ["om"],
    },
    "Journal of Operations Management": {
        "aliases": ["Journal of Operations Management"],
        "issns": ["0272-6963"], "priority": 22, "disciplines": ["om"],
    },
    "Strategic Management Journal": {
        "aliases": ["SMJ", "Strategic Management Journal"],
        "issns": ["0143-2095"], "priority": 24, "disciplines": ["strategy"],
    },
    "Organization Science": {
        "aliases": ["Organization Science"], "issns": ["1047-7039"],
        "priority": 24, "disciplines": ["strategy", "management", "behavioral"],
    },
    "Academy of Management Journal": {
        "aliases": ["AMJ", "Academy of Management Journal"],
        "issns": ["0001-4273"], "priority": 24, "disciplines": ["strategy", "management"],
    },
    "Academy of Management Review": {
        "aliases": ["AMR", "Academy of Management Review"],
        "issns": ["0363-7425"], "priority": 24, "disciplines": ["strategy", "management"],
    },
    "Administrative Science Quarterly": {
        "aliases": ["ASQ", "Administrative Science Quarterly"],
        "issns": ["0001-8392"], "priority": 24, "disciplines": ["management", "behavioral"],
    },
    "Journal of Applied Psychology": {
        "aliases": ["JAP", "Journal of Applied Psychology"],
        "issns": ["0021-9010"], "priority": 22, "disciplines": ["management", "behavioral"],
    },
    "Organizational Behavior and Human Decision Processes": {
        "aliases": ["OBHDP", "Organizational Behavior and Human Decision Processes"],
        "issns": ["0749-5978"], "priority": 22, "disciplines": ["management", "behavioral"],
    },
    "Journal of Finance": {
        "aliases": ["JF", "Journal of Finance"], "issns": ["0022-1082"],
        "priority": 24, "disciplines": ["finance", "economics"],
    },
    "Journal of Financial Economics": {
        "aliases": ["JFE", "Journal of Financial Economics"],
        "issns": ["0304-405X"], "priority": 24, "disciplines": ["finance"],
    },
    "Review of Financial Studies": {
        "aliases": ["RFS", "Review of Financial Studies"],
        "issns": ["0893-9454"], "priority": 24, "disciplines": ["finance"],
    },
    "American Economic Review": {
        "aliases": ["AER", "American Economic Review"], "issns": ["0002-8282"],
        "priority": 24, "disciplines": ["economics"],
    },
    "Quarterly Journal of Economics": {
        "aliases": ["QJE", "Quarterly Journal of Economics"], "issns": ["0033-5533"],
        "priority": 24, "disciplines": ["economics"],
    },
    "Journal of Political Economy": {
        "aliases": ["JPE", "Journal of Political Economy"], "issns": ["0022-3808"],
        "priority": 24, "disciplines": ["economics", "political_economy"],
    },
    "Econometrica": {
        "aliases": ["Econometrica"], "issns": ["0012-9682"],
        "priority": 24, "disciplines": ["economics", "stats"],
    },
    "Review of Economic Studies": {
        "aliases": ["ReStud", "Review of Economic Studies"], "issns": ["0034-6527"],
        "priority": 24, "disciplines": ["economics"],
    },
    "RAND Journal of Economics": {
        "aliases": ["RAND Journal of Economics"], "issns": ["0741-6261"],
        "priority": 22, "disciplines": ["economics", "strategy"],
    },
    "Journal of the American Statistical Association": {
        "aliases": ["JASA", "Journal of the American Statistical Association"],
        "issns": ["0162-1459"], "priority": 23, "disciplines": ["stats"],
    },
    "Annals of Statistics": {
        "aliases": ["Annals of Statistics"], "issns": ["0090-5364"],
        "priority": 23, "disciplines": ["stats"],
    },
    "Biometrika": {
        "aliases": ["Biometrika"], "issns": ["0006-3444"],
        "priority": 23, "disciplines": ["stats"],
    },
    "Journal of Business & Economic Statistics": {
        "aliases": ["JBES", "Journal of Business & Economic Statistics"],
        "issns": ["0735-0015"], "priority": 22, "disciplines": ["stats", "economics"],
    },
    "Psychological Science": {
        "aliases": ["Psychological Science"], "issns": ["0956-7976"],
        "priority": 22, "disciplines": ["behavioral"],
    },
    "Journal of Personality and Social Psychology": {
        "aliases": ["JPSP", "Journal of Personality and Social Psychology"],
        "issns": ["0022-3514"], "priority": 22, "disciplines": ["behavioral"],
    },
    "American Political Science Review": {
        "aliases": ["APSR", "American Political Science Review"], "issns": ["0003-0554"],
        "priority": 23, "disciplines": ["political_economy"],
    },
    "American Journal of Political Science": {
        "aliases": ["AJPS", "American Journal of Political Science"], "issns": ["0092-5853"],
        "priority": 22, "disciplines": ["political_economy"],
    },
    "Journal of Politics": {
        "aliases": ["Journal of Politics"], "issns": ["0022-3816"],
        "priority": 22, "disciplines": ["political_economy"],
    },
    "Journal of Health Economics": {
        "aliases": ["Journal of Health Economics"], "issns": ["0167-6296"],
        "priority": 23, "disciplines": ["healthcare", "economics"],
    },
    "Health Affairs": {
        "aliases": ["Health Affairs"], "issns": ["0278-2715"],
        "priority": 22, "disciplines": ["healthcare"],
    },
    "Health Services Research": {
        "aliases": ["HSR", "Health Services Research"], "issns": ["0017-9124"],
        "priority": 21, "disciplines": ["healthcare"],
    },
    "Medical Care": {
        "aliases": ["Medical Care"], "issns": ["0025-7079"],
        "priority": 21, "disciplines": ["healthcare"],
    },
    "Business Ethics Quarterly": {
        "aliases": ["BEQ", "Business Ethics Quarterly"], "issns": ["1052-150X"],
        "priority": 22, "disciplines": ["ethics"],
    },
    "Journal of Business Ethics": {
        "aliases": ["Journal of Business Ethics"], "issns": ["0167-4544"],
        "priority": 20, "disciplines": ["ethics"],
    },
    "The Accounting Review": {
        "aliases": ["TAR", "The Accounting Review", "Accounting Review"],
        "issns": ["0001-4826"], "priority": 24, "disciplines": ["accounting"],
    },
    "Journal of Accounting Research": {
        "aliases": ["JAR", "Journal of Accounting Research"],
        "issns": ["0021-8456"], "priority": 24, "disciplines": ["accounting"],
    },
    "Journal of Accounting and Economics": {
        "aliases": ["JAE", "Journal of Accounting and Economics"],
        "issns": ["0165-4101"], "priority": 24, "disciplines": ["accounting"],
    },
    "Review of Accounting Studies": {
        "aliases": ["RAST", "Review of Accounting Studies"],
        "issns": ["1380-6653"], "priority": 22, "disciplines": ["accounting"],
    },
    "Contemporary Accounting Research": {
        "aliases": ["CAR", "Contemporary Accounting Research"],
        "issns": ["0823-9150"], "priority": 22, "disciplines": ["accounting"],
    },
    "Marketing Science": {
        "aliases": ["Marketing Science"],
        "issns": ["0732-2399", "1526-548X"],
        "priority": 22,
        "disciplines": ["marketing", "qm"],
    },
    "Journal of Marketing Research": {
        "aliases": ["JMR", "Journal of Marketing Research"],
        "issns": ["0022-2437", "1547-7193"],
        "priority": 22,
        "disciplines": ["marketing"],
    },
    "Journal of Marketing": {
        "aliases": ["JM", "Journal of Marketing"], "issns": ["0022-2429"],
        "priority": 23, "disciplines": ["marketing"],
    },
    "Journal of Consumer Research": {
        "aliases": ["JCR", "Journal of Consumer Research"],
        "issns": ["0093-5301"], "priority": 23, "disciplines": ["marketing"],
    },
}

CS_VENUES = {
    "ICML": ["ICML", "International Conference on Machine Learning"],
    "NeurIPS": ["NeurIPS", "NIPS", "Neural Information Processing Systems"],
    "AISTATS": ["AISTATS", "Artificial Intelligence and Statistics"],
    "ICLR": ["ICLR", "International Conference on Learning Representations"],
    "AAAI": ["AAAI"],
    "KDD": ["KDD", "Knowledge Discovery and Data Mining"],
    "WINE": ["WINE", "Web and Internet Economics"],
    "IEEE": [
        "TKDE",
        "TNNLS",
        "ICDM",
        "ICDE",
        "IEEE BigData",
        "IEEE International Conference on Data Mining",
        "IEEE International Conference on Data Engineering",
        "IEEE Transactions on Knowledge and Data Engineering",
        "IEEE Transactions on Neural Networks and Learning Systems",
    ],
}

FINNLP_HINTS = [
    "finbert",
    "financial nlp",
    "finnlp",
    "earnings call",
    "10-k",
    "10 k",
    "annual report",
    "ipo prospectus",
    "sec filing",
    "stock return",
    "stock price",
    "crash risk",
    "financial distress",
    "bankruptcy",
    "fraud detection",
    "credit risk",
    "analyst forecast",
]

SOURCE_GROUPS = [
    ("all", "全部 / All"),
    ("utd", "商科目标顶刊 / Business Journals"),
    ("ssrn", "SSRN"),
    ("arxiv", "arXiv"),
    ("cs", "CS/ML 来源 / CS/ML Sources"),
    ("finnlp", "FinNLP / Finance"),
    ("other", "其他 / Other"),
]


def journals_for_disciplines(disciplines: Iterable[str]) -> dict[str, dict[str, Any]]:
    selected = {value.strip().lower() for value in disciplines if value.strip()}
    if not selected:
        selected = {"is", "qm"}
    return {
        journal: meta
        for journal, meta in BUSINESS_JOURNALS.items()
        if selected.intersection(meta.get("disciplines", []))
    }


def target_business_journals(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    names = set(plan.get("target_journals") or [])
    if names:
        return {name: BUSINESS_JOURNALS[name] for name in names if name in BUSINESS_JOURNALS}
    return journals_for_disciplines(plan.get("selected_disciplines") or ["is", "qm"])

@dataclasses.dataclass
class SourceIssue:
    source: str
    kind: str
    detail: str


@dataclasses.dataclass
class PaperCandidate:
    id: str
    source: str
    title: str
    title_zh: str = ""
    authors: list[str] = dataclasses.field(default_factory=list)
    year: int | None = None
    venue: str = ""
    abstract: str = ""
    abstract_zh: str = ""
    doi: str = ""
    url: str = ""
    pdf_url: str = ""
    citation_count: int | None = None
    open_access: bool | None = None
    needs_permission: bool | None = None
    score: float = 0.0
    reason: str = ""
    research_value: str = ""
    risks: str = ""
    source_payload: dict[str, Any] = dataclasses.field(default_factory=dict)

    def normalized_title(self) -> str:
        return normalize_title(self.title)

    def to_row(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "title": self.title,
            "title_zh": self.title_zh,
            "authors": "; ".join(self.authors),
            "year": self.year or "",
            "venue": self.venue,
            "source": self.source,
            "source_group": source_group_key(self),
            "doi": self.doi,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "citation_count": self.citation_count if self.citation_count is not None else "",
            "open_access": self.open_access if self.open_access is not None else "",
            "needs_permission": (
                self.needs_permission if self.needs_permission is not None else ""
            ),
            "reason": self.reason,
            "research_value": self.research_value,
            "risks": self.risks,
            "abstract": self.abstract,
            "abstract_zh": self.abstract_zh,
        }


class RecoverableLLMError(Exception):
    pass


class FatalLLMError(Exception):
    pass


class LLMBackend:
    name = "base"

    def complete(self, prompt: str, timeout: int) -> str:
        raise NotImplementedError


class HTTPModelBackend(LLMBackend):
    """Direct HTTPS backend with ordered model fallback and no SDK dependency."""

    def __init__(self, name: str, endpoint: str, key: str, models: list[str]):
        self.name = name
        self.endpoint = endpoint
        self.key = key
        self.models = models
        self.last_model = ""

    def request_for_model(self, model: str, prompt: str) -> urllib.request.Request:
        raise NotImplementedError

    def extract_text(self, data: dict[str, Any]) -> str:
        raise NotImplementedError

    def complete(self, prompt: str, timeout: int) -> str:
        if not self.key:
            raise RecoverableLLMError(f"{self.name}: API key is not configured")
        if not self.endpoint:
            raise RecoverableLLMError(f"{self.name}: endpoint is not configured")
        if not self.models:
            raise RecoverableLLMError(f"{self.name}: model is not configured")
        errors = []
        for model in self.models:
            try:
                request = self.request_for_model(model, prompt)
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                text = self.extract_text(data)
                if text:
                    self.last_model = model
                    return text
                errors.append(f"{model}: empty response")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace").lower()
                reason = (
                    "quota or rate limit" if exc.code in {402, 429} or "insufficient_quota" in detail
                    else "authentication failed" if exc.code in {401, 403}
                    else "service error"
                )
                errors.append(f"{model}: HTTP {exc.code} ({reason})")
            except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
                errors.append(f"{model}: {exc}")
        raise RecoverableLLMError(f"{self.name} models unavailable: {' | '.join(errors)}")


class OpenAIResponsesBackend(HTTPModelBackend):
    def __init__(self, endpoint: str, key: str, models: list[str]):
        super().__init__("openai", endpoint, key, models)

    def request_for_model(self, model: str, prompt: str) -> urllib.request.Request:
        body = json.dumps(
            {"model": model, "input": prompt, "max_output_tokens": 12000},
            ensure_ascii=False,
        ).encode("utf-8")
        return urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )

    def extract_text(self, data: dict[str, Any]) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str):
            return direct.strip()
        texts = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    texts.append(str(content.get("text", "")))
        return "\n".join(texts).strip()


class AnthropicMessagesBackend(HTTPModelBackend):
    def __init__(self, endpoint: str, key: str, models: list[str]):
        super().__init__("anthropic", endpoint, key, models)

    def request_for_model(self, model: str, prompt: str) -> urllib.request.Request:
        body = json.dumps(
            {
                "model": model,
                "max_tokens": 12000,
                "messages": [{"role": "user", "content": prompt}],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "x-api-key": self.key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )

    def extract_text(self, data: dict[str, Any]) -> str:
        return "\n".join(
            str(item.get("text", ""))
            for item in data.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()


class OpenAICompatibleBackend(HTTPModelBackend):
    def __init__(self, endpoint: str, key: str, models: list[str]):
        super().__init__("openai-compatible", endpoint, key, models)

    def request_for_model(self, model: str, prompt: str) -> urllib.request.Request:
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 12000,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )

    def extract_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            return ""
        content = (choices[0].get("message") or {}).get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict)
            ).strip()
        return ""


class OpenCodeBackend(LLMBackend):
    name = "opencode"

    def __init__(self, models: list[str]):
        self.models = models
        self.executable = shutil.which("opencode")
        self.last_model = ""

    def complete(self, prompt: str, timeout: int) -> str:
        if not self.executable:
            raise RecoverableLLMError("opencode command not found")
        last_error = "opencode failed"
        for model in self.models or ["auto"]:
            try:
                command = [self.executable, "run"]
                if model and model != "auto":
                    command.extend(["-m", model])
                command.extend(["--", prompt])
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
            except subprocess.TimeoutExpired as exc:
                last_error = f"opencode timeout for {model}"
                continue
            except OSError as exc:
                raise RecoverableLLMError(f"opencode failed: {exc}") from exc
            raw = strip_ansi((result.stdout or "") + "\n" + (result.stderr or ""))
            if result.returncode == 0 and raw.strip():
                self.last_model = model or "default"
                return raw.strip()
            last_error = f"opencode {model} exited {result.returncode}: {raw[-300:]}"
        raise RecoverableLLMError(last_error)


class AgentCLIBackend(LLMBackend):
    """Use an already authenticated local agent CLI for one-shot text generation."""

    COMMANDS = {
        "codex_cli": ("codex", "codex-cli"),
        "gemini_cli": ("gemini", "gemini-cli"),
    }

    def __init__(self, provider: str, models: list[str]):
        executable_name, backend_name = self.COMMANDS[provider]
        self.provider = provider
        self.name = backend_name
        self.models = models or ["auto"]
        self.executable = shutil.which(executable_name)
        self.last_model = ""

    def _command(self, model: str, prompt: str) -> list[str]:
        assert self.executable
        if self.provider == "codex_cli":
            command = [
                self.executable,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
            ]
            if model != "auto":
                command.extend(["--model", model])
            command.append(prompt)
            return command
        command = [self.executable, "-p", prompt, "--output-format", "json"]
        if model != "auto":
            command.extend(["--model", model])
        return command

    def complete(self, prompt: str, timeout: int) -> str:
        if not self.executable:
            executable_name = self.COMMANDS[self.provider][0]
            raise RecoverableLLMError(f"{executable_name} command not found")
        errors = []
        for model in self.models:
            try:
                result = subprocess.run(
                    self._command(model, prompt),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
            except subprocess.TimeoutExpired:
                errors.append(f"{model}: timeout")
                continue
            except OSError as exc:
                raise RecoverableLLMError(f"{self.name} failed: {exc}") from exc
            stdout = strip_ansi(result.stdout or "").strip()
            stderr = strip_ansi(result.stderr or "").strip()
            if result.returncode == 0 and stdout:
                if self.provider == "gemini_cli":
                    try:
                        payload = json.loads(stdout)
                        stdout = str(payload.get("response") or "").strip()
                    except json.JSONDecodeError:
                        pass
                if stdout:
                    self.last_model = model
                    return stdout
            errors.append(f"{model}: exit {result.returncode} {(stderr or stdout)[-300:]}")
        raise RecoverableLLMError(f"{self.name} unavailable: {' | '.join(errors)}")


class LLMManager:
    def __init__(self, backends: list[LLMBackend], budget_calls: int, timeout: int):
        self.backends = backends
        self.budget_calls = budget_calls
        self.timeout = timeout
        self.calls_used = 0
        self.disabled: set[str] = set()
        self.events: list[str] = []

    def complete(
        self,
        prompt: str,
        purpose: str,
        required: bool = False,
    ) -> tuple[str | None, str | None]:
        if self.calls_used >= self.budget_calls and not required:
            self.events.append(f"LLM skipped for {purpose}: call budget exhausted")
            return None, None
        for backend in self.backends:
            if backend.name in self.disabled:
                continue
            try:
                text = backend.complete(prompt, timeout=self.timeout)
            except RecoverableLLMError as exc:
                self.disabled.add(backend.name)
                self.events.append(f"{backend.name} disabled for this run: {exc}")
                continue
            self.calls_used += 1
            backend_label = backend.name
            if isinstance(backend, (OpenCodeBackend, AgentCLIBackend, HTTPModelBackend)) and backend.last_model:
                backend_label = f"{backend.name}:{backend.last_model}"
            self.events.append(f"{purpose}: used {backend_label}")
            return text, backend_label
        self.events.append(f"LLM skipped for {purpose}: no backend available")
        return None, None

    def reset_disabled_for_retry(self, purpose: str) -> None:
        """Allow transiently unavailable APIs/models to participate in a later round."""
        if self.disabled:
            names = ", ".join(sorted(self.disabled))
            self.events.append(f"{purpose}: retrying disabled backends/models: {names}")
            self.disabled.clear()


class SearchSource:
    name = "base"

    def search(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        raise NotImplementedError


class OpenAlexSource(SearchSource):
    name = "OpenAlex"

    def search(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        candidates: list[PaperCandidate] = []
        for query in plan_queries(plan, max_queries=5):
            params = {
                "search": query,
                "filter": (
                    f"from_publication_date:{start_year}-01-01,"
                    f"to_publication_date:{end_year}-12-31"
                ),
                "per-page": str(min(max(limit * 3, 25), 50)),
                "sort": "relevance_score:desc",
            }
            email = os.environ.get("OPENALEX_EMAIL")
            if email:
                params["mailto"] = email
            url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
            data = fetch_json(url, self.name, issues)
            if not data:
                if (
                    issues
                    and issues[-1].source == self.name
                    and issues[-1].kind == "permission_or_rate_limit"
                    and "429" in issues[-1].detail
                ):
                    break
                continue
            for item in data.get("results", []):
                title = clean_text(item.get("title", ""))
                if not title:
                    continue
                source = ((item.get("primary_location") or {}).get("source") or {})
                location = item.get("primary_location") or {}
                oa = item.get("open_access") or {}
                authors = [
                    clean_text(a.get("author", {}).get("display_name", ""))
                    for a in item.get("authorships", [])
                    if a.get("author", {}).get("display_name")
                ]
                doi = strip_doi(item.get("doi", ""))
                pdf_url = (
                    location.get("pdf_url")
                    or oa.get("oa_url")
                    or ((item.get("best_oa_location") or {}).get("pdf_url"))
                    or ""
                )
                landing = location.get("landing_page_url") or item.get("id", "")
                candidates.append(
                    PaperCandidate(
                        id=f"openalex:{item.get('id', title)}",
                        source=self.name,
                        title=title,
                        authors=authors,
                        year=item.get("publication_year"),
                        venue=clean_text(source.get("display_name", "")),
                        abstract=reconstruct_openalex_abstract(
                            item.get("abstract_inverted_index")
                        ),
                        doi=doi,
                        url=landing,
                        pdf_url=pdf_url,
                        citation_count=item.get("cited_by_count"),
                        open_access=bool(oa.get("is_oa")) if oa else None,
                        needs_permission=infer_permission(pdf_url, bool(oa.get("is_oa"))),
                        source_payload={"query": query},
                    )
                )
        candidates.extend(
            self._search_cs_venue_queries(plan, start_year, end_year, issues)
        )
        return candidates

    def _search_cs_venue_queries(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        candidates: list[PaperCandidate] = []
        cs_base_queries = plan_queries(plan, max_queries=2)
        if not cs_base_queries:
            return candidates
        for venue_keyword in [
            "ICML",
            "NeurIPS",
            "ICLR",
            "KDD",
            "AAAI",
            "AISTATS",
            "WINE",
            "ICDM",
            "ICDE",
            "IEEE BigData",
            "TKDE",
            "TNNLS",
        ]:
            params = {
                "search": f"{cs_base_queries[0]} {venue_keyword}",
                "filter": (
                    f"from_publication_date:{start_year}-01-01,"
                    f"to_publication_date:{end_year}-12-31"
                ),
                "per-page": "12",
                "sort": "relevance_score:desc",
            }
            email = os.environ.get("OPENALEX_EMAIL")
            if email:
                params["mailto"] = email
            url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
            data = fetch_json(url, self.name, issues)
            if not data:
                continue
            for item in data.get("results", []):
                title = clean_text(item.get("title", ""))
                if not title:
                    continue
                source = ((item.get("primary_location") or {}).get("source") or {})
                location = item.get("primary_location") or {}
                oa = item.get("open_access") or {}
                authors = [
                    clean_text(a.get("author", {}).get("display_name", ""))
                    for a in item.get("authorships", [])
                    if a.get("author", {}).get("display_name")
                ]
                doi = strip_doi(item.get("doi", ""))
                pdf_url = (
                    location.get("pdf_url")
                    or oa.get("oa_url")
                    or ((item.get("best_oa_location") or {}).get("pdf_url"))
                    or ""
                )
                landing = location.get("landing_page_url") or item.get("id", "")
                candidates.append(
                    PaperCandidate(
                        id=f"openalex-cs:{item.get('id', title)}",
                        source=self.name,
                        title=title,
                        authors=authors,
                        year=item.get("publication_year"),
                        venue=clean_text(source.get("display_name", "")),
                        abstract=reconstruct_openalex_abstract(
                            item.get("abstract_inverted_index")
                        ),
                        doi=doi,
                        url=landing,
                        pdf_url=pdf_url,
                        citation_count=item.get("cited_by_count"),
                        open_access=bool(oa.get("is_oa")) if oa else None,
                        needs_permission=infer_permission(pdf_url, bool(oa.get("is_oa"))),
                        source_payload={
                            "query": cs_base_queries[0],
                            "venue_keyword": venue_keyword,
                        },
                    )
                )
            time.sleep(0.15)
        return candidates


class CrossrefSource(SearchSource):
    name = "Crossref"

    def search(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        candidates: list[PaperCandidate] = []
        queries = plan_queries(plan, max_queries=4)
        filters = [
            f"from-pub-date:{start_year}-01-01",
            f"until-pub-date:{end_year}-12-31",
            "type:journal-article",
        ]

        for query in queries:
            params = {
                "query.bibliographic": query,
                "filter": ",".join(filters),
                "rows": str(min(max(limit, 10), 40)),
                "sort": "relevance",
                "order": "desc",
            }
            candidates.extend(self._search_url(params, issues, query))

        # Target-journal passes keep the business sources visible even when the
        # global query is dominated by arXiv/CS terms.
        journal_queries = dedupe_keep_order(
            queries[:2]
            + [
                "artificial intelligence",
                "machine learning",
            ]
        )
        for journal, meta in target_business_journals(plan).items():
            issn = meta["issns"][0]
            for query in journal_queries:
                params = {
                    "query.bibliographic": query,
                    "filter": ",".join(filters + [f"issn:{issn}"]),
                    "rows": "6",
                    "sort": "relevance",
                    "order": "desc",
                }
                candidates.extend(self._search_url(params, issues, query, journal))
                time.sleep(0.12)
        return candidates

    def _search_url(
        self,
        params: dict[str, str],
        issues: list[SourceIssue],
        query: str,
        journal_hint: str = "",
    ) -> list[PaperCandidate]:
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        data = fetch_json(url, self.name, issues)
        if not data:
            return []
        candidates: list[PaperCandidate] = []
        for item in data.get("message", {}).get("items", []):
            title = strip_html(first_text(item.get("title")))
            if not title:
                continue
            authors = []
            for author in item.get("author", [])[:12]:
                name = " ".join(
                    p for p in [author.get("given", ""), author.get("family", "")] if p
                ).strip()
                if name:
                    authors.append(name)
            year = crossref_year(item)
            abstract = strip_html(item.get("abstract", ""))
            link_pdf = ""
            for link in item.get("link", []):
                content_type = (link.get("content-type") or "").lower()
                if "pdf" in content_type:
                    link_pdf = link.get("URL", "")
                    break
            doi = strip_doi(item.get("DOI", ""))
            venue = first_text(item.get("container-title")) or journal_hint
            candidates.append(
                PaperCandidate(
                    id=f"crossref:{doi or title}",
                    source=self.name,
                    title=clean_text(title),
                    authors=authors,
                    year=year,
                    venue=clean_text(venue),
                    abstract=clean_text(abstract),
                    doi=doi,
                    url=item.get("URL", ""),
                    pdf_url=link_pdf,
                    citation_count=item.get("is-referenced-by-count"),
                    open_access=True if link_pdf else None,
                    needs_permission=infer_permission(link_pdf, bool(link_pdf)),
                    source_payload={"query": query, "journal_hint": journal_hint},
                )
            )
        return candidates


class ArxivSource(SearchSource):
    name = "arXiv"

    def search(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        candidates: list[PaperCandidate] = []
        queries = arxiv_queries(plan)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for query in queries[:5]:
            params = {
                "search_query": query,
                "start": "0",
                "max_results": str(min(max(limit, 10), 50)),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
            text = fetch_text(url, self.name, issues)
            if not text:
                continue
            try:
                root = ET.fromstring(text)
            except ET.ParseError as exc:
                issues.append(SourceIssue(self.name, "parse_error", str(exc)))
                continue
            for entry in root.findall("atom:entry", ns):
                title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))
                if not title:
                    continue
                published = entry.findtext("atom:published", default="", namespaces=ns)
                year = safe_int(published[:4])
                if year and not (start_year <= year <= end_year):
                    continue
                authors = [
                    clean_text(a.findtext("atom:name", default="", namespaces=ns))
                    for a in entry.findall("atom:author", ns)
                ]
                entry_url = entry.findtext("atom:id", default="", namespaces=ns)
                pdf_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                        pdf_url = link.attrib.get("href", "")
                        break
                categories = [
                    c.attrib.get("term", "")
                    for c in entry.findall("atom:category", ns)
                    if c.attrib.get("term")
                ]
                candidates.append(
                    PaperCandidate(
                        id=f"arxiv:{entry_url}",
                        source=self.name,
                        title=title,
                        authors=authors,
                        year=year,
                        venue="arXiv:" + ",".join(categories[:4]) if categories else "arXiv",
                        abstract=clean_text(
                            entry.findtext("atom:summary", default="", namespaces=ns)
                        ),
                        url=entry_url,
                        pdf_url=pdf_url,
                        open_access=True,
                        needs_permission=False,
                        source_payload={"query": query},
                    )
                )
            time.sleep(0.35)
        return candidates


class SemanticScholarSource(SearchSource):
    name = "Semantic Scholar"

    def search(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        candidates: list[PaperCandidate] = []
        fields = ",".join(
            [
                "title",
                "abstract",
                "authors",
                "year",
                "venue",
                "url",
                "externalIds",
                "citationCount",
                "openAccessPdf",
                "publicationVenue",
            ]
        )
        for query in plan_queries(plan, max_queries=4):
            params = {
                "query": query,
                "limit": str(min(max(limit, 10), 50)),
                "fields": fields,
                "year": f"{start_year}-{end_year}",
            }
            url = (
                "https://api.semanticscholar.org/graph/v1/paper/search?"
                + urllib.parse.urlencode(params)
            )
            data = fetch_json(url, self.name, issues)
            if not data:
                continue
            for item in data.get("data", []):
                title = clean_text(item.get("title", ""))
                if not title:
                    continue
                external = item.get("externalIds") or {}
                oa_pdf = item.get("openAccessPdf") or {}
                venue = item.get("venue") or ""
                pub_venue = item.get("publicationVenue") or {}
                if pub_venue.get("name"):
                    venue = pub_venue["name"]
                candidates.append(
                    PaperCandidate(
                        id=f"s2:{item.get('paperId', title)}",
                        source=self.name,
                        title=title,
                        authors=[
                            clean_text(a.get("name", ""))
                            for a in item.get("authors", [])
                            if a.get("name")
                        ],
                        year=item.get("year"),
                        venue=clean_text(venue),
                        abstract=clean_text(item.get("abstract", "") or ""),
                        doi=strip_doi(external.get("DOI", "")),
                        url=item.get("url", ""),
                        pdf_url=oa_pdf.get("url", "") if oa_pdf else "",
                        citation_count=item.get("citationCount"),
                        open_access=True if oa_pdf.get("url") else None,
                        needs_permission=infer_permission(
                            oa_pdf.get("url", "") if oa_pdf else "",
                            bool(oa_pdf.get("url") if oa_pdf else False),
                        ),
                        source_payload={"query": query},
                    )
                )
            time.sleep(0.25)
        return candidates


class DBLPSource(SearchSource):
    name = "DBLP"

    def search(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        candidates: list[PaperCandidate] = []
        for query in plan_queries(plan, max_queries=4):
            params = {
                "q": query,
                "format": "json",
                "h": str(min(max(limit, 10), 50)),
            }
            url = "https://dblp.org/search/publ/api?" + urllib.parse.urlencode(params)
            data = fetch_json(url, self.name, issues)
            if not data:
                continue
            hits = (
                data.get("result", {})
                .get("hits", {})
                .get("hit", [])
            )
            for hit in hits:
                info = hit.get("info", {})
                title = clean_text(strip_html(info.get("title", "")))
                if not title:
                    continue
                year = safe_int(info.get("year", ""))
                if year and not (start_year <= year <= end_year):
                    continue
                authors = dblp_authors(info.get("authors", {}))
                venue = clean_text(info.get("venue", ""))
                candidates.append(
                    PaperCandidate(
                        id=f"dblp:{info.get('key', title)}",
                        source=self.name,
                        title=title,
                        authors=authors,
                        year=year,
                        venue=venue,
                        doi=strip_doi(info.get("doi", "")),
                        url=info.get("url", ""),
                        open_access=None,
                        needs_permission=None,
                        source_payload={"query": query},
                    )
                )
            time.sleep(0.2)
        return candidates


class SSRNSource(SearchSource):
    name = "SSRN"

    def search(
        self,
        plan: dict[str, Any],
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        candidates: list[PaperCandidate] = []
        for query in plan_queries(plan, max_queries=3):
            candidates.extend(
                self._search_crossref_ssrn(query, start_year, end_year, limit, issues)
            )
            url = ssrn_search_url(query)
            text = fetch_text(url, self.name, issues, timeout=20)
            if not text:
                issues.append(
                    SourceIssue(
                        self.name,
                        "manual_search",
                        f"SSRN has no stable public API here; use {url}",
                    )
                )
                continue
            seen_ids: set[str] = set()
            for match in re.finditer(
                r'href="([^"]*papers\.cfm\?abstract_id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
                text,
                flags=re.I | re.S,
            ):
                abstract_id = match.group(2)
                if abstract_id in seen_ids:
                    continue
                seen_ids.add(abstract_id)
                title = clean_text(strip_html(match.group(3)))
                if not title or len(title) < 8:
                    continue
                paper_url = urllib.parse.urljoin("https://papers.ssrn.com/", match.group(1))
                candidates.append(
                    PaperCandidate(
                        id=f"ssrn:{abstract_id}",
                        source=self.name,
                        title=title,
                        venue="SSRN",
                        url=paper_url,
                        open_access=None,
                        needs_permission=None,
                        source_payload={"query": query, "search_url": url},
                    )
                )
                if len(candidates) >= limit:
                    break
            if not seen_ids:
                issues.append(SourceIssue(self.name, "manual_search", f"Use {url}"))
            time.sleep(0.3)
        return candidates

    def _search_crossref_ssrn(
        self,
        query: str,
        start_year: int,
        end_year: int,
        limit: int,
        issues: list[SourceIssue],
    ) -> list[PaperCandidate]:
        params = {
            "query.bibliographic": query,
            "filter": (
                f"from-posted-date:{start_year}-01-01,"
                f"until-posted-date:{end_year}-12-31,"
                "type:posted-content,prefix:10.2139"
            ),
            "rows": str(min(max(limit, 10), 30)),
            "sort": "relevance",
            "order": "desc",
        }
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
        data = fetch_json(url, "SSRN/Crossref", issues)
        if not data:
            return []
        candidates: list[PaperCandidate] = []
        for item in data.get("message", {}).get("items", []):
            title = strip_html(first_text(item.get("title")))
            doi = strip_doi(item.get("DOI", ""))
            if not title:
                continue
            authors = []
            for author in item.get("author", [])[:12]:
                name = " ".join(
                    p for p in [author.get("given", ""), author.get("family", "")] if p
                ).strip()
                if name:
                    authors.append(name)
            year = crossref_year(item)
            landing = item.get("URL", "")
            if doi.startswith("10.2139/ssrn.") and not landing:
                landing = f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={doi.rsplit('.', 1)[-1]}"
            candidates.append(
                PaperCandidate(
                    id=f"ssrn-crossref:{doi or title}",
                    source=self.name,
                    title=clean_text(strip_html(title)),
                    authors=authors,
                    year=year,
                    venue="SSRN",
                    abstract=strip_html(item.get("abstract", "")),
                    doi=doi,
                    url=landing,
                    open_access=None,
                    needs_permission=None,
                    source_payload={"query": query, "via": "Crossref posted-content"},
                )
            )
        return candidates


def build_llm_manager(args: argparse.Namespace) -> LLMManager:
    backends: list[LLMBackend] = []
    opencode_models = parse_model_list(args.opencode_models)

    provider = (args.api_provider or os.environ.get("LIT_SEARCH_PROVIDER") or "auto").lower()
    api_key = os.environ.get("LIT_SEARCH_API_KEY", "")
    endpoint = args.api_endpoint or os.environ.get("LIT_SEARCH_API_ENDPOINT", "")
    api_models = parse_model_list(
        args.api_models or os.environ.get("LIT_SEARCH_API_MODELS", "")
    )

    if provider == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
            api_key = os.environ["OPENAI_API_KEY"]
            endpoint = endpoint or "https://api.openai.com/v1/responses"
            api_models = api_models or ["gpt-6-luna", "gpt-6-sol"]
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
            api_key = os.environ["ANTHROPIC_API_KEY"]
            endpoint = endpoint or "https://api.anthropic.com/v1/messages"
            api_models = api_models or ["claude-haiku-4-5-20251001", "claude-sonnet-5"]
        elif args.llm_backend == "rules":
            provider = "rules"
        else:
            provider = "rules"

    if provider == "opencode" and api_models:
        opencode_models = api_models

    if provider == "openai":
        backends.append(
            OpenAIResponsesBackend(
                endpoint or "https://api.openai.com/v1/responses",
                api_key,
                api_models or ["gpt-6-luna", "gpt-6-sol"],
            )
        )
    elif provider == "anthropic":
        backends.append(
            AnthropicMessagesBackend(
                endpoint or "https://api.anthropic.com/v1/messages",
                api_key,
                api_models or ["claude-haiku-4-5-20251001", "claude-sonnet-5"],
            )
        )
    elif provider == "openai_compatible":
        backends.append(OpenAICompatibleBackend(endpoint, api_key, api_models))
    elif provider in AgentCLIBackend.COMMANDS:
        backends.append(AgentCLIBackend(provider, api_models or ["auto"]))
    if provider == "opencode":
        backends.append(OpenCodeBackend(opencode_models))
    if provider == "rules":
        backends = []
    return LLMManager(backends, budget_calls=args.llm_budget_calls, timeout=args.llm_timeout)


def llm_query_plan(
    query: str,
    llm: LLMManager,
    disciplines: list[str] | None = None,
) -> dict[str, Any]:
    disciplines = disciplines or ["is", "qm"]
    selected_journals = list(journals_for_disciplines(disciplines))
    discipline_text = ", ".join(
        DISCIPLINE_LABELS.get(value, value) for value in disciplines
    )
    journal_text = ", ".join(selected_journals)
    prompt = f"""
You are building a literature search plan for a PhD student in business/IS/CS.

Task:
- Convert the user's natural-language need into precise academic search terms.
- Prioritize recent arXiv/SSRN work for frontier ideas.
- Prioritize the selected business PhD disciplines: {discipline_text}.
- Keep these selected target journals visible: {journal_text}.
- Also include FinNLP/accounting/finance prediction terms when relevant.

Return ONLY valid JSON with this schema.
Use English ASCII text for search-related values. For folder_title, use concise
Chinese when the user writes Chinese; otherwise use concise English.
{{
  "folder_title": "2 to 6 short words naming the core research topic, no punctuation",
  "english_query": "one concise English query",
  "expanded_queries": ["6 to 10 search queries, no Boolean syntax needed"],
  "method_terms": ["AI/ML/NLP/multimodal method terms"],
  "data_terms": ["corporate data modalities and disclosures"],
  "target_terms": ["prediction targets/outcomes"],
  "must_have_terms": ["terms that indicate relevance"],
  "nice_to_have_terms": ["terms that improve relevance"],
  "exclude_terms": ["off-topic terms"],
  "arxiv_queries": ["3 to 5 arXiv API queries using all:term syntax"],
  "summary": "one sentence describing the intended paper set"
}}

User need:
{query}
""".strip()
    text, _backend = llm.complete(prompt, "query planning")
    if not text:
        return rule_query_plan(query, disciplines)
    parsed = parse_jsonish(text)
    if not isinstance(parsed, dict):
        llm.events.append("query planning: LLM output was not valid JSON; used rules")
        return rule_query_plan(query, disciplines)
    plan = rule_query_plan(query, disciplines)
    for key, value in parsed.items():
        if key in plan and value:
            plan[key] = value
    return sanitize_plan(plan, query)


def rule_query_plan(
    query: str,
    disciplines: list[str] | None = None,
) -> dict[str, Any]:
    """Conservative, topic-specific fallback; never insert unrelated AI/finance terms.

    This is intentionally not an LLM translation. Unrecognised Chinese concepts
    remain in the query so the editable preview makes the limitation visible.
    """
    disciplines = disciplines or ["is", "qm"]
    selected_journals = list(journals_for_disciplines(disciplines))
    concept_map = {
        "人工智能": "artificial intelligence", "生成式": "generative AI",
        "大模型": "large language models", "语言模型": "large language models",
        "机器学习": "machine learning", "深度学习": "deep learning",
        "数字平台": "digital platforms", "平台治理": "platform governance",
        "平台": "platforms", "治理": "governance", "创新": "innovation",
        "企业": "firm", "公司": "corporate", "组织": "organizations",
        "决策": "decision making", "绩效": "performance", "战略": "strategy",
        "供应链": "supply chains", "运营": "operations", "生产": "production",
        "营销": "marketing", "消费者": "consumers", "广告": "advertising",
        "金融": "financial", "股票": "stock", "股价": "stock price",
        "风险": "risk", "暴雷": "crash risk", "上市": "IPO",
        "预测": "prediction", "文本": "text", "视频": "video",
        "语音": "speech", "图片": "image",
        "会计": "accounting", "审计": "auditing", "披露": "disclosure",
        "信息系统": "information systems", "数字化": "digital transformation",
        "劳动": "labor", "就业": "employment", "经济": "economics",
        "因果": "causal inference", "实验": "experiments", "医疗": "healthcare",
        "可持续": "sustainability", "环境": "environmental",
    }
    concepts = [english for chinese, english in concept_map.items() if chinese in query]
    stop_words = {
        "about", "and", "are", "can", "effects", "for", "from", "how", "in",
        "into", "literature", "of", "on", "papers", "research", "search", "study",
        "the", "their", "this", "through", "using", "what", "with", "and",
    }
    english_terms = [
        token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", query)
        if token.lower() not in stop_words
    ]
    concepts = dedupe_keep_order(concepts + english_terms)[:10]
    discipline_terms = {
        "is": "information systems", "qm": "business analytics", "om": "operations management",
        "strategy": "business strategy", "finance": "finance", "accounting": "accounting",
        "management": "management", "marketing": "marketing", "economics": "economics",
        "stats": "statistics", "behavioral": "behavioral science",
        "political_economy": "political economy", "healthcare": "healthcare management",
        "ethics": "business ethics",
    }
    focus = " ".join(concepts[:5]).strip() or query.strip()
    context = [discipline_terms[key] for key in disciplines if key in discipline_terms]
    expanded_queries = dedupe_keep_order([
        focus,
        " ".join(concepts[:3] + context[:1]).strip(),
        " ".join(concepts[1:5] + context[:1]).strip(),
        " ".join(concepts[:2] + context[1:2]).strip(),
    ])
    # Keep at least one direct query even when a Chinese concept is unrecognised.
    if query.strip() not in expanded_queries and not concepts:
        expanded_queries.insert(0, query.strip())
    topical_terms = concepts[:8]
    arxiv_tokens = [t for t in english_terms if re.fullmatch(r"[A-Za-z0-9-]+", t)]
    if len(arxiv_tokens) < 2:
        arxiv_tokens = [t for t in re.findall(r"[A-Za-z]+", focus) if len(t) >= 3]
    arxiv_queries = [
        f"all:{arxiv_tokens[0]} AND all:{arxiv_tokens[1]}"
    ] if len(arxiv_tokens) >= 2 else []

    return sanitize_plan(
        {
            "original_query": query,
            "folder_title": rule_folder_title(query),
            "selected_disciplines": disciplines,
            "target_journals": selected_journals,
            "english_query": expanded_queries[0],
            "expanded_queries": expanded_queries,
            "method_terms": [],
            "data_terms": topical_terms[2:6],
            "target_terms": topical_terms[:4],
            "must_have_terms": topical_terms[:3],
            "nice_to_have_terms": topical_terms[3:8],
            "exclude_terms": [],
            "arxiv_queries": arxiv_queries,
            "summary": "Rule-based query expansion for: " + query.strip(),
        },
        query,
    )


def sanitize_plan(plan: dict[str, Any], original_query: str) -> dict[str, Any]:
    plan["original_query"] = original_query
    plan["folder_title"] = clean_text(str(plan.get("folder_title", "")))
    if not plan["folder_title"]:
        plan["folder_title"] = rule_folder_title(original_query)
    list_keys = [
        "expanded_queries",
        "method_terms",
        "data_terms",
        "target_terms",
        "must_have_terms",
        "nice_to_have_terms",
        "exclude_terms",
        "arxiv_queries",
        "selected_disciplines",
        "target_journals",
    ]
    for key in list_keys:
        value = plan.get(key, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            value = []
        cleaned_values = [clean_text(str(v)) for v in value if clean_text(str(v))]
        if key == "arxiv_queries":
            cleaned_values = [normalize_arxiv_query(v) for v in cleaned_values]
        plan[key] = cleaned_values[:12]
    if not plan.get("expanded_queries"):
        plan["expanded_queries"] = rule_query_plan(original_query)["expanded_queries"]
    if not plan.get("english_query"):
        plan["english_query"] = plan["expanded_queries"][0]
    if not plan.get("summary"):
        plan["summary"] = plan["english_query"]
    return plan


def load_search_plan(
    path: Path,
    original_query: str,
    disciplines: list[str],
) -> dict[str, Any]:
    """Load an edited plan while preserving the current query and safe defaults."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read search plan {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"search plan must be a JSON object: {path}")
    merged = rule_query_plan(original_query, disciplines)
    for key, value in loaded.items():
        if key in merged and value not in (None, "", []):
            merged[key] = value
    merged["selected_disciplines"] = disciplines
    merged["target_journals"] = list(journals_for_disciplines(disciplines))
    return sanitize_plan(merged, original_query)


def save_search_plan(plan: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)
    return path


def rerank_with_llm(
    query: str,
    plan: dict[str, Any],
    candidates: list[PaperCandidate],
    llm: LLMManager,
    max_candidates: int,
) -> None:
    if not candidates or max_candidates <= 0:
        return
    sample = sorted(candidates, key=lambda c: c.score, reverse=True)[:max_candidates]
    candidate_payload = []
    for idx, cand in enumerate(sample, start=1):
        candidate_payload.append(
            {
                "id": idx,
                "title": cand.title,
                "year": cand.year,
                "venue": cand.venue,
                "source": cand.source,
                "abstract": truncate(cand.abstract, 800),
                "rule_score": round(cand.score, 1),
            }
        )
    prompt = f"""
You are screening papers for a business/IS PhD student.

User research need:
{query}

Search-plan summary:
{plan.get("summary", "")}

Score each candidate from 0 to 100.
Use high scores only when the paper is substantively about AI/ML/LLM/NLP/
multimodal methods applied to corporate/financial/business signals and predicts
IPO, stock, crash/fraud/distress, firm performance, or related market outcomes.

Return ONLY valid JSON:
[
  {{
    "id": 1,
    "score": 0-100,
    "reason": "why it matches or not",
    "research_value": "how it may help form a PhD idea",
    "risks": "main caveat, such as old method, weak venue fit, missing abstract"
  }}
]

Candidates:
{json.dumps(candidate_payload, ensure_ascii=False, indent=2)}
""".strip()
    text, _backend = llm.complete(prompt, "candidate reranking")
    if not text:
        return
    parsed = parse_jsonish(text)
    if not isinstance(parsed, list):
        llm.events.append("candidate reranking: LLM output was not valid JSON")
        return
    by_idx = {idx: cand for idx, cand in enumerate(sample, start=1)}
    for row in parsed:
        if not isinstance(row, dict):
            continue
        idx = safe_int(row.get("id"))
        cand = by_idx.get(idx)
        if not cand:
            continue
        llm_score = clamp_float(row.get("score"), 0.0, 100.0)
        # Keep a little of the deterministic score to avoid one brittle LLM pass
        # completely burying strong venue/source evidence.
        cand.score = 0.78 * llm_score + 0.22 * cand.score
        cand.reason = clean_text(str(row.get("reason", ""))) or cand.reason
        cand.research_value = (
            clean_text(str(row.get("research_value", ""))) or cand.research_value
        )
        cand.risks = clean_text(str(row.get("risks", ""))) or cand.risks


def translate_abstracts_with_llm(
    candidates: list[PaperCandidate],
    llm: LLMManager,
    max_items: int,
    char_limit: int,
    batch_size: int,
    retry_rounds: int = 6,
    retry_delay: float = 2.0,
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> tuple[int, int]:
    if max_items <= 0:
        return 0, 0
    targets = candidates[:max_items]
    if not targets:
        llm.events.append("paper translation skipped: no final candidates")
        return 0, 0

    batch_size = max(1, batch_size)

    def complete(cand: PaperCandidate) -> bool:
        return bool(cand.title_zh and (not cand.abstract or cand.abstract_zh))

    def translate_pass(pending: list[PaperCandidate], pass_number: int) -> bool:
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            payload = [
                {
                    "id": index,
                    "title": cand.title,
                    "abstract": truncate(cand.abstract, char_limit),
                }
                for index, cand in enumerate(batch, start=1)
            ]
            prompt = f"""
You are translating academic paper metadata for a Chinese-speaking business/IS/CS PhD student.

Translate EVERY paper title and every available abstract into natural, precise academic Chinese.
Requirements:
- Return exactly one row for every input id, in the same order.
- Preserve technical terms where Chinese translation would be awkward, e.g. LLM, IPO, FinBERT, 10-K, arXiv, SSRN.
- Do not add claims that are not in the source text.
- Do not summarize the abstract too aggressively; preserve its method, data, task, and findings.
- If the input abstract is empty, return an empty abstract_zh but still translate title_zh.
- Return ONLY valid JSON with this schema:
{{
  "translations": [
    {{"id": 1, "title_zh": "中文题名", "abstract_zh": "中文摘要或空字符串"}}
  ]
}}

Papers:
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()
            text, _backend = llm.complete(
                prompt,
                "paper translation" if pass_number == 1 else "paper translation retry",
                required=True,
            )
            if not text:
                return False
            parsed = parse_jsonish(text)
            if not isinstance(parsed, dict) or not isinstance(parsed.get("translations"), list):
                llm.events.append("paper translation: LLM output was not valid JSON")
                continue
            by_id = {index: cand for index, cand in enumerate(batch, start=1)}
            for row in parsed["translations"]:
                if not isinstance(row, dict):
                    continue
                idx = safe_int(row.get("id"))
                cand = by_id.get(idx)
                if not cand:
                    continue
                title_zh = clean_text(strip_html(str(row.get("title_zh", ""))))
                abstract_zh = clean_text(strip_html(str(row.get("abstract_zh", ""))))
                if title_zh:
                    cand.title_zh = title_zh
                if abstract_zh:
                    cand.abstract_zh = abstract_zh
                elif cand.title_zh and not cand.abstract:
                    cand.abstract_zh = "原始元数据未提供摘要。"
            if progress_callback:
                progress_callback(
                    sum(complete(cand) for cand in targets), len(targets), pass_number
                )
        return True

    # Retry incomplete rows in multiple rounds. Each new round re-enables APIs/models
    # that may have been temporarily rate-limited or out of quota.
    retry_rounds = max(1, retry_rounds)
    retry_delay = max(0.0, retry_delay)
    for pass_number in range(1, retry_rounds + 1):
        pending = [cand for cand in targets if not complete(cand)]
        if not pending:
            break
        if pass_number > 1:
            if retry_delay:
                time.sleep(retry_delay)
            llm.reset_disabled_for_retry(f"paper translation round {pass_number}")
        translate_pass(pending, pass_number)

    translated = sum(complete(cand) for cand in targets)
    llm.events.append(f"paper translation coverage: {translated}/{len(targets)} final papers")
    return translated, len(targets)


def search_sources(
    plan: dict[str, Any],
    start_year: int,
    end_year: int,
    limit: int,
    source_names: list[str],
    progress_callback: Callable[[int, int, str, bool], None] | None = None,
) -> tuple[list[PaperCandidate], list[SourceIssue]]:
    source_map: dict[str, SearchSource] = {
        "openalex": OpenAlexSource(),
        "crossref": CrossrefSource(),
        "arxiv": ArxivSource(),
        "semantic_scholar": SemanticScholarSource(),
        "dblp": DBLPSource(),
        "ssrn": SSRNSource(),
    }
    issues: list[SourceIssue] = []
    selected = []
    for name in source_names:
        if name in {"none", "off", "disabled"}:
            return [], issues
        if name == "all":
            selected = list(source_map.values())
            break
        source = source_map.get(name)
        if source:
            selected.append(source)
        else:
            issues.append(SourceIssue(name, "config", "unknown source name"))

    all_candidates: list[PaperCandidate] = []
    per_source_limit = max(limit, 20)
    source_count = max(len(selected), 1)
    for index, source in enumerate(selected):
        if progress_callback:
            progress_callback(index, source_count, source.name, False)
        try:
            all_candidates.extend(
                source.search(plan, start_year, end_year, per_source_limit, issues)
            )
        except Exception as exc:  # Keep one source from killing the run.
            issues.append(SourceIssue(source.name, "unexpected_error", str(exc)))
        if progress_callback:
            progress_callback(min(index + 1, source_count), source_count, source.name, True)
    return all_candidates, issues


def score_candidates(candidates: list[PaperCandidate], plan: dict[str, Any]) -> None:
    for cand in candidates:
        score, reason_parts = rule_score(cand, plan)
        cand.score = score
        if not cand.reason:
            cand.reason = "; ".join(reason_parts[:4]) or "metadata match"
        if not cand.research_value:
            cand.research_value = rule_research_value(cand, plan)
        if not cand.risks:
            cand.risks = rule_risk(cand)


def rule_score(cand: PaperCandidate, plan: dict[str, Any]) -> tuple[float, list[str]]:
    text = " ".join([cand.title, cand.abstract, cand.venue]).lower()
    reasons: list[str] = []
    score = 0.0

    def count_matches(terms: Iterable[str]) -> list[str]:
        hits = []
        for term in terms:
            if academic_term_match(term, text):
                hits.append(term)
        return dedupe_keep_order(hits)

    method_hits = count_matches(plan.get("method_terms", []))
    data_hits = count_matches(plan.get("data_terms", []))
    target_hits = count_matches(plan.get("target_terms", []))
    must_hits = count_matches(plan.get("must_have_terms", []))
    nice_hits = count_matches(plan.get("nice_to_have_terms", []))
    exclude_hits = count_matches(plan.get("exclude_terms", []))

    score += min(26, len(method_hits) * 7)
    score += min(24, len(data_hits) * 6)
    score += min(26, len(target_hits) * 7)
    score += min(10, len(must_hits) * 3)
    score += min(8, len(nice_hits) * 1.2)

    if method_hits:
        reasons.append("method: " + ", ".join(method_hits[:4]))
    if data_hits:
        reasons.append("data: " + ", ".join(data_hits[:4]))
    if target_hits:
        reasons.append("target: " + ", ".join(target_hits[:4]))

    venue_bonus, venue_reason = venue_priority(cand, plan)
    score += venue_bonus
    if venue_reason:
        reasons.append(venue_reason)

    if cand.source in {"arXiv", "SSRN"}:
        score += 8
        reasons.append("recent-preprint source")
    if cand.year:
        if cand.year >= 2023:
            score += 9
            reasons.append("recent paper")
        elif cand.year >= 2018:
            score += 4
    if cand.abstract:
        score += 3
    else:
        score -= 6
        reasons.append("missing abstract")
    if cand.pdf_url:
        score += 2
    if exclude_hits:
        score -= min(30, len(exclude_hits) * 10)
        reasons.append("possible off-topic terms: " + ", ".join(exclude_hits[:3]))

    business_hits = [
        term
        for term in BUSINESS_CONTEXT_TERMS
        if re.search(rf"\b{re.escape(term)}\b", text)
    ]
    topical_hits = dedupe_keep_order(method_hits + data_hits + target_hits + must_hits + nice_hits)
    if not topical_hits:
        score *= 0.35
        reasons.append("no topic terms matched")
    elif not business_hits and not any_business_or_cs_venue(cand):
        # A strategy, marketing, or economics paper can be clearly relevant
        # without using finance-specific words such as "stock" or "firm".
        score *= 0.9
    title_hits = [
        term for term in dedupe_keep_order(plan.get("must_have_terms", [])[:4])
        if academic_term_match(term, cand.title.lower())
    ]
    if title_hits:
        score += min(24, len(title_hits) * 8)
        reasons.append("topic in title: " + ", ".join(title_hits))
    elif plan.get("must_have_terms"):
        score *= 0.55
        reasons.append("topic absent from title")
    if not cand.title:
        score = 0

    return max(0.0, min(100.0, score)), reasons


def any_business_or_cs_venue(cand: PaperCandidate) -> bool:
    venue = (cand.venue or "").lower()
    return any(
        venue_alias_match(venue, alias)
        for meta in BUSINESS_JOURNALS.values()
        for alias in meta["aliases"]
    ) or any(
        venue_alias_match(venue, alias)
        for aliases in CS_VENUES.values()
        for alias in aliases
    )


def venue_priority(
    cand: PaperCandidate,
    plan: dict[str, Any] | None = None,
) -> tuple[float, str]:
    venue = (cand.venue or "").lower()
    journals = target_business_journals(plan or {})
    for journal, meta in journals.items():
        for alias in meta["aliases"]:
            if venue_alias_match(venue, alias):
                return float(meta["priority"]), f"target business source: {journal}"
    for short, aliases in CS_VENUES.items():
        for alias in aliases:
            if venue_alias_match(venue, alias):
                return 13.0, f"target CS venue: {short}"
    combined = f"{venue} {(cand.title or '').lower()}"
    if any(hint in combined for hint in FINNLP_HINTS):
        return 8.0, "FinNLP/finance signal"
    if "journal of finance" in combined or "accounting" in combined:
        return 8.0, "finance/accounting adjacent source"
    return 0.0, ""


def venue_alias_match(venue_lower: str, alias: str) -> bool:
    alias_lower = alias.lower()
    if not venue_lower or not alias_lower:
        return False
    if len(alias_lower) <= 4:
        return bool(re.search(rf"\b{re.escape(alias_lower)}\b", venue_lower))
    return alias_lower in venue_lower


def rule_research_value(cand: PaperCandidate, plan: dict[str, Any]) -> str:
    text = " ".join([cand.title, cand.abstract]).lower()
    venue = (cand.venue or "").lower()
    if cand.source in {"arXiv", "SSRN"} and cand.year and cand.year >= 2023:
        return "Useful for tracking frontier methods and current research angles."
    if any(
        venue_alias_match(venue, alias)
        for meta in BUSINESS_JOURNALS.values()
        for alias in meta["aliases"]
    ):
        return "Useful for positioning the idea in the selected business discipline journals."
    if "earnings call" in text or "10-k" in text or "ipo" in text:
        return "Useful as a data/task anchor for corporate signal prediction."
    if "multimodal" in text or "large language model" in text or "llm" in text:
        return "Useful for method framing, especially if paired with business outcomes."
    return "Potentially useful after abstract/full-text screening."


def academic_term_match(term: str, text: str) -> bool:
    t = term.lower().strip()
    if not t:
        return False
    if t == "llm":
        return bool(re.search(r"\bllms?\b", text))
    if t == "large language model":
        return bool(re.search(r"\blarge\s+language\s+models?\b|\bllms?\b", text))
    if t == "artificial intelligence":
        return "artificial intelligence" in text or bool(re.search(r"\bai\b", text))
    if t in text:
        return True

    generic = {"analysis", "prediction", "study", "using"}
    tokens = [
        tok
        for tok in re.split(r"[^a-z0-9]+", t)
        if len(tok) >= 3 and tok not in generic
    ]
    if not tokens:
        return False
    matches = sum(
        1
        for tok in tokens
        if re.search(rf"\b{re.escape(tok)}s?\b", text)
    )
    if len(tokens) == 1:
        threshold = 1
    elif len(tokens) == 2:
        threshold = 2
    else:
        threshold = max(2, len(tokens) - 1)
    return matches >= threshold


def rule_risk(cand: PaperCandidate) -> str:
    if not cand.abstract:
        return "No abstract found; relevance is title/venue based and needs manual check."
    if cand.year and cand.year < 2020:
        return "Older work; may lag current LLM/multimodal methods."
    if cand.needs_permission:
        return "Likely needs library access for full text."
    if cand.source == "SSRN":
        return "SSRN metadata may be incomplete; verify manually."
    return "Check method details, data leakage, and outcome definition before relying on it."


def source_group_key(cand: PaperCandidate) -> str:
    if is_utd_candidate(cand):
        return "utd"
    if is_ssrn_candidate(cand):
        return "ssrn"
    if is_arxiv_candidate(cand):
        return "arxiv"
    if is_cs_candidate(cand):
        return "cs"
    if is_finnlp_candidate(cand):
        return "finnlp"
    return "other"


def source_group_label(key: str) -> str:
    labels = dict(SOURCE_GROUPS)
    return labels.get(key, labels["other"])


def grouped_candidates(candidates: list[PaperCandidate]) -> dict[str, list[PaperCandidate]]:
    groups: dict[str, list[PaperCandidate]] = {key: [] for key, _label in SOURCE_GROUPS}
    groups["all"] = list(candidates)
    for cand in candidates:
        groups.setdefault(source_group_key(cand), []).append(cand)
    for key, rows in groups.items():
        groups[key] = sorted(rows, key=lambda c: c.score, reverse=True)
    return groups


def display_grouped_candidates(candidates: list[PaperCandidate]) -> dict[str, list[PaperCandidate]]:
    groups: dict[str, list[PaperCandidate]] = {key: [] for key, _label in SOURCE_GROUPS}
    groups["all"] = list(candidates)
    for cand in candidates:
        matched = False
        if is_utd_candidate(cand):
            groups["utd"].append(cand)
            matched = True
        if is_ssrn_candidate(cand):
            groups["ssrn"].append(cand)
            matched = True
        if is_arxiv_candidate(cand):
            groups["arxiv"].append(cand)
            matched = True
        if is_cs_candidate(cand):
            groups["cs"].append(cand)
            matched = True
        if is_finnlp_candidate(cand):
            groups["finnlp"].append(cand)
            matched = True
        if not matched:
            groups["other"].append(cand)
    for key, rows in groups.items():
        groups[key] = sorted(rows, key=lambda c: c.score, reverse=True)
    return groups


def is_utd_candidate(cand: PaperCandidate) -> bool:
    venue = (cand.venue or "").lower()
    return any(
        venue_alias_match(venue, alias)
        for meta in BUSINESS_JOURNALS.values()
        for alias in meta["aliases"]
    )


def is_ssrn_candidate(cand: PaperCandidate) -> bool:
    source = (cand.source or "").lower()
    venue = (cand.venue or "").lower()
    return "ssrn" in source or "ssrn" in venue or "social science research network" in venue


def is_arxiv_candidate(cand: PaperCandidate) -> bool:
    source = (cand.source or "").lower()
    venue = (cand.venue or "").lower()
    return "arxiv" in source or venue.startswith("arxiv")


def is_cs_candidate(cand: PaperCandidate) -> bool:
    venue = (cand.venue or "").lower()
    if venue.startswith("arxiv:") and re.search(r"\bcs\.", venue):
        return True
    return any(
        venue_alias_match(venue, alias)
        for aliases in CS_VENUES.values()
        for alias in aliases
    )


def is_finnlp_candidate(cand: PaperCandidate) -> bool:
    combined = " ".join([cand.source or "", cand.venue or "", cand.title or "", cand.abstract or ""]).lower()
    return any(hint in combined for hint in FINNLP_HINTS) or "finance" in combined or "accounting" in combined


def balanced_select_candidates(
    candidates: list[PaperCandidate],
    limit: int,
    group_min: int | None,
) -> list[PaperCandidate]:
    if limit <= 0:
        return []
    if len(candidates) <= limit:
        return sorted(candidates, key=lambda c: c.score, reverse=True)
    if not group_min or group_min <= 0:
        return sorted(candidates, key=lambda c: c.score, reverse=True)[:limit]

    groups = grouped_candidates(candidates)
    selected: list[PaperCandidate] = []
    seen: set[str] = set()
    group_order = ["utd", "ssrn", "arxiv", "cs", "finnlp", "other"]
    effective_min = min(max(1, group_min), max(1, limit // 5))

    def add(cand: PaperCandidate) -> None:
        key = cand.doi.lower() if cand.doi else cand.normalized_title()
        if key in seen or len(selected) >= limit:
            return
        selected.append(cand)
        seen.add(key)

    for group_key in group_order:
        for cand in groups.get(group_key, [])[:effective_min]:
            add(cand)
            if len(selected) >= limit:
                break
        if len(selected) >= limit:
            break

    for cand in sorted(candidates, key=lambda c: c.score, reverse=True):
        add(cand)
        if len(selected) >= limit:
            break

    return sorted(selected, key=lambda c: c.score, reverse=True)


def dedupe_candidates(candidates: list[PaperCandidate]) -> list[PaperCandidate]:
    by_key: dict[str, PaperCandidate] = {}
    for cand in candidates:
        if not cand.title:
            continue
        keys = []
        if cand.doi:
            keys.append("doi:" + cand.doi.lower())
        keys.append("title:" + cand.normalized_title())
        key = keys[0] if cand.doi else keys[-1]
        existing = by_key.get(key)
        if not existing:
            by_key[key] = cand
            continue
        merge_candidate(existing, cand)
    # Second pass: merge exact normalized-title duplicates missed because DOI
    # differed across providers.
    by_title: dict[str, PaperCandidate] = {}
    for cand in by_key.values():
        key = cand.normalized_title()
        existing = by_title.get(key)
        if existing:
            merge_candidate(existing, cand)
        else:
            by_title[key] = cand
    return list(by_title.values())


def merge_candidate(base: PaperCandidate, other: PaperCandidate) -> None:
    if len(other.abstract) > len(base.abstract):
        base.abstract = other.abstract
    if not base.doi and other.doi:
        base.doi = other.doi
    if not base.url and other.url:
        base.url = other.url
    if not base.pdf_url and other.pdf_url:
        base.pdf_url = other.pdf_url
    if not base.venue and other.venue:
        base.venue = other.venue
    if not base.year and other.year:
        base.year = other.year
    if not base.authors and other.authors:
        base.authors = other.authors
    if base.citation_count is None or (
        other.citation_count is not None and other.citation_count > base.citation_count
    ):
        base.citation_count = other.citation_count
    if base.open_access is not True and other.open_access is True:
        base.open_access = True
        base.needs_permission = False
    elif base.needs_permission is None and other.needs_permission is not None:
        base.needs_permission = other.needs_permission
    if other.source not in base.source.split(" + "):
        base.source = base.source + " + " + other.source


def csv_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    """Keep spreadsheet applications from evaluating untrusted metadata as formulas."""
    return {
        key: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value
        for key, value in row.items()
    }


def write_outputs(
    query: str,
    plan: dict[str, Any],
    candidates: list[PaperCandidate],
    issues: list[SourceIssue],
    llm: LLMManager,
    output_dir: Path,
    start_year: int,
    end_year: int,
) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    slug = query_slug(plan.get("english_query") or query)
    base = output_dir / f"{stamp}-{slug}"
    html_path = base.with_suffix(".html")
    md_path = base.with_suffix(".md")
    csv_path = base.with_suffix(".csv")
    json_path = base.with_suffix(".json")

    rows = [cand.to_row() for cand in candidates]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["title"])
        writer.writeheader()
        writer.writerows(csv_safe_row(row) for row in rows)

    payload = {
        "query": query,
        "years": [start_year, end_year],
        "plan": plan,
        "llm_events": llm.events,
        "issues": [dataclasses.asdict(issue) for issue in issues],
        "results": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path.write_text(
        render_markdown(query, plan, candidates, issues, llm, start_year, end_year),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(query, plan, candidates, issues, llm, start_year, end_year),
        encoding="utf-8",
    )
    return html_path, md_path, csv_path, json_path


def render_markdown(
    query: str,
    plan: dict[str, Any],
    candidates: list[PaperCandidate],
    issues: list[SourceIssue],
    llm: LLMManager,
    start_year: int,
    end_year: int,
) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 文献检索结果 / Literature Search Results - {now}",
        "",
        f"**检索需求 / Query**: {query}",
        "",
        f"**年份 / Years**: {start_year}-{end_year}",
        "",
        f"**需求理解 / Interpreted Need**: {plan.get('summary', '')}",
        "",
        "## 检索计划 / Query Plan",
        "",
        "- 学科方向 / Disciplines: " + ", ".join(plan.get("selected_disciplines", [])),
        "- 目标期刊 / Target journals: " + ", ".join(plan.get("target_journals", [])),
        f"- 英文检索式 / English query: {plan.get('english_query', '')}",
        "- 扩展检索式 / Expanded queries:",
    ]
    for query_item in plan.get("expanded_queries", [])[:10]:
        lines.append(f"  - {query_item}")
    v2_audit = plan.get("search_v2_audit")
    if isinstance(v2_audit, dict):
        curve = " → ".join(str(value) for value in v2_audit.get("discovery_curve", []))
        counts = v2_audit.get("feedback_counts") or {}
        lines.extend(
            [
                "",
                "## Search V2 深搜审计",
                "",
                f"- 反馈：相关 {counts.get('relevant', 0)} / 不相关 {counts.get('irrelevant', 0)} / 不确定 {counts.get('uncertain', 0)}",
                f"- 发现曲线：{curve}",
                f"- 最终新增：{v2_audit.get('new_in_final', 0)}（高相关 {v2_audit.get('high_relevance_new_in_final', 0)}）",
                f"- 引用年份规则：{v2_audit.get('citation_year_policy', '')}",
                f"- 停止原因：{v2_audit.get('stopping_reason', '')}",
            ]
        )
    lines.extend(["", "## 结果 / Results", ""])
    if not candidates:
        lines.append("没有找到候选论文 / No candidate papers found. Check the source issues below.")
    for idx, cand in enumerate(candidates, start=1):
        lines.extend(render_candidate(idx, cand))
    lines.extend(["", "## 来源与权限说明 / Source And Permission Notes", ""])
    if issues:
        for issue in issues:
            lines.append(f"- {issue.source} / {issue.kind}: {issue.detail}")
    else:
        lines.append("- 没有来源级错误 / No source-level errors reported.")
    permission_candidates = [
        cand for cand in candidates if cand.needs_permission and not cand.pdf_url
    ]
    if permission_candidates:
        lines.append("")
        lines.append("可能需要图书馆权限 / Likely library-access checks:")
        for cand in permission_candidates[:30]:
            where = cand.venue or cand.source
            lines.append(f"- {cand.title} ({where})")
    lines.extend(["", "## LLM 兜底日志 / LLM Fallback Log", ""])
    if llm.events:
        for event in llm.events:
            lines.append(f"- {event}")
    else:
        lines.append("- LLM 未启用或未配置，已使用规则评分 / LLM was disabled or not configured; rule scoring was used.")
    lines.append("")
    return "\n".join(lines)


def markdown_external_link(label: str, raw_url: str) -> str:
    """Render only HTTP(S) destinations, quoting characters special to Markdown."""
    value = str(raw_url or "").strip()
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return ""
    if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or any(ord(char) < 32 for char in value)):
        return ""
    encoded = urllib.parse.quote(value, safe=":/?#[]@!$&'()*+,;=%-._~")
    return f"[{label}](<{encoded}>)"


def render_candidate(idx: int, cand: PaperCandidate) -> list[str]:
    links = []
    if cand.doi:
        doi_url = "https://doi.org/" + urllib.parse.quote(cand.doi.strip(), safe="/-._~")
        link = markdown_external_link("DOI", doi_url)
        if link:
            links.append(link)
    if cand.url:
        link = markdown_external_link("landing page", cand.url)
        if link:
            links.append(link)
    if cand.pdf_url:
        link = markdown_external_link("PDF", cand.pdf_url)
        if link:
            links.append(link)
    link_text = " | ".join(links) if links else "no link"
    authors = ", ".join(cand.authors[:6])
    if len(cand.authors) > 6:
        authors += ", et al."
    access = "open" if cand.open_access else "permission/unknown"
    year = cand.year or "n.d."
    abstract = truncate(cand.abstract, 900) if cand.abstract else "No abstract in metadata."
    abstract_zh = truncate(cand.abstract_zh, 900) if cand.abstract_zh else (
        "原始元数据未提供摘要 / No abstract in metadata." if not cand.abstract
        else "未生成中文翻译 / Not translated."
    )
    title_zh = cand.title_zh or "未生成中文题名 / Not translated."
    return [
        f"### {idx}. {cand.title}",
        "",
        f"- 中文题名 / Chinese title: {title_zh}",
        f"- 综合分 / Score: {cand.score:.1f}/100",
        f"- 作者 / Authors: {authors or 'unknown'}",
        f"- 来源分组 / Source group: {source_group_label(source_group_key(cand))}",
        f"- 年份 / 期刊会议 / 来源 / Year / venue / source: {year} / {cand.venue or 'unknown'} / {cand.source}",
        f"- 链接 / Links: {link_text}",
        f"- 获取状态 / Access: {access}",
        f"- 为什么相关 / Why relevant: {cand.reason}",
        f"- 研究价值 / Research value: {cand.research_value}",
        f"- 注意事项 / Caveat: {cand.risks}",
        f"- 中文摘要 / Chinese abstract: {abstract_zh}",
        f"- 英文摘要 / English abstract: {abstract}",
        "",
    ]


def bi(zh: str, en: str) -> str:
    """Render a report label that follows the Chinese/English switch."""
    return f'<span data-lang="zh">{h(zh)}</span><span data-lang="en">{h(en)}</span>'


def render_html(
    query: str,
    plan: dict[str, Any],
    candidates: list[PaperCandidate],
    issues: list[SourceIssue],
    llm: LLMManager,
    start_year: int,
    end_year: int,
) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    open_count = sum(1 for cand in candidates if cand.open_access or cand.pdf_url)
    permission_count = sum(1 for cand in candidates if cand.needs_permission and not cand.pdf_url)
    avg_score = sum(cand.score for cand in candidates) / len(candidates) if candidates else 0
    issue_count = len(issues)
    tabs_html = render_tabs_html(candidates, issues)
    query_items = "\n".join(
        f"<li>{h(item)}</li>" for item in plan.get("expanded_queries", [])[:10]
    )
    group_counts = display_grouped_candidates(candidates)
    source_items = "\n".join(
        f"<li>{bi(*label.split(' / ', 1)) if ' / ' in label else h(label)}: "
        f"{len(group_counts.get(key, []))}</li>"
        for key, label in SOURCE_GROUPS
        if key != "all"
    )
    issues_html = render_issues_html(issues, candidates)
    llm_html = render_llm_events_html(llm)
    v2_audit = plan.get("search_v2_audit")
    v2_html = ""
    if isinstance(v2_audit, dict):
        feedback_counts = v2_audit.get("feedback_counts") or {}
        curve = " → ".join(str(value) for value in v2_audit.get("discovery_curve", []))
        v2_html = f"""
    <section class="v2-banner">
      <strong>{bi("两轮深搜", "Two-round deep search")}</strong>
      <span>{bi("反馈", "Feedback")}: {bi("相关", "Relevant")} {h(feedback_counts.get("relevant", 0))} / {bi("不相关", "Irrelevant")} {h(feedback_counts.get("irrelevant", 0))} / {bi("不确定", "Uncertain")} {h(feedback_counts.get("uncertain", 0))}</span>
      <span>{bi("发现曲线", "Discovery curve")}: {h(curve)} · {bi("最终新增", "New in final set")} {h(v2_audit.get("new_in_final", 0))}</span>
      <span>{h(v2_audit.get("stopping_reason", ""))}</span>
    </section>
"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>文献检索报告 / Literature Search Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: oklch(97% 0.010 83);
      --panel: oklch(99% 0.008 83);
      --ink: oklch(21% 0.018 152);
      --muted: oklch(43% 0.011 152);
      --line: oklch(79% 0.013 83);
      --accent: oklch(39% 0.085 153);
      --accent-2: oklch(48% 0.09 75);
      --good: oklch(36% 0.080 153);
      --warn: oklch(48% 0.09 75);
      --bad: oklch(45% 0.12 27);
    }}
    html[lang="zh-CN"] [data-lang="en"], html[lang="en"] [data-lang="zh"] {{ display: none !important; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "IBM Plex Sans", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
      line-height: 1.55;
    }}
    .page {{
      width: min(1180px, calc(100% - 36px));
      margin: 0 auto;
      padding: 28px 0 46px;
    }}
    header {{
      border-bottom: 2px solid var(--ink);
      padding: 0 0 18px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 26px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0;
      font-size: 19px;
      line-height: 1.35;
      letter-spacing: 0;
    }}
    .title-zh {{
      margin-top: 5px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.45;
    }}
    .subtitle, .meta, .small {{
      color: var(--muted);
      font-size: 14px;
    }}
    .query-box {{
      background: oklch(94% 0.012 83);
      border: 1px solid var(--line);
      padding: 14px 16px;
      margin-top: 14px;
    }}
    .v2-banner {{
      display: grid;
      grid-template-columns: auto 1fr 1fr;
      gap: 8px 18px;
      align-items: center;
      background: oklch(94% 0.012 83);
      border: 1px solid var(--line);
      border-left: 1px solid var(--line);
      padding: 12px 14px;
      margin: 0 0 16px;
      font-size: 13px;
    }}
    .v2-banner span:last-child {{
      grid-column: 1 / -1;
      color: var(--muted);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0 22px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 12px;
      min-height: 86px;
    }}
    .stat strong {{
      display: block;
      font-size: 26px;
      line-height: 1.1;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 290px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}
    aside {{
      position: sticky;
      top: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 14px;
    }}
    aside ul {{
      margin: 8px 0 0;
      padding-left: 18px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 1px solid var(--line);
      margin-bottom: 14px;
      padding: 16px;
    }}
    .tabs {{
      background: transparent;
    }}
    .tab-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 12px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    .tab-btn {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      padding: 8px 10px;
      font-weight: 700;
      cursor: pointer;
      font-size: 13px;
    }}
    .tab-btn.active {{
      border-color: var(--accent);
      background: var(--accent);
      color: var(--panel);
    }}
    .tab-panel {{
      display: none;
    }}
    .tab-panel.active {{
      display: block;
    }}
    .card-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 96px;
      gap: 16px;
      align-items: start;
    }}
    .score {{
      text-align: right;
      font-weight: 700;
      font-size: 24px;
      color: var(--accent);
    }}
    .score small {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 500;
    }}
    .scorebar {{
      height: 7px;
      background: oklch(90% 0.014 83);
      margin: 10px 0 12px;
      overflow: hidden;
    }}
    .scorebar span {{
      display: block;
      height: 100%;
      background: var(--accent);
    }}
    .badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 10px 0;
    }}
    .badge {{
      border: 1px solid var(--line);
      background: oklch(94% 0.012 83);
      color: var(--ink);
      padding: 3px 7px;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .badge.open {{ color: var(--good); border-color: var(--line); background: oklch(94% 0.02 153); }}
    .badge.warn {{ color: var(--warn); border-color: var(--line); background: oklch(95% 0.02 75); }}
    .badge.source {{ color: var(--accent); border-color: var(--line); background: oklch(94% 0.02 153); }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0;
    }}
    .btn {{
      display: inline-block;
      border: 1px solid var(--accent);
      color: var(--accent);
      background: oklch(94% 0.02 153);
      padding: 6px 10px;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
    }}
    .btn.primary {{
      background: var(--accent);
      color: var(--panel);
    }}
    .btn.secondary {{
      border-color: var(--accent-2);
      color: var(--accent-2);
      background: oklch(95% 0.02 75);
    }}
    .fields {{
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr);
      gap: 6px 12px;
      margin-top: 10px;
      font-size: 14px;
    }}
    .field-label {{
      color: var(--muted);
      font-weight: 600;
    }}
    .field-value {{
      overflow-wrap: anywhere;
    }}
    details {{
      border-top: 1px solid var(--line);
      margin-top: 12px;
      padding-top: 10px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 700;
      color: var(--accent);
    }}
    .abstract {{
      margin: 10px 0 0;
      color: var(--ink);
    }}
    .abstract.zh {{
      background: oklch(94% 0.02 153);
      border-left: 1px solid var(--accent);
      padding: 10px 12px;
      margin-bottom: 12px;
    }}
    .abstract-block .field-label {{
      margin-top: 10px;
    }}
    .notes {{
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 14px;
      margin-top: 18px;
    }}
    .notes li {{
      margin-bottom: 6px;
      overflow-wrap: anywhere;
    }}
    .empty {{
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 22px;
    }}
    .empty span {{
      display: block;
      color: var(--muted);
      margin-top: 4px;
    }}
    @media (max-width: 860px) {{
      .stats, .layout, .card-head, .v2-banner {{
        grid-template-columns: 1fr;
      }}
      aside {{
        position: static;
      }}
      .score {{
        text-align: left;
      }}
      .fields {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <button type="button" id="language-toggle" class="btn" style="float:right" aria-label="Switch report language">EN / 中文</button>
      <h1>{bi("商科文献雷达 · 检索报告", "Business Literature Radar · Search Report")}</h1>
      <div class="subtitle">{bi("生成时间", "Generated")}: {h(now)} · {bi("年份", "Years")}: {start_year}-{end_year}</div>
      <div class="query-box">
        <strong>{bi("检索需求", "Research query")}</strong>
        <div>{h(query)}</div>
      </div>
    </header>

    {v2_html}

    <section class="stats" aria-label="summary">
      <div class="stat"><strong>{len(candidates)}</strong><span>{bi("候选论文", "Results")}</span></div>
      <div class="stat"><strong>{open_count}</strong><span>{bi("开放链接", "Open/PDF links")}</span></div>
      <div class="stat"><strong>{permission_count}</strong><span>{bi("疑似需权限", "May need access")}</span></div>
      <div class="stat"><strong>{avg_score:.1f}</strong><span>{bi("平均分", "Average score")}</span></div>
      <div class="stat"><strong>{issue_count}</strong><span>{bi("来源问题", "Source notes")}</span></div>
    </section>

    <section class="layout">
      <aside>
        <h2>{bi("检索计划", "Query plan")}</h2>
        <p class="small"><strong>{bi("需求理解", "Interpreted need")}</strong><br>{h(plan.get("summary", ""))}</p>
        <p class="small"><strong>{bi("学科方向", "Disciplines")}</strong><br>{h(", ".join(plan.get("selected_disciplines", [])))}</p>
        <p class="small"><strong>{bi("目标期刊", "Target journals")}</strong><br>{h(", ".join(plan.get("target_journals", [])))}</p>
        <p class="small"><strong>{bi("英文检索式", "English query")}</strong><br>{h(plan.get("english_query", ""))}</p>
        <details open>
          <summary>{bi("扩展检索式", "Expanded queries")}</summary>
          <ul>{query_items}</ul>
        </details>
        <details open>
          <summary>{bi("来源分组", "Source groups")}</summary>
          <ul>{source_items}</ul>
        </details>
      </aside>

      <section>
        <h2>{bi("按来源分组", "Results by source")}</h2>
        {tabs_html}
      </section>
    </section>

    <section class="notes">
      <h2>{bi("来源与权限说明", "Source and access notes")}</h2>
      {issues_html}
    </section>

    <section class="notes">
      <h2>{bi("模型使用记录", "Model usage log")}</h2>
      {llm_html}
    </section>
  </main>
  <script>
    const setLanguage = (language) => {{
      document.documentElement.lang = language === "en" ? "en" : "zh-CN";
      try {{ localStorage.setItem("blr-report-language", language); }} catch (_) {{}}
    }};
    try {{ setLanguage(localStorage.getItem("blr-report-language") || "zh"); }} catch (_) {{ setLanguage("zh"); }}
    document.getElementById("language-toggle").addEventListener("click", () => {{
      setLanguage(document.documentElement.lang === "en" ? "zh" : "en");
    }});
    document.querySelectorAll("[data-tab-target]").forEach((button) => {{
      button.addEventListener("click", () => {{
        const target = button.getAttribute("data-tab-target");
        document.querySelectorAll("[data-tab-target]").forEach((btn) => btn.classList.remove("active"));
        document.querySelectorAll("[data-tab-panel]").forEach((panel) => panel.classList.remove("active"));
        button.classList.add("active");
        const panel = document.querySelector(`[data-tab-panel="${{target}}"]`);
        if (panel) panel.classList.add("active");
      }});
    }});
  </script>
</body>
</html>
"""


def render_tabs_html(candidates: list[PaperCandidate], issues: list[SourceIssue]) -> str:
    groups = display_grouped_candidates(candidates)
    buttons = []
    panels = []
    for index, (key, label) in enumerate(SOURCE_GROUPS):
        rows = groups.get(key, [])
        active = " active" if index == 0 else ""
        zh, separator, en = label.partition(" / ")
        buttons.append(
            f'<button class="tab-btn{active}" type="button" data-tab-target="{h(key)}">'
            f"{bi(zh, en if separator else zh)} <span>({len(rows)})</span></button>"
        )
        if rows:
            cards = "\n".join(
                render_candidate_html(idx, cand, id_prefix=key)
                for idx, cand in enumerate(rows, 1)
            )
        else:
            cards = render_empty_group_html(key, issues)
        panels.append(
            f'<section class="tab-panel{active}" data-tab-panel="{h(key)}">{cards}</section>'
        )
    return (
        '<div class="tabs">'
        f'<div class="tab-list" role="tablist">{"".join(buttons)}</div>'
        f'{"".join(panels)}'
        "</div>"
    )


def render_empty_group_html(key: str, issues: list[SourceIssue]) -> str:
    messages = {
        "utd": ("所选商科期刊暂无候选；可扩大年份或修改检索式。",
                "No candidates from the selected business journals. Widen the years or revise the query."),
        "ssrn": ("没有抓到 SSRN 论文；站点可能限制自动访问。",
                 "No SSRN papers were retrieved; the site may restrict automated access."),
        "arxiv": ("没有 arXiv 候选；可放宽技术关键词或年份。",
                  "No arXiv candidates. Broaden technical terms or the year range."),
        "cs": ("没有 CS/ML 来源候选；可调整技术检索词。",
               "No CS/ML candidates. Try different technical search terms."),
        "finnlp": ("没有额外 FinNLP / Finance 候选。", "No additional FinNLP / Finance candidates."),
        "other": ("没有其他来源候选。", "No candidates from other sources."),
        "all": ("没有找到候选论文。", "No candidate papers found."),
    }
    zh, en = messages.get(key, ("没有该来源候选。", "No candidates in this source."))
    related = [
        issue
        for issue in issues
        if key == "ssrn" and "SSRN" in issue.source
    ]
    issue_html = ""
    if related:
        issue_html = "<ul>" + "".join(
            f"<li>{h(issue.kind)}: {h(issue.detail)}</li>" for issue in related[:5]
        ) + "</ul>"
    return (
        '<section class="empty">'
        f"{bi(zh, en)}"
        f"<span>{h(source_group_label(key))}</span>"
        f"{issue_html}"
        "</section>"
    )


def render_candidate_html(idx: int, cand: PaperCandidate, id_prefix: str = "paper") -> str:
    authors = ", ".join(cand.authors[:8])
    if len(cand.authors) > 8:
        authors += ", et al."
    year = cand.year or "n.d."
    access_text = bi("开放", "Open") if cand.open_access or cand.pdf_url else bi("权限未知", "Permission unknown")
    access_class = "open" if cand.open_access or cand.pdf_url else "warn"
    score_width = max(0, min(100, cand.score))
    badges = [
        f'<span class="badge source">{h(cand.source)}</span>',
        f'<span class="badge">{h(str(year))}</span>',
        f'<span class="badge {access_class}">{access_text}</span>',
    ]
    if cand.venue:
        badges.append(f'<span class="badge">{h(cand.venue)}</span>')
    links = []
    if cand.pdf_url:
        links.append(html_link_button(bi("PDF 全文", "Full-text PDF"), cand.pdf_url, "primary", escape_label=False))
    if cand.doi:
        links.append(html_link_button("DOI", f"https://doi.org/{cand.doi}", "secondary"))
    if cand.url:
        links.append(html_link_button(bi("文章页", "Article page"), cand.url, "", escape_label=False))
    if not links:
        links.append(f'<span class="small">{bi("没有可用链接", "No link available")}</span>')
    abstract = cand.abstract or "No abstract in metadata."
    abstract_zh = cand.abstract_zh or (
        "原始元数据未提供摘要。" if not cand.abstract else
        "未生成中文翻译。启用翻译后将为全部最终结果尝试生成译文。"
    )
    title_zh_html = (
        f'<div class="title-zh">{h(cand.title_zh)}</div>' if cand.title_zh else ""
    )
    return f"""
<article class="card" id="{h(id_prefix)}-paper-{idx}">
  <div class="card-head">
    <div>
      <h3>{idx}. {h(cand.title)}</h3>
      {title_zh_html}
      <div class="badges">{"".join(badges)}</div>
    </div>
    <div class="score">{cand.score:.1f}<small>/100</small></div>
  </div>
  <div class="scorebar" aria-hidden="true"><span style="width: {score_width:.1f}%"></span></div>
  <div class="links">{"".join(links)}</div>
  <div class="fields">
    <div class="field-label">{bi("作者", "Authors")}</div><div class="field-value">{h(authors or "unknown")}</div>
    <div class="field-label">{bi("年份", "Year")}</div><div class="field-value">{h(str(year))}</div>
    <div class="field-label">{bi("期刊会议", "Venue")}</div><div class="field-value">{h(cand.venue or "unknown")}</div>
    <div class="field-label">{bi("为什么相关", "Why relevant")}</div><div class="field-value">{h(cand.reason)}</div>
    <div class="field-label">{bi("研究价值", "Research value")}</div><div class="field-value">{h(cand.research_value)}</div>
    <div class="field-label">{bi("注意事项", "Caveats")}</div><div class="field-value">{h(cand.risks)}</div>
  </div>
  <details>
    <summary>{bi("摘要", "Abstract")}</summary>
    <div class="abstract-block">
      <div class="field-label">{bi("中文摘要", "Chinese translation")}</div>
      <p class="abstract zh">{h(abstract_zh)}</p>
      <div class="field-label">{bi("英文原文", "Original abstract")}</div>
      <p class="abstract">{h(abstract)}</p>
    </div>
  </details>
</article>
"""


def render_issues_html(issues: list[SourceIssue], candidates: list[PaperCandidate]) -> str:
    lines = []
    if issues:
        lines.append("<ul>")
        for issue in issues:
            lines.append(
                f"<li><strong>{h(issue.source)}</strong> / {h(issue.kind)}: {h(issue.detail)}</li>"
            )
        lines.append("</ul>")
    else:
        lines.append(f"<p>{bi('没有来源级错误。', 'No source-level errors reported.')}</p>")

    permission_candidates = [
        cand for cand in candidates if cand.needs_permission and not cand.pdf_url
    ]
    if permission_candidates:
        lines.append(f"<h3>{bi('可能需要图书馆权限', 'Likely library-access checks')}</h3>")
        lines.append("<ul>")
        for cand in permission_candidates[:30]:
            where = cand.venue or cand.source
            lines.append(f"<li>{h(cand.title)} <span class=\"small\">({h(where)})</span></li>")
        lines.append("</ul>")
    return "\n".join(lines)


def render_llm_events_html(llm: LLMManager) -> str:
    if not llm.events:
        return f"<p>{bi('未启用模型，已使用规则评分。', 'No model was used; results were ranked by rules.')}</p>"
    return "<ul>" + "".join(f"<li>{h(event)}</li>" for event in llm.events) + "</ul>"


def html_link_button(label: str, href: str, css_class: str, escape_label: bool = True) -> str:
    href = str(href or "").strip()
    try:
        parsed = urllib.parse.urlsplit(href)
    except ValueError:
        return ""
    if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or any(ord(char) < 32 for char in href)):
        return ""
    classes = "btn" + (f" {css_class}" if css_class else "")
    return (
        f'<a class="{classes}" href="{h(href)}" target="_blank" '
        f'rel="noopener noreferrer">{h(label) if escape_label else label}</a>'
    )


def h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search business/CS/FinNLP papers from open metadata sources."
    )
    parser.add_argument("query", nargs="?", help="Natural-language research need.")
    parser.add_argument("--years", default="2018-2026", help="Year range, e.g. 2018-2026.")
    parser.add_argument("--limit", type=int, default=50, help="Final result count.")
    parser.add_argument(
        "--sources",
        default="openalex,crossref,arxiv,semantic_scholar,dblp,ssrn",
        help=(
            "Comma-separated sources: openalex,crossref,arxiv,semantic_scholar,"
            "dblp,ssrn or all."
        ),
    )
    parser.add_argument(
        "--llm-backend",
        choices=["auto", "opencode", "rules"],
        default="rules",
        help="LLM strategy; rules mode never calls a model.",
    )
    parser.add_argument(
        "--api-provider",
        choices=[
            "auto", "openai", "anthropic", "openai_compatible", "opencode",
            "codex_cli", "gemini_cli", "rules",
        ],
        default="rules",
        help="User-owned LLM provider. API keys are read from LIT_SEARCH_API_KEY.",
    )
    parser.add_argument("--api-endpoint", default="", help="LLM HTTPS endpoint URL.")
    parser.add_argument("--api-models", default="", help="Comma-separated API model fallback order.")
    parser.add_argument(
        "--no-opencode-fallback",
        action="store_true",
        help="Do not fall back to OpenCode after an API provider fails.",
    )
    parser.add_argument(
        "--llm-budget-calls",
        type=int,
        default=4,
        help=(
            "Maximum LLM calls. Planning/rerank usually use two calls; "
            "abstract translation uses extra batched calls only when requested."
        ),
    )
    parser.add_argument("--llm-timeout", type=int, default=90)
    parser.add_argument("--llm-max-candidates", type=int, default=25)
    parser.add_argument(
        "--translate-abstracts",
        nargs="?",
        const=10,
        default=0,
        type=int,
        help=(
            "Translate abstracts into Chinese for the first N final papers. "
            "Use --translate-abstracts for 10, or --translate-abstracts 30."
        ),
    )
    parser.add_argument(
        "--translation-batch-size",
        type=int,
        default=5,
        help="Number of abstracts per translation LLM call.",
    )
    parser.add_argument(
        "--translation-char-limit",
        type=int,
        default=1800,
        help="Maximum English abstract characters sent per paper for translation.",
    )
    parser.add_argument(
        "--translation-retry-rounds",
        type=int,
        default=6,
        help="Maximum model-rotation rounds for incomplete translations.",
    )
    parser.add_argument(
        "--translation-retry-delay",
        type=float,
        default=2.0,
        help="Seconds to wait before re-enabling unavailable translation backends.",
    )
    parser.add_argument(
        "--group-min",
        type=int,
        default=None,
        help=(
            "Best-effort minimum papers to preserve per source group before "
            "global truncation. Keeps arXiv from crowding out business/SSRN/CS."
        ),
    )
    parser.add_argument(
        "--per-source",
        type=int,
        default=5,
        help=(
            "Target number of papers to preserve for each major source tab "
            "(business journals, SSRN, arXiv, CS/ML, FinNLP). Default: 5."
        ),
    )
    parser.add_argument(
        "--disciplines",
        default="is,qm",
        help=(
            "Business PhD disciplines: is,qm,om,strategy,finance,accounting,"
            "management,marketing,economics,stats,behavioral,political_economy,"
            "healthcare,ethics."
        ),
    )
    parser.add_argument(
        "--opencode-models",
        default=",".join(DEFAULT_OPENCODE_MODELS),
        help="Comma-separated opencode model fallback order.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--create-run-folder",
        action="store_true",
        help="Create an MMDD-HHMM-topic subfolder after query planning.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Emit machine-readable progress events for the graphical interface.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Generate the search plan, write/print it, and exit before retrieval.",
    )
    parser.add_argument(
        "--plan-output",
        default="",
        help="JSON path used by --plan-only.",
    )
    parser.add_argument(
        "--plan-file",
        default="",
        help="Use an existing edited JSON plan instead of planning again.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run local parser/scoring tests.")
    parser.add_argument("--test-llm", action="store_true", help="Test the configured LLM and exit.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    def report_progress(percent: int, stage: str, detail: str = "") -> None:
        if not args.progress:
            return
        payload = {"percent": percent, "stage": stage, "detail": detail}
        # ASCII-only transport avoids GBK/UTF-8 pipe disagreements on Windows.
        print("__PROGRESS__" + json.dumps(payload, ensure_ascii=True), flush=True)

    if args.self_test:
        return run_self_test()
    if args.test_llm:
        llm = build_llm_manager(args)
        text, backend = llm.complete(
            'Return only this JSON: {"status":"ok"}',
            "connection test",
            required=True,
        )
        if text:
            print(f"LLM connection OK: {backend}")
            return 0
        print("LLM connection failed: " + " | ".join(llm.events), file=sys.stderr)
        return 4
    if not args.query:
        print("ERROR: provide a natural-language query or use --self-test", file=sys.stderr)
        return 2
    start_year, end_year = parse_year_range(args.years)
    source_names = [s.strip() for s in args.sources.split(",") if s.strip()]
    disciplines = [
        value.strip().lower()
        for value in args.disciplines.split(",")
        if value.strip().lower() in DISCIPLINE_LABELS
    ] or ["is", "qm"]
    llm = build_llm_manager(args)

    report_progress(4, "正在准备", "检查检索参数与可用服务")
    print("[1/5] Planning query...", flush=True)
    report_progress(8, "规划检索", "扩展关键词与研究主题")
    if args.plan_file:
        try:
            plan = load_search_plan(Path(args.plan_file), args.query, disciplines)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"[1/5] Using edited search plan: {args.plan_file}", flush=True)
    else:
        plan = llm_query_plan(args.query, llm, disciplines)

    if args.plan_only:
        if args.plan_output:
            plan_path = save_search_plan(plan, Path(args.plan_output))
            print(
                "__PLAN_PATH__"
                + json.dumps({"path": str(plan_path)}, ensure_ascii=True),
                flush=True,
            )
        else:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        report_progress(100, "检索计划已生成", "等待用户确认或编辑")
        return 0

    output_dir = Path(args.output_dir)
    if args.create_run_folder:
        folder_stamp = dt.datetime.now().strftime("%m%d-%H%M")
        output_dir = output_dir / f"{folder_stamp}-{plan_folder_slug(plan, args.query)}"
        print(
            "__OUTPUT_DIR__"
            + json.dumps({"path": str(output_dir)}, ensure_ascii=True),
            flush=True,
        )
        report_progress(14, "规划完成", f"主题概括：{plan.get('folder_title', '')}")

    report_progress(18, "检索文献", "即将连接开放学术数据源")
    print("[2/5] Searching metadata sources...", flush=True)

    def source_progress(done: int, total: int, source_name: str, finished: bool) -> None:
        percent = 18 + round(50 * done / max(total, 1))
        if finished:
            detail = f"已完成 {source_name}（{done}/{total}）"
        else:
            detail = f"正在检索 {source_name}（{done + 1}/{total}）"
        report_progress(percent, "检索文献", detail)

    raw_candidates, issues = search_sources(
        plan=plan,
        start_year=start_year,
        end_year=end_year,
        limit=args.limit,
        source_names=source_names,
        progress_callback=source_progress,
    )

    report_progress(70, "整理结果", f"合并 {len(raw_candidates)} 条候选记录")
    print(f"[3/5] Deduplicating {len(raw_candidates)} raw candidates...", flush=True)
    candidates = dedupe_candidates(raw_candidates)
    score_candidates(candidates, plan)
    candidates = sorted(candidates, key=lambda c: c.score, reverse=True)

    report_progress(78, "智能排序", "评估相关性与研究价值")
    print("[4/5] Reranking top candidates with optional LLM...", flush=True)
    rerank_with_llm(args.query, plan, candidates, llm, args.llm_max_candidates)
    per_source = args.group_min if args.group_min is not None else args.per_source
    major_source_count = 5  # Business journals, SSRN, arXiv, CS/ML, FinNLP
    final_limit = args.limit
    if per_source and per_source > 0:
        final_limit = max(args.limit, per_source * major_source_count)
        if final_limit != args.limit:
            print(
                f"[4/5] Raising final limit from {args.limit} to {final_limit} "
                f"to preserve about {per_source} papers per major source."
            )
    candidates = balanced_select_candidates(
        sorted(candidates, key=lambda c: c.score, reverse=True),
        limit=final_limit,
        group_min=per_source,
    )

    translation_coverage: tuple[int, int] | None = None
    if args.translate_abstracts > 0:
        report_progress(86, "翻译摘要", "生成中文摘要，耗时取决于 LLM 服务")
        print("[4b/5] Translating abstracts with optional LLM...", flush=True)

        def translation_progress(done: int, total: int, round_number: int) -> None:
            percent = 86 + round(7 * done / max(total, 1))
            report_progress(
                percent,
                "翻译全部结果",
                f"第 {round_number} 轮：已完成 {done}/{total} 篇",
            )

        translation_coverage = translate_abstracts_with_llm(
            candidates=candidates,
            llm=llm,
            max_items=args.translate_abstracts,
            char_limit=args.translation_char_limit,
            batch_size=args.translation_batch_size,
            retry_rounds=args.translation_retry_rounds,
            retry_delay=args.translation_retry_delay,
            progress_callback=translation_progress,
        )

    report_progress(94, "生成报告", "写入 HTML、Markdown、CSV 与 JSON")
    print("[5/5] Writing outputs...", flush=True)
    html_path, md_path, csv_path, json_path = write_outputs(
        query=args.query,
        plan=plan,
        candidates=candidates,
        issues=issues,
        llm=llm,
        output_dir=output_dir,
        start_year=start_year,
        end_year=end_year,
    )
    print(f"HTML:     {html_path}")
    print(f"Markdown: {md_path}")
    print(f"CSV:      {csv_path}")
    print(f"JSON:     {json_path}")
    if translation_coverage and translation_coverage[0] < translation_coverage[1]:
        translated, total = translation_coverage
        print(
            f"ERROR: translation incomplete after model rotation: {translated}/{total}",
            file=sys.stderr,
            flush=True,
        )
        report_progress(100, "翻译未完成", f"已翻译 {translated}/{total} 篇；报告已保留")
        return 3
    report_progress(100, "检索完成", f"共整理 {len(candidates)} 篇文献")
    return 0


def fetch_json(
    url: str,
    source: str,
    issues: list[SourceIssue],
    timeout: int = 30,
) -> dict[str, Any] | None:
    text = fetch_text(url, source, issues, timeout=timeout)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        issues.append(SourceIssue(source, "parse_error", str(exc)))
        return None


def fetch_text(
    url: str,
    source: str,
    issues: list[SourceIssue],
    timeout: int = 30,
) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return open_url_text(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        kind = "permission_or_rate_limit" if exc.code in {401, 403, 429} else "http_error"
        issues.append(SourceIssue(source, kind, f"HTTP {exc.code}: {detail}"))
    except (urllib.error.URLError, TimeoutError) as exc:
        detail = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in detail and source == "DBLP":
            try:
                text = open_url_text(
                    request,
                    timeout=timeout,
                    context=ssl._create_unverified_context(),
                )
                issues.append(
                    SourceIssue(
                        source,
                        "ssl_fallback",
                        "Used DBLP metadata after local certificate verification failed.",
                    )
                )
                return text
            except Exception as fallback_exc:
                detail = f"{detail}; DBLP SSL fallback failed: {fallback_exc}"
        if "10013" in detail:
            detail = (
                "Network access was blocked by the current sandbox/OS policy "
                "(WinError 10013). Re-run with network permission."
            )
        issues.append(SourceIssue(source, "network_error", detail))
    return None


def open_url_text(
    request: urllib.request.Request,
    timeout: int,
    context: ssl.SSLContext | None = None,
) -> str:
    kwargs = {"timeout": timeout}
    if context is not None:
        kwargs["context"] = context
    with urllib.request.urlopen(request, **kwargs) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def parse_jsonish(text: str) -> Any:
    cleaned = strip_ansi(text).strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    starts = [i for i in [cleaned.find("{"), cleaned.find("[")] if i >= 0]
    if not starts:
        return None
    start = min(starts)
    end_obj = cleaned.rfind("}")
    end_arr = cleaned.rfind("]")
    end = max(end_obj, end_arr)
    if end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def parse_year_range(value: str) -> tuple[int, int]:
    match = re.match(r"^\s*(\d{4})(?:\s*[-:]\s*(\d{4}))?\s*$", value)
    if not match:
        raise SystemExit(f"Invalid --years: {value}")
    start = int(match.group(1))
    end = int(match.group(2) or match.group(1))
    if end < start:
        raise SystemExit("--years end must be >= start")
    return start, end


def parse_model_list(value: str) -> list[str]:
    models = [m.strip() for m in value.split(",") if m.strip()]
    return models or DEFAULT_OPENCODE_MODELS


def plan_queries(plan: dict[str, Any], max_queries: int) -> list[str]:
    queries = []
    if plan.get("english_query"):
        queries.append(str(plan["english_query"]))
    queries.extend(str(q) for q in plan.get("expanded_queries", []))
    return dedupe_keep_order([clean_text(q) for q in queries if clean_text(q)])[:max_queries]


def arxiv_queries(plan: dict[str, Any]) -> list[str]:
    provided = [q for q in plan.get("arxiv_queries", []) if q]
    if provided:
        return provided
    queries = []
    for query in plan_queries(plan, max_queries=4):
        tokens = [
            t
            for t in re.split(r"[^A-Za-z0-9]+", query)
            if len(t) >= 3 and t.lower() not in {"and", "the", "for", "with"}
        ]
        if tokens:
            queries.append(" AND ".join(f"all:{token}" for token in tokens[:5]))
    return queries or ["all:financial AND all:prediction"]


def normalize_arxiv_query(query: str) -> str:
    query = clean_text(query)
    if "all:" in query and not re.search(r"\b(?:AND|OR|ANDNOT)\b", query):
        query = re.sub(r"\s+(?=all:)", " AND ", query)
    return query


def ssrn_search_url(query: str) -> str:
    params = {
        "RequestTimeout": "50000000",
        "txtKey_Words": query,
        "sort": "date",
    }
    return "https://papers.ssrn.com/sol3/results.cfm?" + urllib.parse.urlencode(params)


def strip_doi(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
    return value


def reconstruct_openalex_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, locs in index.items():
        for loc in locs:
            positions.append((loc, word))
    return clean_text(" ".join(word for _loc, word in sorted(positions)))


def crossref_year(item: dict[str, Any]) -> int | None:
    for key in ["published-print", "published-online", "published", "issued"]:
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0]:
            return safe_int(parts[0][0])
    return None


def dblp_authors(value: Any) -> list[str]:
    if not value:
        return []
    author = value.get("author") if isinstance(value, dict) else value
    if isinstance(author, str):
        return [clean_text(author)]
    if isinstance(author, list):
        result = []
        for item in author:
            if isinstance(item, str):
                result.append(clean_text(item))
            elif isinstance(item, dict):
                result.append(clean_text(item.get("text", "")))
        return [x for x in result if x]
    if isinstance(author, dict):
        return [clean_text(author.get("text", ""))]
    return []


def infer_permission(pdf_url: str, open_access: bool | None) -> bool | None:
    if pdf_url:
        return False
    if open_access is True:
        return False
    if open_access is False:
        return True
    return None


def first_text(value: Any) -> str:
    if isinstance(value, list):
        return clean_text(str(value[0])) if value else ""
    if isinstance(value, str):
        return clean_text(value)
    return ""


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def strip_html(value: str) -> str:
    unescaped = html.unescape(value or "")
    return clean_text(re.sub(r"<[^>]+>", " ", unescaped))


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def normalize_title(title: str) -> str:
    title = strip_html(title).lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    stop = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "with"}
    tokens = [tok for tok in title.split() if tok not in stop]
    return " ".join(tokens)


def dedupe_keep_order(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clamp_float(value: Any, low: float, high: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = low
    return max(low, min(high, numeric))


def truncate(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def query_slug(value: str) -> str:
    tokens = [
        tok.lower()
        for tok in re.split(r"[^A-Za-z0-9]+", value)
        if len(tok) >= 3
    ]
    if not tokens:
        return "query"
    return "-".join(tokens[:8])


def rule_folder_title(query: str) -> str:
    """不调用额外服务时，从研究需求中提炼一个短主题名。"""
    lowered = query.lower()
    chinese = bool(re.search(r"[\u4e00-\u9fff]", query))
    parts: list[str] = []

    def add(label_zh: str, label_en: str, *needles: str) -> None:
        if len(parts) < 3 and any(needle in lowered for needle in needles):
            label = label_zh if chinese else label_en
            if label not in parts:
                parts.append(label)

    add("大模型", "llm", "llm", "large language model", "大模型", "语言模型")
    if not parts:
        add("人工智能", "ai", "人工智能", " ai", "machine learning", "机器学习")
    add("路演", "roadshow", "路演", "roadshow")
    add("公司披露", "corporate-disclosure", "公司披露", "corporate disclosure", "公告")
    add("财报", "financial-report", "财报", "annual report", "financial report", "10-k")
    add("业绩电话", "earnings-call", "业绩电话", "电话会议", "earnings call")
    add("多模态", "multimodal", "多模态", "multimodal", "视频", "图片", "图像", "音频", "语音")
    add("IPO预测", "ipo-prediction", "ipo", "上市成功")
    add("股价预测", "stock-prediction", "股价", "stock price", "stock return")
    add("风险预测", "risk-prediction", "暴雷", "风险", "crash", "fraud", "违约")
    add("平台治理", "platform-governance", "平台治理", "platform governance")
    add("创新", "innovation", "创新", "innovation")
    add("供应链", "supply-chain", "供应链", "supply chain")
    add("消费者", "consumer", "消费者", "consumer")
    add("营销", "marketing", "营销", "marketing")
    add("审计", "audit", "审计", "audit")
    add("商业经济", "economics", "经济", "economics")

    if parts:
        return "-".join(parts[:3])

    if chinese:
        return "商科研究"
    stop = {
        "about", "and", "for", "from", "into", "literature", "papers",
        "research", "search", "study", "that", "the", "this", "using", "with",
    }
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", query)
        if len(token) >= 3 and token.lower() not in stop
    ]
    return "-".join(tokens[:4]) or "literature-search"


def plan_folder_slug(plan: dict[str, Any], query: str) -> str:
    """把 LLM/规则产生的主题名清理为简短、安全的文件夹片段。"""
    title = clean_text(str(plan.get("folder_title") or rule_folder_title(query)))
    title = re.sub(r"[<>:\"/\\|?*]+", " ", title)
    title = re.sub(r"[^\w\u4e00-\u9fff\s-]", " ", title, flags=re.UNICODE)
    title = re.sub(r"[\s_]+", "-", title.strip())
    title = re.sub(r"-+", "-", title).strip("-. ")
    if not title:
        title = "文献检索" if re.search(r"[\u4e00-\u9fff]", query) else "literature-search"
    return title[:36].rstrip("-. ")


def run_self_test() -> int:
    plan = rule_query_plan(
        "利用AI/LLM处理公司文本视频语音图片预测IPO是否成功、股价状态、暴雷状态"
    )
    candidate = PaperCandidate(
        id="test",
        source="arXiv",
        title="Large Language Models for Financial Text and Stock Crash Risk Prediction",
        year=2025,
        venue="arXiv:cs.CL",
        abstract=(
            "We use large language models and financial NLP on corporate "
            "disclosures and earnings calls to predict stock price crash risk."
        ),
        pdf_url="https://arxiv.org/pdf/0000.00000",
        open_access=True,
        needs_permission=False,
    )
    score, reasons = rule_score(candidate, plan)
    assert score > 60, (score, reasons)
    parsed = parse_jsonish('```json\n{"expanded_queries":["x"]}\n```')
    assert parsed == {"expanded_queries": ["x"]}
    assert "Journal of Finance" in journals_for_disciplines(["finance"])
    assert "MIS Quarterly" not in journals_for_disciplines(["finance"])
    assert "American Economic Review" in journals_for_disciplines(["economics"])
    assert "Journal of the American Statistical Association" in journals_for_disciplines(["stats"])
    assert "Health Affairs" in journals_for_disciplines(["healthcare"])
    assert OpenAIResponsesBackend("x", "k", ["m"]).extract_text(
        {"output": [{"content": [{"type": "output_text", "text": "ok"}]}]}
    ) == "ok"
    assert AnthropicMessagesBackend("x", "k", ["m"]).extract_text(
        {"content": [{"type": "text", "text": "ok"}]}
    ) == "ok"
    assert OpenAICompatibleBackend("x", "k", ["m"]).extract_text(
        {"choices": [{"message": {"content": "ok"}}]}
    ) == "ok"
    cli_command_cases = {
        "codex_cli": [
            "codex", "exec", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", "hello",
        ],
        "gemini_cli": ["gemini", "-p", "hello", "--output-format", "json"],
    }
    for provider, expected in cli_command_cases.items():
        backend = AgentCLIBackend(provider, ["auto"])
        backend.executable = AgentCLIBackend.COMMANDS[provider][0]
        assert backend._command("auto", "hello") == expected
        model_command = backend._command("test-model", "hello")
        assert "test-model" in model_command

    class FakeTranslationManager:
        def __init__(self) -> None:
            self.calls = 0
            self.events: list[str] = []

        def complete(
            self, prompt: str, _purpose: str, required: bool = False
        ) -> tuple[str, str]:
            self.calls += 1
            payload = json.loads(prompt.split("Papers:\n", 1)[1])
            rows = []
            for item in payload:
                # Deliberately omit one row on the first pass to exercise retry.
                if self.calls == 1 and item["id"] == 2:
                    continue
                rows.append(
                    {
                        "id": item["id"],
                        "title_zh": f"中文题名 {item['id']}",
                        "abstract_zh": "中文摘要" if item["abstract"] else "",
                    }
                )
            return json.dumps({"translations": rows}, ensure_ascii=False), "fake"

        def reset_disabled_for_retry(self, _purpose: str) -> None:
            pass

    translation_candidates = [
        PaperCandidate(id="t1", source="test", title="Paper one", abstract="Abstract one"),
        PaperCandidate(id="t2", source="test", title="Paper two", abstract="Abstract two"),
        PaperCandidate(id="t3", source="test", title="Paper three"),
    ]
    fake_llm = FakeTranslationManager()
    translate_abstracts_with_llm(
        translation_candidates,
        fake_llm,  # type: ignore[arg-type]
        max_items=3,
        char_limit=500,
        batch_size=2,
        retry_delay=0,
    )
    assert all(cand.title_zh for cand in translation_candidates)
    assert all(cand.abstract_zh for cand in translation_candidates)
    assert fake_llm.calls == 3
    print("self-test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
