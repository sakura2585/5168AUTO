"""應用程式狀態讀寫（JSON + UTF-8 + 原子寫入）。"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from paths import CHROME_PROFILE_DIR, DEFAULT_URL, STATE_PATH

SCHEMA_VERSION = 1

_DEFAULT_STATE: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "url": DEFAULT_URL,
    "chrome_profile_dir": str(CHROME_PROFILE_DIR),
    "window": {"width": 720, "height": 560, "x": None, "y": None},
    "headless": False,
    "login_wait_timeout_sec": 300.0,
    "login_poll_interval_sec": 2.0,
    "sms_wait_sec": 60.0,
    "element_wait_sec": 15.0,
    "step_pause_sec": 0.8,
    "run_workflow_after_login": True,
    "loop_steps_3_7": True,
    "max_loop_rounds": 0,
}


def _merge_defaults(raw: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(_DEFAULT_STATE)
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if key == "window" and isinstance(value, dict):
            win = out["window"]
            if isinstance(win, dict):
                win.update(value)
            continue
        out[key] = value
    out["schema_version"] = SCHEMA_VERSION
    return out


def load_state(path: Path | None = None) -> dict[str, Any]:
    p = path or STATE_PATH
    if not p.is_file():
        return deepcopy(_DEFAULT_STATE)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return deepcopy(_DEFAULT_STATE)
    if not isinstance(raw, dict):
        return deepcopy(_DEFAULT_STATE)
    return _merge_defaults(raw)


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    p = path or STATE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = _merge_defaults(state if isinstance(state, dict) else {})
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
