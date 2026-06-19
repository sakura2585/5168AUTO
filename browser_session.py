"""共用 Chrome WebDriver 連線（避免重複開啟 Profile）。"""
from __future__ import annotations

from selenium import webdriver

_driver: webdriver.Chrome | None = None


def set_driver(driver: webdriver.Chrome | None) -> None:
    global _driver
    _driver = driver


def get_driver() -> webdriver.Chrome | None:
    return _driver


def is_driver_alive(driver: webdriver.Chrome | None) -> bool:
    if driver is None:
        return False
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def get_or_clear() -> webdriver.Chrome | None:
    global _driver
    if is_driver_alive(_driver):
        return _driver
    _driver = None
    return None
