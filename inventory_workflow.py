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
from session_guard import LoginStatus, detect_login_status, wait_for_page_ready

LogFn = Callable[[str], None]

_LOOP_INF_SAFETY_CAP = 5000
_DEFAULT_MAX_RECOVERY_PER_ROUND = 3
_DEFAULT_MAX_RECOVERY_TOTAL = 30

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


class WorkflowStepError(Exception):
    """流程步驟失敗（含步驟編號，供恢復邏輯使用）。"""

    def __init__(self, step: int, message: str) -> None:
        self.step = step
        super().__init__(message)


@dataclass
class WorkflowResult:
    ok: bool
    message: str
    step: int = 0
    rounds: int = 0
    recoveries: int = 0
    final_url: str = ""


def _check_stop(stop_check: Callable[[], bool] | None, step: int) -> None:
    if stop_check and stop_check():
        raise InterruptedError(f"使用者停止（步驟 {step}）")


def _wrap_step(step: int, fn: Callable[[], None]) -> None:
    try:
        fn()
    except InterruptedError:
        raise
    except WorkflowStepError:
        raise
    except Exception as exc:
        raise WorkflowStepError(step, str(exc)) from exc


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

    def _step1() -> None:
        menu_els = wait_visible_xpath(
            driver, XPATH_MENU_TRIGGER, timeout_sec=wait, log=log, label="選單觸發"
        )
        hover_element(driver, menu_els[0])
        if pause:
            time.sleep(pause)

    _wrap_step(1, _step1)

    _check_stop(stop_check, 2)
    log("步驟 2：點擊子選單…")

    def _step2() -> None:
        menu_els = wait_visible_xpath(
            driver, XPATH_MENU_TRIGGER, timeout_sec=wait, log=log, label="選單觸發"
        )
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

    _wrap_step(2, _step2)


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
    _wrap_step(3, lambda: _click_pagination_last(driver, timeout_sec=wait, log=log))
    if pause:
        time.sleep(pause)

    _check_stop(stop_check, 4)
    log(f"{prefix}步驟 4：點擊最後一筆修改…")

    def _step4() -> None:
        handles_before = _click_last_edit(driver, timeout_sec=wait, log=log)
        try:
            keep = switch_to_new_tab(driver, handles_before, timeout_sec=wait, log=log)
        except TimeoutError:
            keep = driver.current_window_handle
            log("未偵測到新分頁，保留目前分頁繼續。")
        close_other_tabs(driver, keep, log=log)

    _wrap_step(4, _step4)
    if pause:
        time.sleep(pause)
    dismiss_close_popup(driver, log=log)

    _check_stop(stop_check, 5)
    log(f"{prefix}步驟 5：點擊「我已詳閱並了解」…")

    def _step5() -> None:
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

    _wrap_step(5, _step5)
    if pause:
        time.sleep(pause)

    _check_stop(stop_check, 6)
    log(f"{prefix}步驟 6：點擊「完成」…")

    def _step6() -> None:
        try:
            click_xpath(
                driver, XPATH_BTN_COMPLETE, timeout_sec=wait, log=log, label=TEXT_COMPLETE
            )
        except (TimeoutError, IndexError):
            click_text(driver, TEXT_COMPLETE, timeout_sec=wait, log=log)

    _wrap_step(6, _step6)
    if pause:
        time.sleep(pause)
    dismiss_close_popup(driver, log=log)

    _check_stop(stop_check, 7)
    log(f"{prefix}步驟 7：點擊「返回庫存」…")

    def _step7() -> None:
        current = (driver.current_url or "").lower()
        if "inventory-edit" not in current:
            log("已在庫存列表（非編輯頁），略過「返回庫存」。")
            return
        try:
            click_xpath(
                driver, XPATH_BACK_INVENTORY, timeout_sec=wait, log=log, label=TEXT_BACK
            )
        except (TimeoutError, IndexError):
            click_text(driver, TEXT_BACK, timeout_sec=wait, log=log)

    _wrap_step(7, _step7)
    if pause:
        time.sleep(pause)
    dismiss_close_popup(driver, log=log)


def _reset_to_anchor(
    driver: webdriver.Chrome,
    anchor_url: str,
    *,
    wait: float,
    pause: float,
    stop_check: Callable[[], bool] | None,
    popup_xpaths: list[str],
    log: LogFn,
) -> None:
    _check_stop(stop_check, 0)
    status = detect_login_status(driver)
    if status == LoginStatus.NOT_LOGGED_IN:
        raise RuntimeError("登入已失效，請重新登入後再執行流程。")
    if not anchor_url:
        raise RuntimeError("無法恢復：未記錄步驟 1 起點網址。")

    driver.switch_to.default_content()
    handles = list(driver.window_handles)
    if len(handles) > 1:
        keep = handles[0]
        close_other_tabs(driver, keep, log=log)

    log(f"[恢復] 回到起點網址：{anchor_url}")
    driver.get(anchor_url)
    ready_timeout = min(max(wait, 5.0), 30.0)
    try:
        wait_for_page_ready(driver, timeout_sec=ready_timeout)
    except Exception:
        pass
    driver.refresh()
    time.sleep(max(pause, 0.5))
    try:
        wait_for_page_ready(driver, timeout_sec=ready_timeout)
    except Exception:
        pass
    dismiss_close_popup(driver, log=log)
    if popup_xpaths:
        dismiss_custom_xpaths(driver, popup_xpaths, log=log)


