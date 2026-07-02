# Screen Bot

用螢幕截圖 + 圖像比對辨識遊戲畫面中的素材（樹、礦石…），自動移動過去、按鍵採集，
採不到時會重對準再試，找不到素材時回中心待機，全部靠模擬鍵盤操作，不讀取遊戲記憶體。

## 需求與安裝

```
pip install -r requirements.txt
```

需要 Python 3 + `pyautogui`、`opencv-python`、`pillow`、`keyboard`（打包用 `pyinstaller`）。

Windows 上 `keyboard` 套件需要系統管理員權限才能註冊全域熱鍵，所以要**以系統管理員身分執行**
`python bot.py`（或打包後的 exe），不然 F1/F2 熱鍵不會有反應。

## 快速開始

1. 用 `capture_helper.py` 截圖，存出素材（大樹、各種礦石）跟需要的話再截角色朝上下左右的定格畫面。
2. 用 `test_recognition.py` 拿截圖 + 模板測一下辨識效果，調到 `MATCH_THRESHOLD` 抓得穩。
3. 打開 `config.py`，把素材圖片路徑、採集鍵等填好（詳見下面「config.py 設定」）。
4. 執行 `python bot.py` 開啟控制面板。
5. `F1` 啟動、`F2` 停止；滑鼠移到螢幕左上角可以緊急停止（pyautogui 的 failsafe）。

## 運作方式

`engine.py` 的 `BotEngine` 是一個簡單的狀態機，主迴圈大致是：

```
尋找素材中 → 移動靠近中 → 採集中 → 等待刷新 → 尋找素材中 → ...
```

- **尋找素材中**：對 `config.MATERIALS` 每一種素材做樣板比對，找螢幕上距離角色（畫面中心）最近的一個。
  找不到的話，若 `RETURN_HOME_WHEN_IDLE = True` 就走回啟動時的位置待機，每隔
  `IDLE_SCAN_INTERVAL` 秒才重新掃描一次；設 `False` 則用舊的 `SEARCH_PATTERN` 到處遊走找。
- **移動靠近中**：持續按方向鍵靠近，含卡住偵測（久了沒移動就跳一下、換方向逃脫）。
- **採集中**：按 `collect_key` 採集鍵，等一下再重掃一次確認素材是否消失。
  沒消失就「重對準」（退後 → 面向素材的方向鍵沒按對就補按 → 側移／前進後退甩開卡位）再靠近一次重試，
  最多重試 `COLLECT_RETRY_MAX` 次。
- **同一位置持續失敗**：跨越好幾輪都採不到同一顆（位置在 `SAME_MATERIAL_TOLERANCE` 內視為同一顆），
  累積到 `STUCK_FAIL_THRESHOLD` 次會改用截圖判定面向（如果有設定，見下面），
  累積到 `STUCK_GIVE_UP_THRESHOLD` 次就暫時放棄這個位置 `STUCK_QUARANTINE_SECONDS` 秒，改找別的素材。
- **等待刷新**：採集成功後原地等 `RESPAWN_WAIT` 秒再重新尋找。

這款遊戲的移動鍵同時也是角色面向（按哪個方向鍵就轉向哪邊，沒有獨立轉向鍵），
所以角色目前面向預設是用「最後按的方向鍵」去估計；角色目前位置也沒有座標可讀，
是用「往某方向按鍵的秒數」累加成一個相對於出生點（中心）的估計位移，回中心待機時再用相反方向按回去。
兩者都只是估計值，不是絕對精準的座標系統。

## 素材截圖與辨識

- `capture_helper.py`：截圖工具。左鍵加點框出素材的多邊形範圍、右鍵/Enter 存檔，
  存出 `images/captured_N.png` + `images/captured_N_mask.png`（遮罩，讓比對只看素材本體、忽略背景）。
  截完把檔名改成 `config.py` 對應的名稱（例如 `tree_big.png`）。
- `test_recognition.py`：離線測試工具，不用真的跑機器人。
  `python test_recognition.py <截圖> <模板> [門檻]`，視窗內用 `+`/`-` 調門檻、`R` 重跑，
  可以看到比對分數跟熱圖，用來決定 `config.MATCH_THRESHOLD` 設多少比較穩。
- 同一顆素材（或同一個面向）可以放**多張模板**：`config.py` 的 `image` 欄位除了單一路徑字串，
  也可以放路徑清單，例如素材有搖晃動畫或不同光影下外觀不同：
  ```python
  "image": ["images/tree_big_1.png", "images/tree_big_2.png"],
  ```
  比對時任一張命中就算數。

## config.py 設定

