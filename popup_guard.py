"""開啟頁面後排除彈窗。"""
from __future__ import annotations

import time
from typing import Callable

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

LogFn = Callable[[str], None]

# 5168 常見公告彈窗「關閉」按鈕
XPATH_POPUP_CLOSE_PRIMARY = "/html/body/div[6]/div[2]/button[1]"
XPATH_POPUP_CLOSE_FALLBACK = "//button[normalize-space(.)='\u95dc\u9589']"
CLOSE_LABEL = "\u95dc\u9589"


def _noop_log(_msg: str) -> None:
    pass


def _element_text(el) -> str:
    try:
        return (el.text or "").strip()
    except WebDriverException:
        return ""


def _safe_click(driver: webdriver.Chrome, el) -> None:
    try:
        driver.execute_script(
            "try{arguments[0].scrollIntoView({block:'center',inline:'nearest'});}catch(e){}",
            el,
        )
    except Exception:
        pass
    time.sleep(0.1)
    try:
        el.click()
        return
    except WebDriverException:
        pass
    driver.execute_script("arguments[0].click();", el)


def dismiss_close_popup(
    driver: webdriver.Chrome,
    *,
    wait_sec: float = 3.0,
    log: LogFn = _noop_log,
) -> bool:
    """
    若存在「關閉」彈窗按鈕則點擊。
    優先使用 /html/body/div[6]/div[2]/button[1]，並確認文字含「關閉」。
    """
    driver.switch_to.default_content()
    deadline = time.monotonic() + max(0.5, float(wait_sec))
    xpaths = (XPATH_POPUP_CLOSE_PRIMARY, XPATH_POPUP_CLOSE_FALLBACK)

    while time.monotonic() < deadline:
        for xpath in xpaths:
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    if not el.is_displayed():
                        continue
                    text = _element_text(el)
                    if xpath == XPATH_POPUP_CLOSE_PRIMARY and CLOSE_LABEL not in text:
                        continue
                    _safe_click(driver, el)
                    log(f"已點擊彈窗「關閉」按鈕（{xpath}）。")
                    time.sleep(0.4)
                    return True
                except WebDriverException:
                    continue
        time.sleep(0.3)

    log("未偵測到「關閉」彈窗，略過。")
    return False


def dismiss_custom_xpaths(
    driver: webdriver.Chrome,
    xpaths: list[str],
    *,
    wait_sec: float = 3.0,
    log: LogFn = _noop_log,
) -> int:
    """依 UI 設定的 XPath 嘗試關閉彈窗；回傳點擊次數。"""
    cleaned = [x.strip() for x in xpaths if isinstance(x, str) and x.strip()]
    if not cleaned:
        log("（循環彈窗）未設定 XPath，略過。")
        return 0

    driver.switch_to.default_content()
    clicks = 0
    deadline = time.monotonic() + max(0.5, float(wait_sec))
    while time.monotonic() < deadline:
        found_any = False
        for xpath in cleaned:
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    if not el.is_displayed():
                        continue
                    _safe_click(driver, el)
                    clicks += 1
                    found_any = True
                    log(f"（循環彈窗）已點擊：{xpath}")
                    time.sleep(0.4)
                    break
                except WebDriverException:
                    continue
            if found_any:
                break
        if not found_any:
            break
        time.sleep(0.3)

    if clicks == 0:
        log("（循環彈窗）未偵測到可點擊元素。")
    else:
        log(f"（循環彈窗）共關閉 {clicks} 個。")
    return clicks


def navigate_and_dismiss(
    driver: webdriver.Chrome,
    url: str,
    *,
    settle_sec: float = 1.5,
    popup_wait_sec: float = 3.0,
    log: LogFn = _noop_log,
) -> None:
    """開啟網址並嘗試關閉彈窗。"""
    driver.get(url)
    time.sleep(max(0.5, float(settle_sec)))
    dismiss_close_popup(driver, wait_sec=popup_wait_sec, log=log)
