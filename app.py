#!/usr/bin/env python3
"""Local-only web application for Business Literature Radar.

The browser never receives an API key. Search jobs run in a separate process so
Stop can interrupt a slow provider without corrupting the web server.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import app_settings
import search_papers
import search_v2


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ASSET_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "web"
OUTPUT_DIR = APP_DIR / "output"
TOKEN = secrets.token_urlsafe(32)
MAX_BODY = 64 * 1024
STAGE_EN = {
    "正在准备": "Preparing", "规划检索": "Planning the search",
    "检索计划已生成": "Search plan ready", "规划完成": "Plan ready",
    "检索文献": "Searching sources", "整理结果": "Organizing results",
    "智能排序": "Ranking papers", "翻译摘要": "Translating abstracts",
    "翻译全部结果": "Translating every result", "生成报告": "Writing reports",
    "检索完成": "Search complete", "翻译未完成": "Translation incomplete",
    "整理反馈": "Reviewing feedback", "第二轮检索": "Second-round search",
    "引用扩展": "Exploring citations", "合并与重排": "Merging and ranking",
    "生成深搜报告": "Writing deep-search report", "深搜完成": "Deep search complete",
    "任务失败": "Task failed", "正在停止": "Stopping", "已停止": "Stopped",
}
SOURCE_IDS = {"openalex", "crossref", "arxiv", "semantic_scholar", "dblp", "ssrn"}
API_PROVIDERS = {"openai", "anthropic", "openai_compatible"}
ADVANCED_PROVIDERS = {"opencode", "gemini_cli"}
ALL_PROVIDERS = API_PROVIDERS | ADVANCED_PROVIDERS


def _public_config(settings: dict[str, Any]) -> dict[str, Any]:
    key = str(settings.get("api_key", ""))
    return {
        "provider": settings.get("provider", "openai"),
        "api_endpoint": settings.get("endpoint", ""),
        "api_models": settings.get("models", ""),
        "llm_backend": settings.get("llm_backend", "rules"),
        "has_key": bool(key),
        "masked_key": app_settings.masked_key(key) if key else "",
        "configured": bool(settings.get("configured")),
    }


def _row_identity(row: dict[str, Any]) -> str:
    return search_v2.feedback_key(row)


def _public_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row, identity=_row_identity(row),
                 publication_source=search_papers.publication_name(search_v2.candidate_from_row(row)))
            for row in rows if isinstance(row, dict)]


def _parse_selection(values: Any, allowed: set[str], default: list[str]) -> list[str]:
    if not isinstance(values, list):
        return default
    result = [str(value) for value in values if str(value) in allowed]
    return list(dict.fromkeys(result)) or default


def _validate_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query", "")).strip()
    if not 3 <= len(query) <= 3000:
        raise ValueError("检索需求需为 3–3000 个字符 / Query must be 3–3000 characters.")
    years = str(payload.get("years", "2018-2026")).strip()
    if not re.fullmatch(r"\d{4}-\d{4}", years):
        raise ValueError("年份格式应为 YYYY-YYYY / Use YYYY-YYYY for years.")
    first, last = map(int, years.split("-"))
    if first < 1900 or last > dt.datetime.now().year + 1 or first > last:
        raise ValueError("请检查年份范围 / Check the year range.")
    try:
        limit = int(payload.get("limit", 30))
    except (TypeError, ValueError) as exc:
        raise ValueError("文献数量必须是整数 / Result count must be an integer.") from exc
    if not 1 <= limit <= 150:
        raise ValueError("文献数量应在 1–150 之间 / Choose 1–150 papers.")
    disciplines = _parse_selection(payload.get("disciplines"), set(search_papers.DISCIPLINE_LABELS), ["is", "or"])
    incoming_scopes = payload.get("publication_scopes", payload.get("sources"))
    public_selection = not isinstance(incoming_scopes, list) or not incoming_scopes or any(
        str(value) == "utd24" for value in incoming_scopes
    ) or all(str(value) in search_papers.PUBLICATION_SCOPE_IDS for value in incoming_scopes)
    scopes: list[str] | None = None
    journals: list[str] | None = None
    if public_selection:
        if isinstance(incoming_scopes, list) and not incoming_scopes:
            raise ValueError("请选择至少一种文献来源 / Select at least one publication source.")
        if isinstance(incoming_scopes, list) and any(str(value) not in search_papers.PUBLICATION_SCOPE_IDS for value in incoming_scopes):
            raise ValueError("请选择 UTD24 期刊、arXiv 或 SSRN / Select UTD24 journals, arXiv or SSRN.")
        scopes = _parse_selection(incoming_scopes, search_papers.PUBLICATION_SCOPE_IDS, ["utd24", "arxiv", "ssrn"])
        incoming_journals = payload.get("journals")
        if incoming_journals is not None and not isinstance(incoming_journals, list):
            raise ValueError("期刊选择格式不正确 / Invalid journal selection.")
        if isinstance(incoming_journals, list) and any(str(name) not in search_papers.UTD24_JOURNALS for name in incoming_journals):
            raise ValueError("期刊不在 UTD24 列表中 / A selected journal is not in UTD24.")
        journals = (list(dict.fromkeys(str(name) for name in incoming_journals if str(name) in search_papers.UTD24_JOURNALS))
                    if incoming_journals is not None else search_papers.utd24_journals_for_disciplines(disciplines))
        if "utd24" in scopes and not journals:
            raise ValueError("请至少选择一本 UTD24 期刊 / Select at least one UTD24 journal.")
        sources = search_papers.metadata_sources_for_scopes(scopes)
    else:
        sources = _parse_selection(payload.get("sources"), SOURCE_IDS, ["openalex", "crossref", "semantic_scholar"])
    return {
        "query": query,
        "years": years,
        "limit": limit,
        "disciplines": disciplines,
        "sources": sources,
        "publication_scopes": scopes,
        "journals": journals,
        "translate": bool(payload.get("translate", False)),
        "plan": payload.get("plan") if isinstance(payload.get("plan"), dict) else None,
    }


def _safe_endpoint(value: str, provider: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urllib.parse.urlsplit(value)
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("API 地址不能含账户、查询参数或片段 / Use a clean API endpoint URL.")
    if parsed.scheme != "https" and not (
        provider == "openai_compatible"
        and parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("API 地址必须使用 HTTPS；仅本机兼容接口可用 HTTP。")
    if not parsed.hostname:
        raise ValueError("请填写有效 API 地址 / Enter a valid API endpoint.")
    return value


class Controller:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.settings = app_settings.load_settings()
        self.settings.setdefault("llm_backend", "rules")
        self.job: dict[str, Any] | None = None
        self.process: subprocess.Popen[str] | None = None
        self.report_json: Path | None = None
        self.feedback: list[dict[str, Any]] = []
        self.history: list[dict[str, Any]] = []

    def state(self) -> dict[str, Any]:
        with self.lock:
            return {
                "config": _public_config(self.settings),
                "job": dict(self.job) if self.job else None,
                "history": list(self.history[:8]),
                "feedback": list(self.feedback),
            }

    def save_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider = str(payload.get("provider", self.settings.get("provider", "openai")))
        mode = str(payload.get("llm_backend", self.settings.get("llm_backend", "rules")))
        if provider not in ALL_PROVIDERS or mode not in {"api", "codex", "advanced", "rules"}:
            raise ValueError("请选择支持的模型入口 / Choose a supported model mode.")
        if (mode == "api" and provider not in API_PROVIDERS) or (mode == "advanced" and provider not in ADVANCED_PROVIDERS):
            raise ValueError("模型入口与服务商不匹配 / The model mode and provider do not match.")
        endpoint = _safe_endpoint(str(payload.get("api_endpoint", "")), provider)
        models = str(payload.get("api_models", "")).strip()
        if len(models) > 600:
            raise ValueError("模型列表过长 / Model list is too long.")
        incoming_key = str(payload.get("api_key", "")).strip()
        if len(incoming_key) > 1000:
            raise ValueError("API Key 过长 / API key is too long.")
        with self.lock:
            previous_provider = self.settings.get("provider")
            existing_key = self.settings.get("api_key", "") if provider == previous_provider else ""
            key = "" if payload.get("clear_key") is True else incoming_key or existing_key
            if mode == "api" and provider in API_PROVIDERS and not key:
                raise ValueError("请先输入自己的 API Key；也可选 Codex 或规则模式。")
            if mode == "api" and provider == "openai_compatible" and not endpoint:
                raise ValueError("兼容接口需要 API 地址 / Compatible API needs an endpoint.")
            updated = dict(self.settings)
            updated.update({
                "provider": provider,
                "endpoint": endpoint,
                "models": models,
                "api_key": key,
                "llm_backend": mode,
                "configured": True,
            })
            app_settings.save_settings(updated)
            self.settings = updated
            return _public_config(updated)

    def _provider_args(self) -> list[str]:
        with self.lock:
            cfg = dict(self.settings)
        mode = cfg.get("llm_backend", "rules")
        provider = "rules" if mode == "rules" else "codex_cli" if mode == "codex" else cfg.get("provider", "rules")
        args = ["--api-provider", provider, "--llm-backend", "rules" if provider == "rules" else "auto"]
        if provider in API_PROVIDERS:
            args.extend(["--api-endpoint", cfg.get("endpoint", ""), "--api-models", cfg.get("models", "")])
        elif provider in ADVANCED_PROVIDERS:
            args.extend(["--api-models", cfg.get("models", "")])
        args.extend(["--no-opencode-fallback", "--llm-budget-calls", "12"])
        return args

    def _command(self, engine: str) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--engine", engine]
        script = "search_papers.py" if engine == "search" else "search_v2.py"
        return [sys.executable, "-u", str(APP_DIR / script)]

    def _start(self, kind: str, fn: Any, spec: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            if self.job and self.job["status"] in {"queued", "running", "stopping"}:
                raise ValueError("已有任务在运行；请等待或先停止 / A job is already running.")
            job = {
                "id": secrets.token_hex(8), "kind": kind, "status": "queued",
                "percent": 0, "stage": "等待启动", "stage_zh": "等待启动", "stage_en": "Starting",
                "detail": "", "detail_zh": "", "detail_en": "", "error": "",
                "plan": None, "results": [], "report_url": "", "report_json_url": "",
                "started_at": dt.datetime.now().isoformat(timespec="seconds"),
                "query": (spec or {}).get("query", ""),
                "years": (spec or {}).get("years", ""),
                "limit": (spec or {}).get("limit", 0),
                "disciplines": (spec or {}).get("disciplines", []),
                "sources": (spec or {}).get("publication_scopes") or (spec or {}).get("sources", []),
                "publication_scopes": (spec or {}).get("publication_scopes"),
                "journals": (spec or {}).get("journals"),
            }
            self.job = job
        threading.Thread(target=self._run, args=(job["id"], fn), daemon=True).start()
        return dict(job)

    def _run(self, job_id: str, fn: Any) -> None:
        with self.lock:
            if not self.job or self.job["id"] != job_id:
                return
            if self.job["status"] == "stopping":
                self.job.update(status="stopped", stage="已停止", stage_zh="已停止",
                                stage_en="Stopped", detail="任务已中断",
                                detail_zh="任务已中断", detail_en="The job was stopped.")
                return
            self.job["status"] = "running"
        try:
            fn(job_id)
            with self.lock:
                if self.job and self.job["id"] == job_id and self.job["status"] != "stopping":
                    self.job.update(status="completed", percent=100)
        except Exception as exc:  # UI must receive a bounded, actionable failure.
            with self.lock:
                if self.job and self.job["id"] == job_id:
                    if self.job["status"] == "stopping":
                        self.job.update(status="stopped", stage="已停止", stage_zh="已停止",
                                        stage_en="Stopped", detail="任务已中断",
                                        detail_zh="任务已中断", detail_en="The job was stopped.")
                    else:
                        self.job.update(status="failed", error=str(exc)[:700], stage="任务失败",
                                        stage_zh="任务失败", stage_en="Task failed")

    def _execute(self, job_id: str, command: list[str]) -> tuple[int, list[str]]:
        with self.lock:
            if self.job and self.job["id"] == job_id and self.job["status"] == "stopping":
                raise RuntimeError("任务已由用户停止 / Job stopped by user.")
        env = os.environ.copy()
        with self.lock:
            key = str(self.settings.get("api_key", ""))
        env["LIT_SEARCH_API_KEY"] = key
        env["PYTHONIOENCODING"] = "utf-8"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = subprocess.Popen(
            command, cwd=APP_DIR, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
            creationflags=flags, start_new_session=os.name != "nt",
        )
        with self.lock:
            self.process = proc
        lines: list[str] = []
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("__PROGRESS__"):
                    try:
                        progress = json.loads(line[len("__PROGRESS__"):])
                        with self.lock:
                            if self.job and self.job["id"] == job_id:
                                stage = str(progress.get("stage", ""))[:100]
                                detail = str(progress.get("detail", ""))[:240]
                                self.job.update({
                                    "percent": max(0, min(100, int(progress.get("percent", 0)))),
                                    "stage": stage, "stage_zh": stage,
                                    "stage_en": STAGE_EN.get(stage, stage),
                                    "detail": detail, "detail_zh": detail,
                                    "detail_en": STAGE_EN.get(stage, "Working") + " — " + str(progress.get("percent", 0)) + "%",
                                })
                    except (ValueError, TypeError):
                        pass
                else:
                    lines.append(line.replace(key, "[REDACTED]") if key else line)
                    lines = lines[-35:]
            return proc.wait(), lines
        finally:
            if proc.stdout is not None:
                proc.stdout.close()
            with self.lock:
                if self.process is proc:
                    self.process = None

    def _checked_exit(self, code: int, lines: list[str]) -> None:
        with self.lock:
            stopping = bool(self.job and self.job["status"] == "stopping")
        if stopping:
            raise RuntimeError("任务已由用户停止 / Job stopped by user.")
        if code:
            reason = next((line for line in reversed(lines) if line.startswith("ERROR:")), "")
            if code == 3:
                raise RuntimeError((reason or "翻译未覆盖全部文献") + "；已保留报告，请检查模型额度并重试。")
            raise RuntimeError(reason or f"检索程序退出，代码 {code}。请检查网络与模型配置。")

    def plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        spec = _validate_search(payload)

        def task(job_id: str) -> None:
            with tempfile.TemporaryDirectory(prefix="blr-plan-") as tmp:
                plan_path = Path(tmp) / "plan.json"
                command = self._command("search") + [
                    spec["query"], "--years", spec["years"], "--limit", str(spec["limit"]),
                    "--disciplines", ",".join(spec["disciplines"]),
                    "--sources", ",".join(spec["sources"]),
                    "--plan-only", "--plan-output", str(plan_path), "--progress",
                ] + self._provider_args()
                if spec["publication_scopes"] is not None:
                    command.extend(["--publication-scopes", ",".join(spec["publication_scopes"]),
                                    "--target-journals", ",".join(spec["journals"] or [])])
                code, lines = self._execute(job_id, command)
                self._checked_exit(code, lines)
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                with self.lock:
                    if self.job and self.job["id"] == job_id:
                        self.job["plan"] = plan
                        self.job["stage"] = "检索计划已生成"
                        self.job["stage_zh"] = "检索计划已生成"
                        self.job["stage_en"] = "Search plan ready"

        return self._start("plan", task, spec)

    def _make_run_dir(self, plan: dict[str, Any], query: str) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%m%d-%H%M")
        slug = search_papers.plan_folder_slug(plan, query)[:28].rstrip("-_. ") or "research"
        base = OUTPUT_DIR / f"{stamp}-{slug}"
        path = base
        suffix = 2
        while path.exists():
            path = OUTPUT_DIR / f"{base.name}-{suffix}"
            suffix += 1
        path.mkdir()
        return path

    def _finish_report(self, job_id: str, directory: Path) -> None:
        reports = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        reports = [p for p in reports if p.name not in {"search_plan.json", "feedback.json", "search_v2_session.json"}]
        if not reports:
            raise RuntimeError("检索已结束，但未生成报告 / The search finished without a report.")
        report_json = reports[0]
        report = json.loads(report_json.read_text(encoding="utf-8"))
        rows = _public_results(report.get("results", []))
        html_path = report_json.with_suffix(".html")
        with self.lock:
            self.report_json = report_json
            if self.job and self.job["id"] == job_id:
                self.job.update({
                    "plan": report.get("plan"),
                    "results": rows,
                    "report_url": self._report_url(html_path),
                    "report_json_url": self._report_url(report_json),
                    "detail": f"已整理 {len(rows)} 篇文献",
                })
                self.history.insert(0, {
                    "query": report.get("query", ""),
                    "count": len(rows),
                    "report_url": self._report_url(html_path),
                    "created_at": dt.datetime.now().isoformat(timespec="minutes"),
                })

    @staticmethod
    def _report_url(path: Path) -> str:
        return "/reports/" + urllib.parse.quote(str(path.relative_to(OUTPUT_DIR)).replace("\\", "/"), safe="/")

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        spec = _validate_search(payload)
        plan = spec["plan"]
        if plan is None:
            with self.lock:
                plan = self.job.get("plan") if self.job else None
        if not isinstance(plan, dict):
            raise ValueError("请先生成检索计划 / Generate a search plan first.")
        with self.lock:
            mode = self.settings.get("llm_backend", "rules")
        if spec["translate"] and mode == "rules":
            raise ValueError("翻译全部文献需要先配置 API 或 Codex；规则模式不会伪造译文。")
        plan = search_papers.sanitize_plan(dict(plan), spec["query"])
        plan["selected_disciplines"] = spec["disciplines"]
        if spec["publication_scopes"] is not None:
            search_papers.set_publication_selection(plan, spec["publication_scopes"], spec["journals"])
        else:
            plan["target_journals"] = list(search_papers.journals_for_disciplines(spec["disciplines"]))

        def task(job_id: str) -> None:
            directory = self._make_run_dir(plan, spec["query"])
            plan_path = search_papers.save_search_plan(plan, directory / "search_plan.json")
            command = self._command("search") + [
                spec["query"], "--years", spec["years"], "--limit", str(spec["limit"]),
                "--disciplines", ",".join(spec["disciplines"]),
                "--sources", ",".join(spec["sources"]),
                "--plan-file", str(plan_path), "--output-dir", str(directory),
                "--per-source", "0", "--progress",
            ] + self._provider_args()
            if spec["translate"]:
                command.extend(["--translate-abstracts", "10000"])
            code, lines = self._execute(job_id, command)
            if code == 3:
                self._finish_report(job_id, directory)
            self._checked_exit(code, lines)
            self._finish_report(job_id, directory)

        return self._start("search", task, spec)

    def _feedback_rows(self, submitted: Any) -> list[dict[str, Any]]:
        if not isinstance(submitted, list):
            raise ValueError("反馈格式不正确 / Invalid feedback format.")
        with self.lock:
            rows = list(self.job.get("results", [])) if self.job else []
        known = {row["identity"]: row for row in rows}
        output = []
        for item in submitted:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", ""))
            label = str(item.get("label", item.get("state", "uncertain")))
            if key in known and label in {"relevant", "irrelevant", "uncertain"}:
                row = known[key]
                output.append({"key": key, "title": row.get("title", ""), "doi": row.get("doi", ""), "state": label})
        return output

    def save_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        feedback = self._feedback_rows(payload.get("feedback"))
        with self.lock:
            self.feedback = feedback
        return {"feedback": feedback}

    def deep_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        feedback = self._feedback_rows(payload.get("feedback", self.feedback))
        if not any(row["state"] in {"relevant", "irrelevant"} for row in feedback):
            raise ValueError("请先标记至少一篇相关或不相关文献 / Mark at least one paper.")
        with self.lock:
            prior = self.report_json
            results = list(self.job.get("results", [])) if self.job else []
            cfg_mode = self.settings.get("llm_backend", "rules")
        if not prior or not prior.exists():
            raise ValueError("请先完成首轮检索 / Complete the first search round.")
        translated = bool(results) and all(row.get("title_zh") and (not row.get("abstract") or row.get("abstract_zh")) for row in results)
        if translated and cfg_mode == "rules":
            raise ValueError("两轮结果要保持全量翻译，请先配置模型再深搜。")
        with self.lock:
            self.feedback = feedback

        def task(job_id: str) -> None:
            feedback_path = prior.parent / "feedback.json"
            feedback_path.write_text(json.dumps({"feedback": feedback}, ensure_ascii=False, indent=2), encoding="utf-8")
            deep_dir = prior.parent / "deep-search"
            suffix = 2
            while deep_dir.exists():
                deep_dir = prior.parent / f"deep-search-{suffix}"
                suffix += 1
            deep_dir.mkdir()
            command = self._command("v2") + [
                "--report-json", str(prior), "--feedback-json", str(feedback_path),
                "--limit", str(len(results)), "--output-dir", str(deep_dir), "--progress",
            ] + self._provider_args()
            if translated:
                command.append("--translate-abstracts")
            code, lines = self._execute(job_id, command)
            if code == 3:
                self._finish_report(job_id, deep_dir)
            self._checked_exit(code, lines)
            self._finish_report(job_id, deep_dir)

        prior_report = json.loads(prior.read_text(encoding="utf-8"))
        prior_plan = prior_report.get("plan") or {}
        return self._start("deep-search", task, {
            "query": prior_report.get("query", ""),
            "years": "-".join(map(str, prior_report.get("years", []))),
            "limit": len(results), "disciplines": prior_plan.get("selected_disciplines", []),
            "publication_scopes": prior_plan.get("publication_scopes"),
            "journals": prior_plan.get("target_journals"),
        })

    def stop(self) -> dict[str, Any]:
        with self.lock:
            if not self.job or self.job["status"] not in {"queued", "running"}:
                return dict(self.job) if self.job else {}
            self.job.update(status="stopping", stage="正在停止", stage_zh="正在停止",
                            stage_en="Stopping", detail="正在中断当前检索",
                            detail_zh="正在中断当前检索", detail_en="Interrupting the active search")
            proc = self.process
        if proc and proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW, check=False)
            else:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        return self.state().get("job") or {}


CONTROLLER = Controller()


class Handler(BaseHTTPRequestHandler):
    server_version = "BusinessLiteratureRadar/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Local console logs intentionally omit query strings and credentials.
        return

    def _send(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, payload: Any) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "").split(":")[0].lower()
        return host in {"127.0.0.1", "localhost", "[::1]"}

    def _guard(self, write: bool = False) -> bool:
        if not self._host_ok():
            self._json(HTTPStatus.FORBIDDEN, {"error": "Local access only."})
            return False
        if write:
            origin = self.headers.get("Origin", "")
            if origin and urllib.parse.urlsplit(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Invalid origin."})
                return False
            if self.headers.get("X-Session-Token", "") != TOKEN:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Invalid local session token."})
                return False
        return True

    def do_GET(self) -> None:
        if not self._guard():
            return
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path == "/api/state":
            self._json(HTTPStatus.OK, CONTROLLER.state())
            return
        if path == "/api/meta":
            disciplines = []
            for key in search_papers.PUBLIC_DISCIPLINE_IDS:
                label = search_papers.DISCIPLINE_LABELS[key]
                en, _, zh = label.partition(" / ")
                disciplines.append({"id": key, "label_zh": zh or en, "label_en": en})
            sources = [
                {"id": "utd24", "label_zh": "UTD24 期刊", "label_en": "UTD24 journals"},
                {"id": "arxiv", "label_zh": "arXiv", "label_en": "arXiv"},
                {"id": "ssrn", "label_zh": "SSRN", "label_en": "SSRN"},
            ]
            journals = [{"id": name, "label_zh": name, "label_en": name,
                         "disciplines": meta["disciplines"]}
                        for name, meta in search_papers.UTD24_JOURNALS.items()]
            labels = {"openai": ("OpenAI API", "OpenAI API"), "anthropic": ("Claude API", "Claude API"),
                      "openai_compatible": ("兼容 API", "Compatible API"), "opencode": ("OpenCode CLI", "OpenCode CLI"),
                      "gemini_cli": ("Gemini CLI", "Gemini CLI")}
            providers = [{"id": key, "label_zh": zh, "label_en": en,
                          "endpoint": value["endpoint"], "models": value["models"],
                          "key_hint": value["key_hint"]}
                         for key, value in app_settings.PROVIDER_PRESETS.items() if key in labels
                         for zh, en in [labels[key]]]
            self._json(HTTPStatus.OK, {"disciplines": disciplines, "sources": sources,
                                      "journals": journals, "providers": providers})
            return
        if path.startswith("/reports/"):
            relative = path.removeprefix("/reports/")
            resolved = (OUTPUT_DIR / relative).resolve()
            if not resolved.is_relative_to(OUTPUT_DIR.resolve()) or resolved.suffix not in {".html", ".json", ".md", ".csv"} or not resolved.is_file():
                self._json(HTTPStatus.NOT_FOUND, {"error": "Report not found."})
                return
            mime = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
            self._send(HTTPStatus.OK, resolved.read_bytes(), mime + ("; charset=utf-8" if resolved.suffix in {".html", ".json", ".md"} else ""))
            return
        if path == "/":
            path = "/index.html"
        if path.startswith("/web/"):
            path = path.removeprefix("/web")
        resolved = (ASSET_DIR / path.lstrip("/")).resolve()
        if not resolved.is_relative_to(ASSET_DIR.resolve()) or not resolved.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        data = resolved.read_bytes()
        if resolved.name == "index.html":
            data = data.replace(b"__SESSION_TOKEN__", TOKEN.encode("ascii"))
        mime = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self._send(HTTPStatus.OK, data, mime + ("; charset=utf-8" if resolved.suffix in {".html", ".css", ".js"} else ""))

    def do_POST(self) -> None:
        if not self._guard(write=True):
            return
        path = urllib.parse.urlsplit(self.path).path
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                raise ValueError("请求内容过大或为空 / Request body is empty or too large.")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("请求格式不正确 / Expected a JSON object.")
            if path == "/api/config":
                result = {"config": CONTROLLER.save_config(payload)}
            elif path == "/api/plan":
                result = {"job": CONTROLLER.plan(payload)}
            elif path == "/api/search":
                result = {"job": CONTROLLER.search(payload)}
            elif path == "/api/feedback":
                result = CONTROLLER.save_feedback(payload)
            elif path == "/api/deep-search":
                result = {"job": CONTROLLER.deep_search(payload)}
            elif path == "/api/stop":
                result = {"job": CONTROLLER.stop()}
            elif path == "/api/shutdown":
                CONTROLLER.stop()
                result = {"stopped": True}
                threading.Timer(0.25, self.server.shutdown).start()
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint."})
                return
            self._json(HTTPStatus.OK, result)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"本地服务遇到问题 / Local service error: {exc}"})


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--engine":
        engine = sys.argv[2]
        if engine == "search":
            raise SystemExit(search_papers.main(sys.argv[3:]))
        if engine == "v2":
            raise SystemExit(search_v2.main(sys.argv[3:]))
        if engine == "bridge":
            from agent_bridge import main as bridge_main
            raise SystemExit(bridge_main(sys.argv[3:]))
        raise SystemExit(f"Unknown engine: {engine}")

    parser = argparse.ArgumentParser(description="Business Literature Radar local web app")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"商科文献雷达 / Business Literature Radar: {url}", flush=True)
    if not args.no_browser:
        threading.Timer(0.45, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
