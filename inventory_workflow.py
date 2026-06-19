"""5168 庫存修改自動化流程。"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from selenium import webdriver
from selenium.webdriver.common.by import By

from browser_actions import (
    click_text,
    click_xpath,
    close_other_tabs,
    hover_element,
    safe_click,
    switch_to_new_tab,
    visible_elements,
    wait_visible_xpath,
)
from popup_guard import dismiss_close_popup, dismiss_custom_xpaths

LogFn = Callable[[str], None]

_LOOP_INF_SAFETY_CAP = 5000

XPATH_MENU_TRIGGER = '//*[@id="app"]/div[2]/header/div/div[2]/ul[1]/li[3]/div[1]'
XPATH_MENU_ITEM = '//*[@id="app"]/div[2]/header/div/div[2]/ul[1]/li[3]/div[2]/ul/li[2]/a/span'
XPATH_PAGINATION_UL = (
    '//*[@id="app"]/div[3]/div/div/div[2]/div[4]/div/section[2]/section[2]/div[21]/ul'
)
XPATH_EDIT_LAST = "//*[contains(normalize-space(.), '\u4fee\u6539')]"
XPATH_BTN_COMPLETE = '//*[@id="app"]/div[3]/div/div[2]/div[2]/div[2]/div/div[11]/button[2]'
XPATH_BACK_INVENTORY = '//*[@id="app"]/div[3]/div/div/div/div[2]/div[3]/a[1]'

TEXT_ACK = "\u6211\u5df2\u8a73\u95b1\u4e26\u4e86\u89e3"
TEXT_COMPLETE = "\u5b8c\u6210"
TEXT_BACK = "\u8fd4\u56de\u5eab\u5b58"
TEXT_EDIT = "\u4fee\u6539"


@dataclass
class WorkflowResult:
    ok: bool
    message: str
    step: int = 0
    rounds: int = 0
    final_url: str = ""


def _check_stop(stop_check: Callable[[], bool] | None, step: int) -> None:
    if stop_check and stop_check():
        raise InterruptedError(f"使用者停止（步驟 {step}）")


def _click_pagination_last(
    driver: webdriver.Chrome,
    *,
    timeout_sec: float,
    log: LogFn,
) -> None:
    uls = wait_visible_xpath(
        driver, XPATH_PAGINATION_UL, timeout_sec=timeout_sec, log=log, label="頁數列"
    )
    ul = uls[0]
    candidates = []
    for el in ul.find_elements(By.XPATH, ".//li//a | .//a | .//li"):
        try:
            if not el.is_displayed():
                continue
            txt = (el.text or "").strip()
            if txt.isdigit():
                candidates.append((int(txt), el))
        except Exception:
            continue
    if not candidates:
        links = [e for e in ul.find_elements(By.XPATH, ".//a") if e.is_displayed()]
        if not links:
            raise RuntimeError("頁數列找不到可點擊頁碼")
        safe_click(driver, links[-1])
        log("已點擊頁數列最後一個連結。")
        return
    candidates.sort(key=lambda x: x[0])
    last_page, el = candidates[-1]
    safe_click(driver, el)
    log(f"已點擊最後一頁：第 {last_page} 頁")


def _click_last_edit(
    driver: webdriver.Chrome,
    *,
    timeout_sec: float,
    log: LogFn,
) -> set[str]:
    handles_before = set(driver.window_handles)
    els = wait_visible_xpath(
        driver, XPATH_EDIT_LAST, timeout_sec=timeout_sec, log=log, label=TEXT_EDIT
    )
    safe_click(driver, els[-1])
    log(f"已點擊最後一筆「{TEXT_EDIT}」。")
    return handles_before


def _run_steps_1_to_2(
    driver: webdriver.Chrome,
    *,
    wait: float,
    pause: float,
    stop_check: Callable[[], bool] | None,
    log: LogFn,
) -> None:
    _check_stop(stop_check, 1)
    log("步驟 1：尋找選單…")
    menu_els = wait_visible_xpath(
        driver, XPATH_MENU_TRIGGER, timeout_sec=wait, log=log, label="選單觸發"
    )
    hover_element(driver, menu_els[0])
    if pause:
        time.sleep(pause)

    _check_stop(stop_check, 2)
    log("步驟 2：點擊子選單…")
    try:
        click_xpath(driver, XPATH_MENU_ITEM, timeout_sec=wait, log=log, label="子選單項目")
    except (TimeoutError, IndexError):
        log("子選單未直接可見，改為點擊選單觸發點後重試…")
        safe_click(driver, menu_els[0])
        time.sleep(0.5)
        click_xpath(driver, XPATH_MENU_ITEM, timeout_sec=wait, log=log, label="子選單項目")
    if pause:
        time.sleep(pause)
    dismiss_close_popup(driver, log=log)


def _run_steps_3_to_7(
    driver: webdriver.Chrome,
    *,
    wait: float,
    pause: float,
    stop_check: Callable[[], bool] | None,
    log: LogFn,
    round_no: int,
) -> None:
    prefix = f"[第 {round_no} 輪] " if round_no > 1 else ""

    _check_stop(stop_check, 3)
    log(f"{prefix}步驟 3：點擊最後一頁…")
    _click_pagination_last(driver, timeout_sec=wait, log=log)
    if pause:
        time.sleep(pause)

    _check_stop(stop_check, 4)
    log(f"{prefix}步驟 4：點擊最後一筆修改…")
    handles_before = _click_last_edit(driver, timeout_sec=wait, log=log)
    try:
        keep = switch_to_new_tab(driver, handles_before, timeout_sec=wait, log=log)
    except TimeoutError:
        keep = driver.current_window_handle
        log("未偵測到新分頁，保留目前分頁繼續。")
    close_other_tabs(driver, keep, log=log)
    if pause:
        time.sleep(pause)
    dismiss_close_popup(driver, log=log)

    _check_stop(stop_check, 5)
    log(f"{prefix}步驟 5：點擊「我已詳閱並了解」…")
    try:
        click_text(driver, TEXT_ACK, timeout_sec=wait, log=log)
    except (TimeoutError, IndexError):
        log("以文字找不到，嘗試其他可見按鈕…")
        ack_els = visible_elements(
            driver, f"//*[contains(normalize-space(.), '{TEXT_ACK}')]"
        )
        if not ack_els:
            raise
        safe_click(driver, ack_els[0])
        log(f"已點擊：{TEXT_ACK}")
    if pause:
        time.sleep(pause)

    _check_stop(stop_check, 6)
    log(f"{prefix}步驟 6：點擊「完成」…")
    try:
        click_xpath(
            driver, XPATH_BTN_COMPLETE, timeout_sec=wait, log=log, label=TEXT_COMPLETE
        )
    except (TimeoutError, IndexError):
        click_text(driver, TEXT_COMPLETE, timeout_sec=wait, log=log)
    if pause:
        time.sleep(pause)

    _check_stop(stop_check, 7)
    log(f"{prefix}步驟 7：點擊「返回庫存」…")
    try:
        click_xpath(
            driver, XPATH_BACK_INVENTORY, timeout_sec=wait, log=log, label=TEXT_BACK
        )
    except (TimeoutError, IndexError):
        click_text(driver, TEXT_BACK, timeout_sec=wait, log=log)
    if pause:
        time.sleep(pause)
    dismiss_close_popup(driver, log=log)


def run_inventory_workflow(
    driver: webdriver.Chrome,
    *,
    element_wait_sec: float = 15.0,
    step_pause_sec: float = 0.8,
    loop_steps_3_7: bool = True,
    max_loop_rounds: int = 0,
    loop_popup_xpaths: list[str] | None = None,
    stop_check: Callable[[], bool] | None = None,
    log: LogFn | None = None,
) -> WorkflowResult:
    _log = log or (lambda _m: None)
    wait = float(element_wait_sec)
    pause = max(0.0, float(step_pause_sec))
    max_rounds = int(max_loop_rounds)
    if max_rounds < 0:
        max_rounds = 0
    popup_xpaths = list(loop_popup_xpaths or [])

    try:
        driver.switch_to.default_content()
        dismiss_close_popup(driver, log=_log)

        _run_steps_1_to_2(
            driver, wait=wait, pause=pause, stop_check=stop_check, log=_log
        )

        round_no = 1
        while True:
            _run_steps_3_to_7(
                driver,
                wait=wait,
                pause=pause,
                stop_check=stop_check,
                log=_log,
                round_no=round_no,
            )
            _log(f"第 {round_no} 輪（步驟 3～7）完成。")

            if not loop_steps_3_7:
                break
            if max_rounds > 0 and round_no >= max_rounds:
                _log(f"已達最大循環次數 {max_rounds}，停止。")
                break
            if round_no >= _LOOP_INF_SAFETY_CAP:
                _log(f"無限循環已達安全上限 {_LOOP_INF_SAFETY_CAP} 輪，停止。")
                break

            _check_stop(stop_check, 3)
            round_no += 1
            _log(f"返回步驟 3，開始第 {round_no} 輪…")
            if popup_xpaths:
                dismiss_custom_xpaths(driver, popup_xpaths, log=_log)
            time.sleep(max(pause, 0.3))

        if loop_steps_3_7 and round_no > 1:
            msg = f"流程完成，共 {round_no} 輪（步驟 3～7 循環）"
        else:
            msg = "流程完成"
        _log(msg)
        return WorkflowResult(
            ok=True,
            message=msg,
            step=7,
            rounds=round_no,
            final_url=driver.current_url or "",
        )
    except InterruptedError as exc:
        _log(str(exc))
        return WorkflowResult(ok=False, message=str(exc), final_url=driver.current_url or "")
    except Exception as exc:
        _log(f"流程失敗：{exc}")
        return WorkflowResult(
            ok=False,
            message=str(exc),
            final_url=driver.current_url or "",
        )
