"""登入相關背景工作（不阻塞 UI）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from browser_core import build_driver
from browser_session import get_or_clear, set_driver
from popup_guard import dismiss_close_popup, navigate_and_dismiss
from session_guard import LoginResult, LoginStatus, check_login_only, ensure_logged_in
from inventory_workflow import run_inventory_workflow


class LoginWorker(QObject):
    log_line = Signal(str)
    finished = Signal(object)  # LoginResult

    def __init__(self) -> None:
        super().__init__()
        self._stop = False
        self._driver = None
        self._params: dict[str, Any] = {}

    def configure(self, **params: Any) -> None:
        self._params = dict(params)
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def _stopped(self) -> bool:
        return self._stop

    def _log(self, msg: str) -> None:
        self.log_line.emit(msg)

    def run_check(self) -> None:
        def _do(driver) -> LoginResult:
            result = check_login_only(
                driver,
                home_url=str(self._params.get("home_url", "")),
                log=self._log,
            )
            if result.ok and result.status == LoginStatus.LOGGED_IN:
                return self._maybe_run_workflow(driver, result)
            return result

        result = self._with_driver(_do)
        self.finished.emit(result)

    def run_ensure_login(self) -> None:
        result = self._with_driver(self._ensure)
        self.finished.emit(result)

    def _ensure(self, driver) -> LoginResult:
        result = ensure_logged_in(
            driver,
            phone=str(self._params.get("phone", "")),
            home_url=str(self._params.get("home_url", "")),
            login_url=str(self._params.get("login_url", "")),
            wait_timeout_sec=float(self._params.get("wait_timeout_sec", 300)),
            poll_interval_sec=float(self._params.get("poll_interval_sec", 2)),
            sms_wait_sec=float(self._params.get("sms_wait_sec", 60)),
            stop_check=self._stopped,
            log=self._log,
        )
        if not result.ok:
            return result
        return self._maybe_run_workflow(driver, result)

    def _maybe_run_workflow(self, driver, result: LoginResult) -> LoginResult:
        if not bool(self._params.get("run_workflow_after_login", True)):
            self._log("已登入；未勾選「登入後自動執行庫存流程」，略過步驟 1～7。")
            return result
        if self._stopped():
            return LoginResult(
                ok=False,
                status=result.status,
                message="登入成功，但已停止，未執行庫存流程。",
                final_url=result.final_url,
            )
        self._log("登入成功，接續執行庫存流程（步驟 1～7，完成後循環 3～7）…")
        dismiss_close_popup(driver, log=self._log)
        wf = run_inventory_workflow(
            driver,
            element_wait_sec=float(self._params.get("element_wait_sec", 15)),
            step_pause_sec=float(self._params.get("step_pause_sec", 0.8)),
            loop_steps_3_7=bool(self._params.get("loop_steps_3_7", True)),
            max_loop_rounds=int(self._params.get("max_loop_rounds", 0)),
            stop_check=self._stopped,
            log=self._log,
        )
        if wf.ok:
            rounds_msg = f"（{wf.rounds} 輪）" if wf.rounds > 1 else ""
            return LoginResult(
                ok=True,
                status=result.status,
                message=f"登入並完成庫存流程{rounds_msg}。",
                final_url=wf.final_url or result.final_url,
            )
        return LoginResult(
            ok=False,
            status=result.status,
            message=f"登入成功，但庫存流程失敗：{wf.message}",
            final_url=wf.final_url or result.final_url,
        )

    def _with_driver(self, fn) -> LoginResult:
        from session_guard import LoginResult as LR, LoginStatus

        profile = Path(str(self._params.get("chrome_profile_dir", "")))
        headless = bool(self._params.get("headless", False))
        home_url = str(self._params.get("home_url", ""))
        driver = get_or_clear()
        try:
            if driver is not None:
                self._log("沿用已開啟的 Chrome…")
                navigate_and_dismiss(driver, home_url, log=self._log)
            else:
                self._log("啟動 Chrome（Selenium Manager 自動配對 ChromeDriver）…")
                driver = build_driver(headless=headless, user_data_dir=profile, detach=True)
                navigate_and_dismiss(driver, home_url, log=self._log)
            self._driver = driver
            return fn(driver)
        except Exception as exc:
            self._log(f"錯誤：{exc}")
            return LR(ok=False, status=LoginStatus.UNKNOWN, message=str(exc))
        finally:
            self._driver = driver
            if driver is not None:
                set_driver(driver)


class LoginThread(QThread):
    def __init__(self, worker: LoginWorker, mode: str) -> None:
        super().__init__()
        self._worker = worker
        self._mode = mode

    def run(self) -> None:
        if self._mode == "check":
            self._worker.run_check()
        else:
            self._worker.run_ensure_login()
