"""瀏覽器通用操作（點擊、等待、分頁）。"""
from __future__ import annotations

import time
from typing import Callable

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

LogFn = Callable[[str], None]


def _noop_log(_msg: str) -> None:
    pass


def visible_elements(driver: webdriver.Chrome, xpath: str) -> list:
    out = []
    for el in driver.find_elements(By.XPATH, xpath):
        try:
            if el.is_displayed():
                out.append(el)
        except WebDriverException:
            continue
    return out


def element_text(el) -> str:
    try:
        return (el.text or "").strip()
    except WebDriverException:
        return ""


def safe_click(driver: webdriver.Chrome, el) -> None:
    try:
        driver.execute_script(
            "try{arguments[0].scrollIntoView({block:'center',inline:'nearest'});}catch(e){}",
            el,
        )
    except Exception:
        pass
    time.sleep(0.1)
    try:
        driver.execute_script(
            "try{var n=arguments[0]; if(n&&n.focus) n.focus();}catch(e){}",
            el,
        )
    except Exception:
        pass
    last_err: BaseException | None = None
    for _ in range(2):
        try:
            el.click()
            return
        except StaleElementReferenceException:
            raise
        except Exception as exc:
            last_err = exc
            time.sleep(0.12)
    try:
        ActionChains(driver).move_to_element(el).pause(0.08).click().perform()
        return
    except Exception as exc:
        last_err = exc
    try:
        driver.execute_script("arguments[0].click();", el)
        return
    except Exception as exc:
        last_err = exc
    if last_err is not None:
        raise last_err
    raise RuntimeError("click failed")


def hover_element(driver: webdriver.Chrome, el) -> None:
    driver.execute_script(
        "try{arguments[0].scrollIntoView({block:'center',inline:'nearest'});}catch(e){}",
        el,
    )
    ActionChains(driver).move_to_element(el).pause(0.25).perform()


def wait_visible_xpath(
    driver: webdriver.Chrome,
    xpath: str,
    *,
    timeout_sec: float = 15.0,
    log: LogFn = _noop_log,
    label: str = "",
) -> list:
    deadline = time.monotonic() + max(1.0, float(timeout_sec))
    name = label or xpath
    while time.monotonic() < deadline:
        els = visible_elements(driver, xpath)
        if els:
            log(f"已找到：{name}（{len(els)} 個可見）")
            return els
        time.sleep(0.3)
    raise TimeoutError(f"逾時找不到元素：{name}")


def click_xpath(
    driver: webdriver.Chrome,
    xpath: str,
    *,
    timeout_sec: float = 15.0,
    log: LogFn = _noop_log,
    label: str = "",
    index: int = 0,
) -> None:
    name = label or xpath
    els = wait_visible_xpath(driver, xpath, timeout_sec=timeout_sec, log=log, label=name)
    idx = index if index >= 0 else len(els) + index
    if idx < 0 or idx >= len(els):
        raise IndexError(f"元素索引超出範圍：{name} index={index}")
    safe_click(driver, els[idx])
    log(f"已點擊：{name}")


def click_text(
    driver: webdriver.Chrome,
    text: str,
    *,
    timeout_sec: float = 15.0,
    log: LogFn = _noop_log,
    index: int = -1,
    tag: str = "*",
) -> None:
    xpath = f"//{tag}[contains(normalize-space(.), '{text}')]"
    els = wait_visible_xpath(driver, xpath, timeout_sec=timeout_sec, log=log, label=text)
    idx = index if index >= 0 else len(els) + index
    safe_click(driver, els[idx])
    log(f"已點擊文字：{text}")


def close_other_tabs(driver: webdriver.Chrome, keep_handle: str, log: LogFn = _noop_log) -> None:
    closed = 0
    for handle in list(driver.window_handles):
        if handle == keep_handle:
            continue
        driver.switch_to.window(handle)
        driver.close()
        closed += 1
    driver.switch_to.window(keep_handle)
    if closed:
        log(f"已關閉 {closed} 個其他分頁，保留目前分頁。")


def switch_to_new_tab(
    driver: webdriver.Chrome,
    handles_before: set[str],
    *,
    timeout_sec: float = 15.0,
    log: LogFn = _noop_log,
) -> str:
    deadline = time.monotonic() + max(1.0, float(timeout_sec))

    def _new_handle(drv: webdriver.Chrome) -> str | bool:
        new_on = set(drv.window_handles) - handles_before
        if new_on:
            return next(iter(new_on))
        if len(drv.window_handles) > len(handles_before):
            return drv.window_handles[-1]
        return False

    handle = WebDriverWait(driver, max(1.0, float(timeout_sec))).until(_new_handle)
    if not isinstance(handle, str):
        raise TimeoutError("等待新分頁開啟逾時")
    driver.switch_to.window(handle)
    log(f"已切換至新分頁：{driver.current_url}")
    return handle
