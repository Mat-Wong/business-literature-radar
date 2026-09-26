"""Per-user settings for the public product, isolated from personal editions."""

from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from typing import Any


APP_NAME = "BusinessLiteratureRadar"
DEFAULT_SETTINGS: dict[str, Any] = {
    "version": 1,
    "provider": "openai",
    "llm_backend": "rules",
    "endpoint": "",
    "models": "",
    "api_key": "",
    "disciplines": ["is", "qm"],
    "configured": False,
}

PROVIDER_PRESETS = {
    "rules": {
        "label": "不使用 LLM（规则模式）",
        "endpoint": "",
        "models": "",
        "key_hint": "无需 API Key",
    },
    "openai": {
        "label": "OpenAI API",
        "endpoint": "https://api.openai.com/v1/responses",
        "models": "gpt-6-luna,gpt-6-sol",
        "key_hint": "sk-...",
    },
    "anthropic": {
        "label": "Anthropic Claude API",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "models": "claude-haiku-4-5-20251001,claude-sonnet-5",
        "key_hint": "sk-ant-...",
    },
    "openai_compatible": {
        "label": "其他 OpenAI 兼容 API",
        "endpoint": "",
        "models": "",
        "key_hint": "填写服务商提供的 API Key",
    },
    "opencode": {
        "label": "OpenCode CLI（使用本机登录）",
        "endpoint": "",
        "models": "auto",
        "key_hint": "无需在此填写 Key",
    },
    "codex_cli": {
        "label": "OpenAI Codex CLI（使用本机登录）",
        "endpoint": "",
        "models": "auto",
        "key_hint": "需要已安装并登录 codex 命令",
    },
    "gemini_cli": {
        "label": "Google Gemini CLI（使用本机登录）",
        "endpoint": "",
        "models": "auto",
        "key_hint": "需要已安装并登录 gemini 命令",
    },
}


def settings_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_NAME / "settings.json"


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DataBlob, Any]:
    buffer = ctypes.create_string_buffer(data)
    return DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect_secret(secret: str) -> str:
    if not secret:
        return ""
    raw = secret.encode("utf-8")
    if os.name != "nt":
        return "plain:" + base64.b64encode(raw).decode("ascii")
    input_blob, input_buffer = _blob(raw)
    output_blob = DataBlob()
    protected_ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "Literature Search API Key",
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    if not protected_ok:
        # Some managed or portable Windows environments disable DPAPI. Saving
        # locally is still preferable to making the user configure credentials
        # on every launch; this format is also used on non-Windows systems.
        return "plain:" + base64.b64encode(raw).decode("ascii")
    try:
        protected = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return "dpapi:" + base64.b64encode(protected).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def unprotect_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("plain:"):
        return base64.b64decode(value[6:]).decode("utf-8")
    if not value.startswith("dpapi:") or os.name != "nt":
        return ""
    protected = base64.b64decode(value[6:])
    input_blob, input_buffer = _blob(protected)
    output_blob = DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def load_settings() -> dict[str, Any]:
    result = dict(DEFAULT_SETTINGS)
    path = settings_path()
    if not path.exists():
        return result
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            result.update({key: value for key, value in stored.items() if key != "api_key"})
            result["api_key"] = unprotect_secret(str(stored.get("api_key_protected", "")))
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)
    return result


def save_settings(settings: dict[str, Any]) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "provider": str(settings.get("provider", "rules")),
        "llm_backend": str(settings.get("llm_backend", "rules")),
        "endpoint": str(settings.get("endpoint", "")),
        "models": str(settings.get("models", "")),
        "disciplines": list(settings.get("disciplines") or ["is", "qm"]),
        "configured": True,
        "api_key_protected": protect_secret(str(settings.get("api_key", ""))),
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)
    if os.name != "nt":
        path.chmod(0o600)
    return path


def masked_key(key: str) -> str:
    if not key:
        return "未配置"
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:3]}••••••{key[-4:]}"
