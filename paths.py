"""專案路徑集中定義。"""
from __future__ import annotations

import sys
from pathlib import Path


def _resolve_app_dir() -> Path:
    """開發模式用原始碼目錄；PyInstaller 打包後用 exe 所在資料夾。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = _resolve_app_dir()
DATA_DIR = APP_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"
CREDENTIALS_PATH = DATA_DIR / "credentials.json"
CHROME_PROFILE_DIR = DATA_DIR / "chrome_profile"
DEBUG_DIR = DATA_DIR / "debug"

DEFAULT_URL = "https://007.houseprice.tw/"
LOGIN_URL = (
    "https://member.houseprice.tw/agent"
    "?fromhp=https%3A%2F%2F007.houseprice.tw%2Finventory%2Fpublished"
)