def run_inventory_workflow(
    driver: webdriver.Chrome,
    *,
    element_wait_sec: float = 15.0,
    step_pause_sec: float = 0.8,
    loop_steps_3_7: bool = True,
    max_loop_rounds: int = 0,
    loop_popup_xpaths: list[str] | None = None,
    max_recovery_per_round: int = _DEFAULT_MAX_RECOVERY_PER_ROUND,
    max_recovery_total: int = _DEFAULT_MAX_RECOVERY_TOTAL,
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
    recovery_per_round = max(1, int(max_recovery_per_round))
    recovery_total_cap = max(1, int(max_recovery_total))

    total_recoveries = 0
    round_recoveries = 0
    last_failed_step = 0

    def _recover_from_error(*, failed_step: int, reason: str, round_no: int) -> None:
        nonlocal total_recoveries, round_recoveries, last_failed_step
        last_failed_step = failed_step
        if total_recoveries >= recovery_total_cap:
            raise RuntimeError(
                f"恢復次數已達上限（{recovery_total_cap} 次），停止流程。"
                f"最後失敗：步驟 {failed_step} — {reason}"
            )
        if round_recoveries >= recovery_per_round:
            raise RuntimeError(
                f"本輪恢復次數已達上限（{recovery_per_round} 次），停止流程。"
                f"最後失敗：步驟 {failed_step} — {reason}"
            )

        total_recoveries += 1
        round_recoveries += 1
        round_label = f"第 {round_no} 輪" if round_no > 0 else "初始"
        _log(
            f"[恢復 {total_recoveries}/{recovery_total_cap}] "
            f"{round_label} 步驟 {failed_step} 失敗：{reason}"
        )
        _log(
            f"[恢復] 本輪第 {round_recoveries}/{recovery_per_round} 次，"
            "回到起點網址並刷新…"
        )
        _reset_to_anchor(
            driver,
            anchor_url,
            wait=wait,
            pause=pause,
            stop_check=stop_check,
            popup_xpaths=popup_xpaths,
            log=_log,
        )

    def _run_steps_1_to_2_with_recovery() -> None:
        while True:
            try:
                _run_steps_1_to_2(
                    driver, wait=wait, pause=pause, stop_check=stop_check, log=_log
                )
                return
            except InterruptedError:
                raise
            except WorkflowStepError as exc:
                _recover_from_error(failed_step=exc.step, reason=str(exc), round_no=0)
            except Exception as exc:
                _recover_from_error(failed_step=1, reason=str(exc), round_no=0)

    try:
        driver.switch_to.default_content()
        dismiss_close_popup(driver, log=_log)

        anchor_url = (driver.current_url or "").strip()
        _log(f"已記錄步驟 1 起點網址：{anchor_url or '（空）'}")

        _run_steps_1_to_2_with_recovery()

        round_no = 1
        while True:
            try:
                _run_steps_3_to_7(
                    driver,
                    wait=wait,
                    pause=pause,
                    stop_check=stop_check,
                    log=_log,
                    round_no=round_no,
                )
            except InterruptedError:
                raise
            except WorkflowStepError as exc:
                _recover_from_error(
                    failed_step=exc.step, reason=str(exc), round_no=round_no
                )
                _log("[恢復] 重跑步驟 1～2…")
                _run_steps_1_to_2_with_recovery()
                continue
            except Exception as exc:
                _recover_from_error(
                    failed_step=last_failed_step or 3, reason=str(exc), round_no=round_no
                )
                _log("[恢復] 重跑步驟 1～2…")
                _run_steps_1_to_2_with_recovery()
                continue

            round_recoveries = 0
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
        if total_recoveries > 0:
            msg += f"，期間自動恢復 {total_recoveries} 次"
        _log(msg)
        return WorkflowResult(
            ok=True,
            message=msg,
            step=7,
            rounds=round_no,
            recoveries=total_recoveries,
            final_url=driver.current_url or "",
        )
    except InterruptedError as exc:
        _log(str(exc))
        return WorkflowResult(
            ok=False,
            message=str(exc),
            step=last_failed_step,
            recoveries=total_recoveries,
            final_url=driver.current_url or "",
        )
    except Exception as exc:
        _log(f"流程失敗：{exc}")
        return WorkflowResult(
            ok=False,
            message=str(exc),
            step=last_failed_step,
            recoveries=total_recoveries,
            final_url=driver.current_url or "",
        )
