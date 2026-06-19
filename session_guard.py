"""5168 登入狀態偵測與 Session 維護。"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from paths import DEFAULT_URL, LOGIN_URL
from popup_guard import dismiss_close_popup, navigate_and_dismiss

LogFn = Callable[[str], None]

# 5168 首頁未登入時，頂部會有「登入 / 註冊」連到 member.houseprice.tw
XPATH_LOGIN_ENTRY = (
    "//a[contains(@href,'member.houseprice.tw/agent') and contains(normalize-space(.), '\u767b\u5165')]"
)
# 已登入時常見後台連結
XPATH_LOGGED_IN_HINTS = (
    "//a[contains(@href,'/dashboard')]"
    " | //a[contains(@href,'/inventory/') and contains(@href,'published')]"
    " | //a[contains(normalize-space(.), '\u6211\u7684\u8cb7\u65b9')]"
    " | //a[contains(normalize-space(.), '\u6211\u7684\u5eab\u5b58')]"
)
XPATH_PHONE_INPUT = "//input[@type='tel']"
XPATH_SEND_CODE = "//a[contains(normalize-space(.), '\u767c\u9001\u9a57\u8b49\u78bc') or contains(normalize-space(.), '\u767c\u9001')]"
XPATH_VERIFY_CODE_INPUT = "//input[@type='text' and contains(@placeholder, '\u9a57\u8b49')]"
XPATH_SUBMIT_LOGIN = "//input[@type='submit'] | //button[@type='submit']"


class LoginStatus(str, Enum):
    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    UNKNOWN = "unknown"


@dataclass
class LoginResult:
    ok: bool
    status: LoginStatus
    message: str
    final_url: str = ""


def _noop_log(_msg: str) -> None:
    pass


def _visible_elements(driver: webdriver.Chrome, xpath: str) -> list:
    out = []
    for el in driver.find_elements(By.XPATH, xpath):
        try:
            if el.is_displayed():
                out.append(el)
        except WebDriverException:
            continue
    return out


def detect_login_status(driver: webdriver.Chrome, *, url: str = DEFAULT_URL) -> LoginStatus:
    """在指定網址判斷是否已登入。"""
    try:
        if not (driver.current_url or "").startswith("https://007.houseprice.tw"):
            navigate_and_dismiss(driver, url, log=_noop_log)
        else:
            dismiss_close_popup(driver, log=_noop_log)
        if _visible_elements(driver, XPATH_LOGIN_ENTRY):
            return LoginStatus.NOT_LOGGED_IN
        if _visible_elements(driver, XPATH_LOGGED_IN_HINTS):
            return LoginStatus.LOGGED_IN
        # member 網域通常代表仍在登入流程
        if "member.houseprice.tw" in (driver.current_url or ""):
            return LoginStatus.NOT_LOGGED_IN
        return LoginStatus.UNKNOWN
    except WebDriverException:
        return LoginStatus.UNKNOWN


def prefill_phone_on_login_page(driver: webdriver.Chrome, phone: str, log: LogFn = _noop_log) -> bool:
    """在 member 登入頁預填手機號碼（簡訊驗證碼仍需使用者手動輸入）。"""
    phone = (phone or "").strip()
    if not phone:
        return False
    try:
        driver.switch_to.default_content()
        inputs = _visible_elements(driver, XPATH_PHONE_INPUT)
        if not inputs:
            return False
        el = inputs[0]
        el.clear()
        el.send_keys(phone)
        log(f"已預填手機號碼：{phone[:3]}****{phone[-2:] if len(phone) > 4 else ''}")
        return True
    except WebDriverException as exc:
        log(f"預填手機失敗：{exc}")
        return False


def _interruptible_countdown(
    total_sec: float,
    *,
    poll_interval_sec: float = 1.0,
    stop_check: Callable[[], bool] | None = None,
    log: LogFn = _noop_log,
    prefix: str = "等待驗證碼簡訊",
) -> bool:
    """倒數等待；回傳 True=等完，False=被停止。"""
    total = max(0.0, float(total_sec))
    if total <= 0:
        return True
    log(f"{prefix}，預計等待 {int(total)} 秒…")
    deadline = time.monotonic() + total
    poll = max(0.2, float(poll_interval_sec))
    last_logged = -1
    while time.monotonic() < deadline:
        if stop_check and stop_check():
            log("已取消等待驗證碼。")
            return False
        remaining = int(deadline - time.monotonic())
        if remaining != last_logged and (remaining <= 10 or remaining % 10 == 0):
            log(f"{prefix}… 剩餘 {remaining} 秒")
            last_logged = remaining
        time.sleep(min(poll, max(0.05, deadline - time.monotonic())))
    log(f"{prefix}完成，請在 Chrome 輸入驗證碼。")
    return True


def trigger_sms_send(driver: webdriver.Chrome, log: LogFn = _noop_log) -> bool:
    """嘗試觸發發送驗證碼（找不到時改由使用者手動操作）。"""
    driver.switch_to.default_content()
    candidates = [
        XPATH_SEND_CODE,
        "//a[contains(normalize-space(.), '\u9a57\u8b49\u78bc')]",
        "//button[contains(normalize-space(.), '\u9a57\u8b49')]",
        "//*[contains(normalize-space(.), '\u53d6\u5f97\u9a57\u8b49\u78bc')]",
        "//*[contains(normalize-space(.), '\u767c\u9001\u9a57\u8b49\u78bc')]",
    ]
    for xpath in candidates:
        for el in _visible_elements(driver, xpath):
            try:
                el.click()
                time.sleep(0.8)
                log("已點擊發送／取得驗證碼。")
                return True
            except WebDriverException:
                continue
    # 輸入電話後按 Enter，部分頁面會切換到驗證碼步驟
    for el in _visible_elements(driver, XPATH_PHONE_INPUT):
        try:
            el.send_keys("\n")
            time.sleep(0.8)
            log("已在手機欄送出 Enter（若網站支援會進入驗證碼步驟）。")
            return True
        except WebDriverException:
            continue
    log("未自動找到發送驗證碼按鈕；請在 Chrome 手動點擊「發送驗證碼」。")
    return False


def wait_for_verify_code_input(
    driver: webdriver.Chrome,
    *,
    timeout_sec: float = 15.0,
    log: LogFn = _noop_log,
) -> bool:
    """等待驗證碼輸入欄出現（選填，僅用於日誌提示）。"""
    deadline = time.monotonic() + max(1.0, float(timeout_sec))
    while time.monotonic() < deadline:
        if _visible_elements(driver, XPATH_VERIFY_CODE_INPUT):
            log("驗證碼輸入欄已出現，請輸入簡訊驗證碼。")
            return True
        time.sleep(0.5)
    return False


def open_login_page(
    driver: webdriver.Chrome,
    *,
    phone: str = "",
    login_url: str = LOGIN_URL,
    sms_wait_sec: float = 60.0,
    poll_interval_sec: float = 2.0,
    stop_check: Callable[[], bool] | None = None,
    log: LogFn = _noop_log,
) -> bool:
    log(f"前往登入頁：{login_url}")
    navigate_and_dismiss(driver, login_url, log=log)
    if prefill_phone_on_login_page(driver, phone, log=log):
        trigger_sms_send(driver, log=log)
        wait_for_verify_code_input(driver, log=log)
        if not _interruptible_countdown(
            sms_wait_sec,
            poll_interval_sec=min(1.0, poll_interval_sec),
            stop_check=stop_check,
            log=log,
            prefix="等待驗證碼簡訊回傳",
        ):
            return False
    else:
        log("未預填手機；請在 Chrome 手動輸入電話並取得驗證碼。")
    log("請在 Chrome 視窗輸入驗證碼完成登入；Session 會寫入 Chrome Profile。")
    return True


def wait_until_logged_in(
    driver: webdriver.Chrome,
    *,
    timeout_sec: float = 300.0,
    poll_interval_sec: float = 2.0,
    home_url: str = DEFAULT_URL,
    stop_check: Callable[[], bool] | None = None,
    log: LogFn = _noop_log,
) -> LoginResult:
    """輪詢直到登入成功、逾時或外部停止。"""
    deadline = time.monotonic() + max(5.0, float(timeout_sec))
    poll = max(0.5, float(poll_interval_sec))
    last_status = LoginStatus.UNKNOWN

    while time.monotonic() < deadline:
        if stop_check and stop_check():
            return LoginResult(
                ok=False,
                status=last_status,
                message="已取消等待登入。",
                final_url=driver.current_url or "",
            )
        last_status = detect_login_status(driver, url=home_url)
        if last_status == LoginStatus.LOGGED_IN:
            log("登入成功，Session 已就緒。")
            return LoginResult(
                ok=True,
                status=LoginStatus.LOGGED_IN,
                message="已登入。",
                final_url=driver.current_url or "",
            )
        if last_status == LoginStatus.NOT_LOGGED_IN:
            # 若使用者仍在 member 頁操作，不強制跳轉
            if "member.houseprice.tw" not in (driver.current_url or ""):
                try:
                    navigate_and_dismiss(driver, home_url, log=log)
                except WebDriverException:
                    pass
        time.sleep(poll)

    return LoginResult(
        ok=False,
        status=last_status,
        message=f"等待登入逾時（{int(timeout_sec)} 秒）。請在瀏覽器完成簡訊驗證後再試。",
        final_url=driver.current_url or "",
    )


def ensure_logged_in(
    driver: webdriver.Chrome,
    *,
    phone: str = "",
    home_url: str = DEFAULT_URL,
    login_url: str = LOGIN_URL,
    wait_timeout_sec: float = 300.0,
    poll_interval_sec: float = 2.0,
    sms_wait_sec: float = 60.0,
    stop_check: Callable[[], bool] | None = None,
    log: LogFn = _noop_log,
) -> LoginResult:
    """確保已登入：已登入則直接成功，否則開登入頁並等待手動驗證。"""
    status = detect_login_status(driver, url=home_url)
    if status == LoginStatus.LOGGED_IN:
        log("偵測到已登入（Chrome Profile Session 有效）。")
        return LoginResult(
            ok=True,
            status=LoginStatus.LOGGED_IN,
            message="已登入。",
            final_url=driver.current_url or "",
        )

    log("尚未登入，將開啟登入頁並等待您完成簡訊驗證。")
    if not open_login_page(
        driver,
        phone=phone,
        login_url=login_url,
        sms_wait_sec=sms_wait_sec,
        poll_interval_sec=poll_interval_sec,
        stop_check=stop_check,
        log=log,
    ):
        return LoginResult(
            ok=False,
            status=LoginStatus.NOT_LOGGED_IN,
            message="已取消等待驗證碼。",
            final_url=driver.current_url or "",
        )
    return wait_until_logged_in(
        driver,
        timeout_sec=wait_timeout_sec,
        poll_interval_sec=poll_interval_sec,
        home_url=home_url,
        stop_check=stop_check,
        log=log,
    )


def check_login_only(driver: webdriver.Chrome, *, home_url: str = DEFAULT_URL, log: LogFn = _noop_log) -> LoginResult:
    status = detect_login_status(driver, url=home_url)
    if status == LoginStatus.LOGGED_IN:
        msg = "已登入。"
        ok = True
    elif status == LoginStatus.NOT_LOGGED_IN:
        msg = "未登入：請按「開啟瀏覽器登入」完成簡訊驗證。"
        ok = False
    else:
        msg = "無法判斷登入狀態，請手動確認或重新登入。"
        ok = False
    log(msg)
    return LoginResult(ok=ok, status=status, message=msg, final_url=driver.current_url or "")


def wait_for_page_ready(driver: webdriver.Chrome, timeout_sec: float = 20.0) -> None:
    WebDriverWait(driver, timeout_sec).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
