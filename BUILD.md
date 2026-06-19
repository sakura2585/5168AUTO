# 5168AUTO 打包 EXE 說明

## 需求

- Windows 10+
- Python 3.10+（建議用專案或共用 venv）
- 已安裝 **Google Chrome**（執行時由 Selenium Manager 配對 ChromeDriver）

## 安裝打包依賴

```powershell
cd H:\PY\5168AUTO
pip install -r requirements.txt
pip install pyinstaller>=6.0.0
```

## 本機打包（單檔 EXE）

```powershell
cd H:\PY\5168AUTO
# 建議使用共用 venv
& H:\PY\autokey\.venv\Scripts\Activate.ps1
python -m PyInstaller --noconfirm 5168AUTO.spec
```

或直接雙擊 `build_exe.bat`。

產物：

| 路徑 | 說明 |
|------|------|
| `dist\5168AUTO_v0.2.x.exe` | 可執行檔（檔名含版號，供 Release 上傳） |
| `build\` | 暫存（可刪） |

**已驗證**（2026-06-19）：PyInstaller 6.19 + Python 3.12，產物約 **242 MB**（單檔，含 PySide6 / selenium）。

### spec 檔對照

| 檔案 | 用途 |
|------|------|
| `5168AUTO.spec` | 本機打包主 spec |
| `5168AUTO_full.spec` | 同上（完整打包別名） |
| `order_note.spec` | 上傳小幫手預設辨識名稱（轉呼叫 `5168AUTO.spec`） |
| `order_note_full.spec` | 上傳小幫手「完整打包」（轉呼叫 `5168AUTO_full.spec`） |

## 用上傳小幫手發 GitHub Release

1. 執行 `H:\PY\docs前置準備\10_上傳發版\上傳小幫手_含TOKEN.bat`
2. 專案資料夾：`H:\PY\5168AUTO`
3. Repo URL：`https://github.com/sakura2585/5168AUTO.git`
4. 勾選 **發布前執行 PyInstaller**（小幫手會用 `order_note.spec`）
5. 建議在 bat 或環境變數設定：
   ```bat
   set "GH_PUSH_EXE_ASSET_NAME=5168AUTO"
   ```
6. 小幫手會自動：
   - bump `app.py` 的 `_APP_VERSION`
   - 執行 `5168AUTO.spec`（或 `5168AUTO_full.spec`）
   - 將 `dist\5168AUTO_v版號.exe` 壓成 **`5168AUTO_v版號.zip`** 上傳 Release

## 規範（docs前置準備）

- Release 資產檔名：**英文** + **`.zip`**
- zip 內放單一 **`5168AUTO_v版號.exe`**
- 不直接上傳裸 `.exe` 到 Release 頁

## 首次執行注意

- 程式會在 exe 旁（或使用者目錄）建立 `data\` 存放設定與 Chrome Profile
- 請勿把含登入 Session 的 `data\` 提交到 Git

## 常見問題

1. **打包後雙擊沒反應**  
   先用 `5168AUTO.spec` 將 `console=False` 暫改 `console=True` 重打包，看終端機錯誤。

2. **缺少 Qt / selenium 模組**  
   確認使用 `5168AUTO.spec`（已含 `PySide6`、`selenium`、`certifi` hiddenimports）。

3. **Chrome 找不到**  
   本機需安裝 Google Chrome；與開發模式相同，靠 Selenium Manager 自動下載 driver。
