"""5168AUTO — 登入模組入口。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config_store import load_state, save_state
from credentials_store import load_credentials, mask_phone, save_credentials
from login_worker import LoginThread, LoginWorker
from paths import CHROME_PROFILE_DIR, DEFAULT_URL, LOGIN_URL
from session_guard import LoginResult, LoginStatus
from workflow_worker import WorkflowThread, WorkflowWorker
from inventory_workflow import WorkflowResult

_APP_VERSION = "v0.2.15"


def _clamp_geometry(
    x: int | None, y: int | None, w: int, h: int, min_w: int, min_h: int
) -> tuple[int, int, int, int]:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return 120, 120, max(min_w, w), max(min_h, h)
    geo = screen.availableGeometry()
    width = max(min_w, min(w, geo.width()))
    height = max(min_h, min(h, geo.height()))
    if x is None or y is None:
        nx = geo.x() + (geo.width() - width) // 2
        ny = geo.y() + (geo.height() - height) // 2
        return nx, ny, width, height
    nx = max(geo.x(), min(int(x), geo.x() + geo.width() - width))
    ny = max(geo.y(), min(int(y), geo.y() + geo.height() - height))
    return nx, ny, width, height


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"5168AUTO v{_APP_VERSION}")
        self.setMinimumSize(680, 700)

        self._state = load_state()
        self._creds = load_credentials()
        self._login_worker = LoginWorker()
        self._workflow_worker = WorkflowWorker()
        self._login_thread: LoginThread | None = None
        self._workflow_thread: WorkflowThread | None = None
        self._busy = False
        self._busy_mode = ""

        self._build_ui()
        self._restore_geometry()
        self._load_form_from_state()
        self._append_log("就緒。5168 使用手機＋簡訊驗證碼登入，Session 保存在 Chrome Profile。")

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # --- 固定頂部：登入設定 ---
        login_box = QGroupBox("登入設定 / Login")
        form = QFormLayout(login_box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.url_edit = QLineEdit(DEFAULT_URL)
        self.url_edit.setPlaceholderText("https://007.houseprice.tw/")
        form.addRow("啟動網址 / URL", self.url_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("09xxxxxxxx")
        form.addRow("手機號碼 / Phone", self.phone_edit)

        self.remember_chk = QCheckBox("記住手機號碼 / Remember phone")
        form.addRow("", self.remember_chk)

        self.profile_label = QLabel(str(CHROME_PROFILE_DIR))
        self.profile_label.setWordWrap(True)
        form.addRow("Chrome Profile", self.profile_label)

        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(30, 1800)
        self.timeout_spin.setSuffix(" 秒 / sec")
        self.timeout_spin.setDecimals(0)
        form.addRow("登入等待逾時 / Login timeout", self.timeout_spin)

        self.sms_wait_spin = QDoubleSpinBox()
        self.sms_wait_spin.setRange(0, 600)
        self.sms_wait_spin.setSuffix(" 秒 / sec")
        self.sms_wait_spin.setDecimals(0)
        self.sms_wait_spin.setToolTip(
            "輸入電話並觸發發送後，等待簡訊驗證碼送達的秒數。\n"
            "Seconds to wait for SMS verification code after phone entry."
        )
        form.addRow("驗證碼等待 / SMS wait", self.sms_wait_spin)

        outer.addWidget(login_box)

        workflow_box = QGroupBox("庫存流程 / Inventory Workflow")
        wf_form = QFormLayout(workflow_box)
        self.element_wait_spin = QDoubleSpinBox()
        self.element_wait_spin.setRange(5, 120)
        self.element_wait_spin.setSuffix(" 秒 / sec")
        self.element_wait_spin.setDecimals(0)
        wf_form.addRow("元素等待 / Element wait", self.element_wait_spin)
        self.step_pause_spin = QDoubleSpinBox()
        self.step_pause_spin.setRange(0, 10)
        self.step_pause_spin.setSingleStep(0.1)
        self.step_pause_spin.setSuffix(" 秒 / sec")
        self.step_pause_spin.setDecimals(1)
        wf_form.addRow("步驟間隔 / Step pause", self.step_pause_spin)
        self.run_workflow_chk = QCheckBox("登入後自動執行庫存流程 / Run workflow after login")
        self.run_workflow_chk.setChecked(True)
        wf_form.addRow("", self.run_workflow_chk)
        self.loop_3_7_chk = QCheckBox("循環步驟 3～7 / Loop steps 3-7")
        self.loop_3_7_chk.setChecked(True)
        wf_form.addRow("", self.loop_3_7_chk)
        self.max_loop_spin = QDoubleSpinBox()
        self.max_loop_spin.setRange(0, 9999)
        self.max_loop_spin.setDecimals(0)
        self.max_loop_spin.setSpecialValueText("無限 / Until stop")
        self.max_loop_spin.setToolTip("0 表示無限循環，按「停止」結束。")
        wf_form.addRow("最大循環次數 / Max loops", self.max_loop_spin)

        popup_row = QHBoxLayout()
        self.popup_xpath_edit = QLineEdit()
        self.popup_xpath_edit.setPlaceholderText(
            "例如 /html/body/div[6]/div[2]/button[1]"
        )
        self.btn_popup_add = QPushButton("新增 / Add")
        self.btn_popup_remove = QPushButton("刪除 / Remove")
        popup_row.addWidget(self.popup_xpath_edit, stretch=1)
        popup_row.addWidget(self.btn_popup_add)
        popup_row.addWidget(self.btn_popup_remove)
        wf_form.addRow("循環彈窗 XPath / Loop popup", popup_row)
        self.popup_xpath_list = QListWidget()
        self.popup_xpath_list.setMaximumHeight(72)
        self.popup_xpath_list.setToolTip(
            "僅在返回步驟 3 開始下一輪前，依序嘗試點擊這些 XPath。"
        )
        wf_form.addRow("", self.popup_xpath_list)

        outer.addWidget(workflow_box)

        # --- 固定頂部：操作按鈕 ---
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("儲存 / Save")
        self.btn_login = QPushButton("開啟瀏覽器登入 / Open Browser Login")
        self.btn_check = QPushButton("檢查登入狀態 / Check Login")
        self.btn_workflow = QPushButton("執行庫存流程 / Run Workflow")
        self.btn_stop = QPushButton("停止 / Stop")
        self.btn_clear_profile = QPushButton("清除 Profile / Clear Profile")
        self.btn_stop.setEnabled(False)
        for btn in (
            self.btn_save,
            self.btn_login,
            self.btn_check,
            self.btn_workflow,
            self.btn_stop,
            self.btn_clear_profile,
        ):
            btn_row.addWidget(btn)
        outer.addLayout(btn_row)

        self.status_label = QLabel("狀態 / Status：待命")
        outer.addWidget(self.status_label)

        # --- 內容區：日誌 ---
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("執行紀錄 / Log…")
        outer.addWidget(self.log_view, stretch=1)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_login.clicked.connect(self._on_open_login)
        self.btn_check.clicked.connect(self._on_check_login)
        self.btn_workflow.clicked.connect(self._on_run_workflow)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_clear_profile.clicked.connect(self._on_clear_profile)
        self.btn_popup_add.clicked.connect(self._on_popup_add)
        self.btn_popup_remove.clicked.connect(self._on_popup_remove)

        self._login_worker.log_line.connect(self._append_log)
        self._login_worker.finished.connect(self._on_login_finished)
        self._workflow_worker.log_line.connect(self._append_log)
        self._workflow_worker.finished.connect(self._on_workflow_finished)

    def _load_form_from_state(self) -> None:
        self.url_edit.setText(str(self._state.get("url", DEFAULT_URL)))
        self.timeout_spin.setValue(float(self._state.get("login_wait_timeout_sec", 300)))
        self.sms_wait_spin.setValue(float(self._state.get("sms_wait_sec", 60)))
        self.element_wait_spin.setValue(float(self._state.get("element_wait_sec", 15)))
        self.step_pause_spin.setValue(float(self._state.get("step_pause_sec", 0.8)))
        self.run_workflow_chk.setChecked(bool(self._state.get("run_workflow_after_login", True)))
        self.loop_3_7_chk.setChecked(bool(self._state.get("loop_steps_3_7", True)))
        self.max_loop_spin.setValue(float(self._state.get("max_loop_rounds", 0)))
        self._load_popup_xpaths_from_state()
        phone = self._creds.get("phone", "")
        if phone:
            self.phone_edit.setText(str(phone))
        self.remember_chk.setChecked(bool(self._creds.get("remember_phone", False)))
        profile = str(self._state.get("chrome_profile_dir", CHROME_PROFILE_DIR))
        self.profile_label.setText(profile)

    def _collect_state(self) -> None:
        self._state["url"] = self.url_edit.text().strip() or DEFAULT_URL
        self._state["login_wait_timeout_sec"] = float(self.timeout_spin.value())
        self._state["sms_wait_sec"] = float(self.sms_wait_spin.value())
        self._state["element_wait_sec"] = float(self.element_wait_spin.value())
        self._state["step_pause_sec"] = float(self.step_pause_spin.value())
        self._state["run_workflow_after_login"] = bool(self.run_workflow_chk.isChecked())
        self._state["loop_steps_3_7"] = bool(self.loop_3_7_chk.isChecked())
        self._state["max_loop_rounds"] = int(self.max_loop_spin.value())
        self._state["loop_popup_xpaths"] = self._popup_xpaths_from_list()
        self._state["chrome_profile_dir"] = str(CHROME_PROFILE_DIR)

    def _popup_xpaths_from_list(self) -> list[str]:
        out: list[str] = []
        for i in range(self.popup_xpath_list.count()):
            item = self.popup_xpath_list.item(i)
            if item is None:
                continue
            text = item.text().strip()
            if text:
                out.append(text)
        return out

    def _load_popup_xpaths_from_state(self) -> None:
        self.popup_xpath_list.clear()
        raw = self._state.get("loop_popup_xpaths", [])
        if not isinstance(raw, list):
            return
        for xp in raw:
            if isinstance(xp, str) and xp.strip():
                self.popup_xpath_list.addItem(xp.strip())

    def _on_popup_add(self) -> None:
        xp = self.popup_xpath_edit.text().strip()
        if not xp:
            return
        self.popup_xpath_list.addItem(xp)
        self.popup_xpath_edit.clear()
        self._append_log(f"已新增循環彈窗 XPath：{xp}")

    def _on_popup_remove(self) -> None:
        row = self.popup_xpath_list.currentRow()
        if row < 0:
            return
        item = self.popup_xpath_list.takeItem(row)
        if item is not None:
            self._append_log(f"已刪除循環彈窗 XPath：{item.text()}")

    def _restore_geometry(self) -> None:
        win = self._state.get("window", {})
        if not isinstance(win, dict):
            win = {}
        w = int(win.get("width", 720) or 720)
        h = int(win.get("height", 560) or 560)
        x = win.get("x")
        y = win.get("y")
        nx, ny, nw, nh = _clamp_geometry(
            int(x) if x is not None else None,
            int(y) if y is not None else None,
            w,
            h,
            self.minimumWidth(),
            self.minimumHeight(),
        )
        self.setGeometry(nx, ny, nw, nh)

    def _save_geometry(self) -> None:
        g = self.geometry()
        self._state["window"] = {
            "width": g.width(),
            "height": g.height(),
            "x": g.x(),
            "y": g.y(),
        }

    def _append_log(self, msg: str) -> None:
        self.log_view.append(msg)
        sb = self.log_view.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def _set_busy(self, busy: bool, mode: str = "") -> None:
        self._busy = busy
        self._busy_mode = mode if busy else ""
        self.btn_save.setEnabled(not busy)
        self.btn_login.setEnabled(not busy)
        self.btn_check.setEnabled(not busy)
        self.btn_workflow.setEnabled(not busy)
        self.btn_clear_profile.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)

    def _worker_params(self) -> dict:
        return {
            "phone": self.phone_edit.text().strip(),
            "home_url": self.url_edit.text().strip() or DEFAULT_URL,
            "login_url": LOGIN_URL,
            "chrome_profile_dir": str(CHROME_PROFILE_DIR),
            "headless": bool(self._state.get("headless", False)),
            "wait_timeout_sec": float(self.timeout_spin.value()),
            "poll_interval_sec": float(self._state.get("login_poll_interval_sec", 2)),
            "sms_wait_sec": float(self.sms_wait_spin.value()),
            "element_wait_sec": float(self.element_wait_spin.value()),
            "step_pause_sec": float(self.step_pause_spin.value()),
            "run_workflow_after_login": bool(self.run_workflow_chk.isChecked()),
            "loop_steps_3_7": bool(self.loop_3_7_chk.isChecked()),
            "max_loop_rounds": int(self.max_loop_spin.value()),
            "loop_popup_xpaths": self._popup_xpaths_from_list(),
        }

    def _workflow_params(self) -> dict:
        base = self._worker_params()
        return base

    def _start_worker(self, mode: str) -> None:
        if self._busy:
            return
        self._collect_state()
        save_state(self._state)
        self._login_worker.configure(**self._worker_params())
        self._set_busy(True, "login")
        self.status_label.setText("狀態 / Status：執行中…")
        self._login_thread = LoginThread(self._login_worker, mode)
        self._login_thread.finished.connect(self._clear_thread)
        self._login_thread.start()

    def _clear_thread(self) -> None:
        self._login_thread = None

    def _on_save(self) -> None:
        phone = self.phone_edit.text().strip()
        remember = self.remember_chk.isChecked()
        save_credentials(phone, remember)
        self._collect_state()
        save_state(self._state)
        shown = mask_phone(phone) if remember else "(未記住)"
        self._append_log(f"已儲存設定。手機：{shown}")
        self.status_label.setText("狀態 / Status：已儲存")

    def _on_open_login(self) -> None:
        self._on_save()
        self._append_log("開始登入流程（成功後將自動執行步驟 1～7）…")
        self._start_worker("ensure")

    def _on_check_login(self) -> None:
        self._on_save()
        if self.run_workflow_chk.isChecked():
            self._append_log("檢查登入狀態（已登入則自動執行步驟 1～7）…")
        else:
            self._append_log("檢查登入狀態…")
        self._start_worker("check")

    def _on_run_workflow(self) -> None:
        if self._busy:
            return
        self._on_save()
        self._append_log("開始執行庫存流程…")
        self._workflow_worker.configure(**self._workflow_params())
        self._set_busy(True, "workflow")
        self.status_label.setText("狀態 / Status：庫存流程執行中…")
        self._workflow_thread = WorkflowThread(self._workflow_worker)
        self._workflow_thread.finished.connect(self._clear_workflow_thread)
        self._workflow_thread.start()

    def _clear_workflow_thread(self) -> None:
        self._workflow_thread = None

    def _on_stop(self) -> None:
        if self._busy_mode == "workflow":
            self._workflow_worker.request_stop()
        else:
            self._login_worker.request_stop()
        self._append_log("已送出停止請求。")

    def _on_clear_profile(self) -> None:
        ans = QMessageBox.question(
            self,
            "清除 Chrome Profile / Clear Profile",
            "將刪除本機 Chrome Profile（含登入 Cookie）。\n"
            "Delete local Chrome profile including login cookies.\n\n"
            "確定繼續？",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        profile = Path(str(self._state.get("chrome_profile_dir", CHROME_PROFILE_DIR)))
        if profile.exists():
            shutil.rmtree(profile, ignore_errors=True)
        self._append_log(f"已清除 Chrome Profile：{profile}")
        self.status_label.setText("狀態 / Status：Profile 已清除")

    def _on_workflow_finished(self, result: object) -> None:
        self._set_busy(False)
        if not isinstance(result, WorkflowResult):
            self.status_label.setText("狀態 / Status：未知結果")
            return
        if result.ok:
            self.status_label.setText("狀態 / Status：流程完成 / Done")
        else:
            self.status_label.setText("狀態 / Status：流程失敗 / Failed")
        self._append_log(f"結果：{result.message}")
        if result.rounds > 0:
            self._append_log(f"完成輪數：{result.rounds}")
        if result.final_url:
            self._append_log(f"目前網址：{result.final_url}")

    def _on_login_finished(self, result: object) -> None:
        self._set_busy(False)
        if not isinstance(result, LoginResult):
            self.status_label.setText("狀態 / Status：未知結果")
            return
        if result.ok and result.status == LoginStatus.LOGGED_IN:
            self.status_label.setText("狀態 / Status：已登入 / Logged in")
        elif result.status == LoginStatus.NOT_LOGGED_IN:
            self.status_label.setText("狀態 / Status：未登入 / Not logged in")
        else:
            self.status_label.setText("狀態 / Status：待確認 / Unknown")
        self._append_log(f"結果：{result.message}")
        if result.final_url:
            self._append_log(f"目前網址：{result.final_url}")

    def _verify_controls_visible(self) -> None:
        for w in (
            self.btn_save,
            self.btn_login,
            self.btn_check,
            self.btn_workflow,
            self.btn_stop,
            self.btn_clear_profile,
        ):
            if not w.isVisible() or w.height() <= 0:
                self._append_log(f"警告：控制項可能不可見 — {w.text()}")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._verify_controls_visible()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._busy:
            if self._busy_mode == "workflow":
                self._workflow_worker.request_stop()
            else:
                self._login_worker.request_stop()
        self._collect_state()
        self._save_geometry()
        try:
            save_state(self._state)
        except OSError:
            pass
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
