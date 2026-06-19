"""Chrome + Selenium Manager（自動配對 ChromeDriver）。"""
from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def build_driver(
    *,
    headless: bool = False,
    user_data_dir: str | Path | None = None,
    detach: bool = True,
) -> webdriver.Chrome:
    """
    user_data_dir：Chrome Profile，用於保存 Cookie／登入 Session。
    detach=True：腳本結束後保留 Chrome 視窗（方便手動完成簡訊驗證）。
    """
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    if detach:
        opts.add_experimental_option("detach", True)
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    if user_data_dir:
        p = Path(user_data_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        opts.add_argument(f"--user-data-dir={p}")
    driver = webdriver.Chrome(service=Service(), options=opts)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
            },
        )
    except Exception:
        pass
    return driver


def safe_quit(driver: webdriver.Chrome | None) -> None:
    if driver is None:
        return
    try:
        driver.quit()
    except Exception:
        pass
