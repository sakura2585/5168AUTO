"""專案路徑集中定義。"""
from __future__ import annotations

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
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
