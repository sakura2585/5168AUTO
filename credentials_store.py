"""本機登入資訊儲存（5168 為手機＋簡訊驗證，不儲存驗證碼）。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from paths import CREDENTIALS_PATH

_EMPTY: dict[str, Any] = {
    "phone": "",
    "remember_phone": False,
}


def load_credentials(path: Path | None = None) -> dict[str, Any]:
    p = path or CREDENTIALS_PATH
    if not p.is_file():
        return deepcopy(_EMPTY)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return deepcopy(_EMPTY)
    if not isinstance(raw, dict):
        return deepcopy(_EMPTY)
    return {
        "phone": str(raw.get("phone", "")).strip(),
        "remember_phone": bool(raw.get("remember_phone", False)),
    }


def save_credentials(phone: str, remember_phone: bool, path: Path | None = None) -> None:
    p = path or CREDENTIALS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phone": (phone or "").strip(),
        "remember_phone": bool(remember_phone),
    }
    if not payload["remember_phone"]:
        payload["phone"] = ""
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def mask_phone(phone: str) -> str:
    p = (phone or "").strip()
    if len(p) <= 4:
        return "***" if p else "(未設定)"
    return f"{p[:3]}****{p[-2:]}"
