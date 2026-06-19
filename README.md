# 5168AUTO

5168（[007.houseprice.tw](https://007.houseprice.tw/)）自動化工具。

## 目前功能（v0.2.1）

### 登入模組
- Chrome + **Selenium Manager** 自動配對 ChromeDriver
- **Chrome Profile** 保存登入 Session
- 手機＋簡訊驗證碼登入、驗證碼等待倒數
- 自動關閉「關閉」彈窗

### 庫存流程（7 步 + 循環）
1. 尋找並展開頂部選單
2. 點擊子選單項目
3. 點擊頁數列**最後一頁**
4. 點擊列表**最後一筆「修改」**，開新分頁後關閉其他分頁
5. 點擊「我已詳閱並了解」
6. 點擊「完成」
7. 點擊「返回庫存」
8. **返回步驟 3 循環**（預設開啟；0 = 無限直到按停止）

執行前先完成登入；按 **執行庫存流程 / Run Workflow**。

## 安裝

```bash
pip install -r requirements.txt
```

需已安裝 **Google Chrome**。

## 執行

```bash
cd H:\PY\5168AUTO
python app.py
```

## 登入流程

1. 填寫手機號碼，勾選「記住手機號碼」，按 **儲存 / Save**
2. 按 **開啟瀏覽器登入 / Open Browser Login**
3. 程式預填手機、嘗試觸發發送驗證碼，並依 **驗證碼等待 / SMS wait** 秒數倒數等待簡訊
4. 在瀏覽器輸入**簡訊驗證碼**並完成登入
5. 登入成功後 Session 寫入 `data/chrome_profile/`，之後可直接 **檢查登入狀態**

## 設定檔

| 檔案 | 說明 |
|------|------|
| `data/state.json` | 視窗、網址、逾時等（自動產生） |
| `data/credentials.json` | 手機號碼（gitignore，參考 `credentials.example.json`） |
| `data/chrome_profile/` | Chrome 登入 Session（gitignore） |

## 常見問題

1. **ChromeDriver 版本不符**  
   確認 `selenium>=4.15`，Selenium Manager 會自動下載對應 driver。

2. **一直顯示未登入**  
   在 Chrome 視窗完成簡訊驗證；或按「清除 Profile」後重新登入。

3. **Chrome 視窗沒出現**  
   關閉 headless（目前預設關閉）；確認沒有其他 Chrome 占用同一 Profile。

4. **日誌出現亂碼**  
   確認檔案為 UTF-8；終端機編碼設為 UTF-8。

## 打包 EXE

詳見 [BUILD.md](BUILD.md)。

```powershell
# 快速打包
build_exe.bat
# 產物：dist\5168AUTO.exe
```

上傳 Release 時請設 `GH_PUSH_EXE_ASSET_NAME=5168AUTO`，zip 內放 `5168AUTO.exe`。