| 設定 | 說明 |
|---|---|
| `HOTKEY_START` / `HOTKEY_STOP` | 啟動／停止熱鍵 |
| `MATERIALS` | 素材清單，每項要有 `image`（路徑或清單）、`collect_key`（採集鍵）、`collect_times`（按幾次）、`collect_interval`（每次間隔秒數） |
| `MATCH_THRESHOLD` | 圖像比對信心門檻（0~1），用 `test_recognition.py` 調 |
| `SCAN_REGION` | 只掃描螢幕的一部分，`None` 代表全螢幕 |
| `MOVE_KEYS` | 上下左右對應的實際按鍵；這款遊戲用方向鍵，移動方向＝角色面向 |
| `SCAN_WHILE_MOVING` | 邊走邊重新掃描素材位置的頻率（秒） |
| `REACH_RADIUS` | 距離角色（畫面中心）幾 px 內視為已到達素材旁邊 |
| `COLLECT_VERIFY_DELAY` / `COLLECT_RETRY_MAX` | 按完採集鍵等幾秒確認消失／最多重試幾次 |
| `REALIGN_BACK_DURATION` / `REALIGN_STRAFE_DURATION` | 重對準時退後／側移或轉向的按鍵時長 |
| `CHARACTER_CROP` / `FACING_IMAGES` | 進階、選用：設定角色在螢幕上的範圍 + 朝上下左右的定格截圖，開啟後同一顆素材連續失敗多次時會改用截圖判定面向（沒設定就一直用按鍵估計） |
| `SAME_MATERIAL_TOLERANCE` | 幾 px 內視為「同一顆」素材（用來累計持續失敗次數） |
| `STUCK_FAIL_THRESHOLD` | 同一顆累積失敗幾次後，優先改用截圖判定面向 |
| `STUCK_GIVE_UP_THRESHOLD` / `STUCK_QUARANTINE_SECONDS` | 累積失敗幾次後暫時放棄、放棄後幾秒內不再選它 |
| `STUCK_TIMEOUT` / `STUCK_MOVEMENT_THRESHOLD` / `STUCK_ESCAPE_DURATION` / `STUCK_MAX_ATTEMPTS` | 移動中卡住的偵測與脫困參數 |
| `JUMP_KEY` | 脫困時按的跳躍鍵 |
| `SCAN_INTERVAL` | 找不到素材、用遊走模式時，每輪掃描間隔 |
| `RESPAWN_WAIT` | 採集成功後原地等待刷新的秒數 |
| `RETURN_HOME_WHEN_IDLE` / `IDLE_SCAN_INTERVAL` | 找不到素材時是否回中心待機、待機時多久掃描一次 |
| `SEARCH_DURATION` / `SEARCH_PATTERN` | `RETURN_HOME_WHEN_IDLE = False` 時，遊走找素材的時長與路線 |

## Log 與除錯

- GUI 視窗裡的黑色文字框：即時顯示目前在做什麼。
- `bot_log.txt`（跟 `bot.py`/打包後的 exe 同一層目錄）：所有訊息都會加上時間戳記存一份，
  關掉程式也不會消失，方便測完之後回頭看發生了什麼。

常見訊息代表的意思：

| Log 訊息 | 代表 | 可以調的設定 |
|---|---|---|
| 一直「搜尋中：遊走一圈」找不到素材 | 圖像辨識沒命中 | 用 `test_recognition.py` 檢查模板/門檻，或截圖檔名路徑對不上 |
| 反覆「重對準：轉向面對素材」 | 面向一直判斷錯（估計可能跟遊戲實際不同步） | 設定 `CHARACTER_CROP`/`FACING_IMAGES` 改用截圖判定 |
| 「這個位置已連續失敗 N 次，重對準改用截圖判定面向」 | 觸發 `STUCK_FAIL_THRESHOLD` | 確認有沒有設定截圖面向；沒設定的話這行只是提示，實際還是用估計 |
| 「這個位置累積失敗 N 次，暫時放棄 N 秒」 | 觸發 `STUCK_GIVE_UP_THRESHOLD` | 太常出現代表某個點位有問題，或調整 `STUCK_GIVE_UP_THRESHOLD`/`STUCK_QUARANTINE_SECONDS` |
| 「卡住，第 N 次脫困」很多次 | 移動路徑被地形卡住 | 調 `STUCK_TIMEOUT`/`STUCK_ESCAPE_DURATION` |

## 打包成 exe（選用）

Windows 上可以用 `build.bat`（呼叫 PyInstaller）打包成獨立資料夾，
或用 `installer.iss`（Inno Setup）做成安裝檔。兩者都會把 `config.py` 和 `images/` 放在
輸出資料夾旁邊，方便使用者之後直接編輯，不用重新打包。

## 已知限制

- 角色目前位置是用「往某方向按鍵的秒數」累加估算，不是真的座標，長時間跑下來可能會累積誤差
  （例如卡地形、被打斷移動時）。
- 角色面向預設用按鍵估計；`CHARACTER_CROP`/`FACING_IMAGES` 是可選的加強，沒截圖設定就不會啟用。
