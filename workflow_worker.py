"""庫存流程背景工作。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from browser_core import build_driver
from browser_session import get_or_clear, is_driver_alive, set_driver
from inventory_workflow import WorkflowResult, run_inventory_workflow
from popup_guard import navigate_and_dismiss


class WorkflowWorker(QObject):
    log_line = Signal(str)
    finished = Signal(object)  # WorkflowResult

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

    def run(self) -> None:
        profile = Path(str(self._params.get("chrome_profile_dir", "")))
        headless = bool(self._params.get("headless", False))
        home_url = str(self._params.get("home_url", ""))
        driver = get_or_clear()
        created = False
        try:
            if driver is not None:
                self._log("沿用已開啟的 Chrome 執行庫存流程…")
            else:
                self._log("啟動 Chrome 執行庫存流程…")
                driver = build_driver(headless=headless, user_data_dir=profile, detach=True)
                created = True
                navigate_and_dismiss(driver, home_url, log=self._log)
            self._driver = driver
            set_driver(driver)
            result = run_inventory_workflow(
                driver,
                element_wait_sec=float(self._params.get("element_wait_sec", 15)),
                step_pause_sec=float(self._params.get("step_pause_sec", 0.8)),
                loop_steps_3_7=bool(self._params.get("loop_steps_3_7", True)),
                max_loop_rounds=int(self._params.get("max_loop_rounds", 0)),
                loop_popup_xpaths=list(self._params.get("loop_popup_xpaths") or []),
                max_recovery_per_round=int(self._params.get("max_recovery_per_round", 3)),
                max_recovery_total=int(self._params.get("max_recovery_total", 30)),
                stop_check=self._stopped,
                log=self._log,
            )
            self.finished.emit(result)
        except Exception as exc:
            self._log(f"錯誤：{exc}")
            self.finished.emit(
                WorkflowResult(
                    ok=False,
                    message=str(exc),
                    final_url=getattr(driver, "current_url", "") or "",
                )
            )
        finally:
            self._driver = driver
            if driver is not None and (not created or is_driver_alive(driver)):
                set_driver(driver)


class WorkflowThread(QThread):
    def __init__(self, worker: WorkflowWorker) -> None:
        super().__init__()
        self._worker = worker

    def run(self) -> None:
        self._worker.run()
