# Screen Bot

用螢幕截圖 + 圖像比對辨識遊戲畫面中的素材（樹、礦石…），自動移動過去、點擊按鈕採集，
採不到時會重對準再試，找不到素材時回中心待機，全部靠模擬滑鼠操作，不讀取遊戲記憶體。

> 這款遊戲目前吃不到模擬鍵盤輸入，所以移動／轉向／採集都改成用滑鼠點擊/按住畫面上固定的按鈕座標，
> 不是按鍵盤。詳見下面「控制方式」。

## 需求與安裝

```
pip install -r requirements.txt
```

需要 Python 3 + `pyautogui`、`opencv-python`、`pillow`、`keyboard`（打包用 `pyinstaller`）。

Windows 上 `keyboard` 套件需要系統管理員權限才能註冊全域熱鍵，所以要**以系統管理員身分執行**
`python bot.py`（或打包後的 exe），不然 `F1`/`F2`/`F3` 熱鍵不會有反應。這些熱鍵讀的是你自己實體鍵盤
的按鍵（用來控制腳本本身），跟遊戲吃不吃模擬鍵盤是兩回事。

## 快速開始

1. 用 `capture_helper.py` 截圖，工具會先問你現在要截哪個素材／面向，自動存成對應檔名。
2. 用 `test_recognition.py` 拿截圖 + 模板測一下辨識效果，調到 `MATCH_THRESHOLD` 抓得穩。
3. 找出遊戲畫面上移動/採集按鈕的螢幕座標：開 `python bot.py`，按 `F3`（或按 GUI 上的「Debug 座標」鈕），
   在倒數的幾秒內把滑鼠移到目標按鈕上，log 會印出當下的座標，填進 `config.py` 的 `MOVE_POINTS`／`COLLECT_POINTS`。
   之後座標要重抓（換解析度、遊戲視窗搬過位置）也是用這個功能，不用改程式碼。
4. 打開 `config.py`，把素材圖片路徑、對應的 `collect_action` 等填好（詳見下面「config.py 設定」）。
5. 執行 `python bot.py` 開啟控制面板。
6. `F1` 啟動、`F2` 停止；滑鼠移到螢幕左上角可以緊急停止（pyautogui 的 failsafe）。

## 控制方式：滑鼠點擊畫面按鈕

這款遊戲不接受模擬鍵盤，所以所有操作都改成 `pyautogui` 的滑鼠功能（`mouseDown`/`mouseUp`/`click`），
點擊/按住畫面上固定的按鈕座標，而不是按鍵盤：

- `config.MOVE_POINTS`：上下左右方向鈕的螢幕座標。按住＝持續朝該方向移動，這款遊戲移動同時也是轉向
  （按哪個方向鈕角色就轉向哪邊，沒有獨立轉向鈕）。
- `config.COLLECT_POINTS`：具名的採集按鈕座標（例如 `"lumber"` 是伐木鈕、`"ore"` 是採礦鈕），
  `MATERIALS` 每一項用 `collect_action` 指定要點哪一個。
- `config.JUMP_POINT`：選用的跳躍鈕座標，用在卡住脫困時；沒有這個按鈕就留 `None`，脫困時會跳過這一步。

**重要限制：只有一個滑鼠游標，同一時間只能按住一個按鈕**，不像鍵盤可以同時按住兩個方向鍵做斜向移動。
所以現在移動時會挑「距離較遠的那個軸」單獨按住（例如目標在右上方，會先往右修正，等左右對齊得差不多了
才切換成往上修正），用來逼近斜向目標，但不是真正同時的斜向移動。

這些座標是綁定「目前螢幕解析度＋遊戲視窗位置/大小」的，換解析度、視窗搬過位置、或視窗大小改變
都要重新抓一次座標，不然點擊的位置就不對了。

## 運作方式

`engine.py` 的 `BotEngine` 是一個簡單的狀態機，主迴圈大致是：

```
尋找素材中 → 移動靠近中 → 採集中 → 等待刷新 → 尋找素材中 → ...
```

- **尋找素材中**：對 `config.MATERIALS` 每一種素材做樣板比對，找螢幕上距離角色（畫面中心）最近的一個。
  找不到的話，若 `RETURN_HOME_WHEN_IDLE = True` 就走回啟動時的位置待機，每隔
  `IDLE_SCAN_INTERVAL` 秒才重新掃描一次；設 `False` 則用舊的 `SEARCH_PATTERN` 到處遊走找。
- **移動靠近中**：持續按住方向按鈕靠近，含卡住偵測（久了沒移動就跳一下、換方向逃脫）。
- **採集中**：點擊 `collect_action` 對應的採集按鈕，等一下再重掃一次確認素材是否消失。
  沒消失就「重對準」（退後 → 面向素材的方向按鈕沒按對就補按 → 側移／前進後退甩開卡位）再靠近一次重試，
  最多重試 `COLLECT_RETRY_MAX` 次。
- **同一位置持續失敗**：跨越好幾輪都採不到同一顆（位置在 `SAME_MATERIAL_TOLERANCE` 內視為同一顆），
  累積到 `STUCK_FAIL_THRESHOLD` 次會改用截圖判定面向（如果有設定，見下面），
  累積到 `STUCK_GIVE_UP_THRESHOLD` 次就暫時放棄這個位置 `STUCK_QUARANTINE_SECONDS` 秒，改找別的素材。
- **等待刷新**：採集成功後原地等 `RESPAWN_WAIT` 秒再重新尋找。

### 「中心點」是什麼、人物移動後怎麼回去

這裡的「中心點」不是螢幕上某個固定像素位置，而是**角色在遊戲世界裡的某個位置**。
`screen_center()` 回傳的是螢幕（或 `SCAN_REGION`）正中央的像素座標，這是固定不變的，用來代表「角色目前所在
的螢幕位置」——因為這款遊戲的鏡頭會跟著角色走，角色永遠畫在畫面中間附近，所以可以拿這個固定像素點當作
「角色現在在哪」的替代品，並不是真的在讀角色的世界座標。角色離開這個位置之後，要怎麼判斷「該往哪走才會
回去」，有兩種做法（`go_home()` 會自動挑）：

- **地標導航（`config.HOME_LANDMARK_IMAGE` 有設定時，較準）**：在想當中心點的位置，用
  `capture_helper.py` 的 `home_landmark` 類別截一個固定不動、獨特的地標（石頭、建築物角落、特殊地面花紋
  都可以），工具會算出這個地標的中心跟畫面正中央的偏移量並印出來，貼進 `HOME_LANDMARK_OFFSET`。
  之後回中心待機時，就去找這個地標目前在畫面上的位置，只要它跟「當初截圖時的偏移量」對不上，就照著
  找素材同一套邏輯（`_move_toward`）移動過去，直到對上為止——這是用畫面上看得到的東西直接導航，
  不會有下面「估計位置」那種累積誤差的問題。缺點是角色如果離地標太遠、地標整個不在畫面上，就找不到，
  這時會先退回用估計位置法把角色帶回地標的可視範圍內，抓到地標後再切回精準導航。
- **估計位置（沒設定 `HOME_LANDMARK_IMAGE` 時的預設值，或地標暫時看不到時的備援）**：把「你按下 F1
  啟動當下角色站的位置」當中心，用「往某個方向按住按鈕的秒數」累加成一個估計位移（`engine._position`，
  出發時歸零）：每次移動/重對準/脫困，都會依按住的方向與時間更新這個估計值，回中心待機時就往相反方向
  按住同樣的秒數，把估計值歸零。這只是「用時間換算距離」的估算法，不是真的座標系統，長時間跑下來會累積
  誤差（例如卡地形、被打斷移動、或移動速度本身不是完全穩定），所以比較建議設定地標導航。

## 素材截圖與辨識

- `capture_helper.py`：截圖工具。啟動後（或按 `M`）會先問你現在要截哪個素材／面向
  （清單在檔案開頭的 `CATEGORIES`，跟 `config.py` 的素材/面向名稱對應，也包含 `home_landmark`
  中心點地標），之後存檔會自動用 `<名稱>_<編號>.png` 命名，編號會接續 `images/` 資料夾裡已經有的
  檔案，不會覆蓋、也不用你自己改檔名。操作：左鍵加點框出多邊形、右鍵/Enter 存檔（存出 `.png` +
  `_mask.png` 遮罩）、`G` 重新截一張畫面（拍下一個動畫幀/時間點時用）、`M` 換素材、`Q` 離開。
  截 `home_landmark` 時會額外印出跟畫面中心的偏移量，直接貼進 `config.HOME_LANDMARK_OFFSET`。
- `test_recognition.py`：離線測試工具，不用真的跑機器人。
  `python test_recognition.py <截圖> <模板> [門檻]`，視窗內用 `+`/`-` 調門檻、`R` 重跑，
  可以看到比對分數跟熱圖，用來決定 `config.MATCH_THRESHOLD` 設多少比較穩。
- 同一顆素材（或同一個面向）可以放**多張模板**：`config.py` 的 `image` 欄位除了單一路徑字串，
  也可以放路徑清單，例如素材有搖晃動畫或不同光影下外觀不同：
  ```python
  "image": ["images/tree_big_1.png", "images/tree_big_2.png"],
  ```
  比對時任一張命中就算數，也正好對應 `capture_helper.py` 自動編號存出來的檔名。

## config.py 設定

| 設定 | 說明 |
|---|---|
| `HOTKEY_START` / `HOTKEY_STOP` / `HOTKEY_DEBUG` | 啟動／停止／讀取滑鼠座標熱鍵（讀你自己的實體鍵盤，跟遊戲吃不吃鍵盤無關） |
| `DEBUG_POSITION_DELAY` | 按下 `HOTKEY_DEBUG` 後，等幾秒才讀取滑鼠座標（留時間把滑鼠移過去） |
| `MATERIALS` | 素材清單，每項要有 `image`（路徑或清單）、`collect_action`（對應 `COLLECT_POINTS` 的名稱）、`collect_times`（點幾次）、`collect_interval`（每次間隔秒數） |
| `MATCH_THRESHOLD` | 圖像比對信心門檻（0~1），用 `test_recognition.py` 調 |
| `SCAN_REGION` | 只掃描螢幕的一部分，`None` 代表全螢幕 |
| `MOVE_POINTS` | 上下左右方向按鈕的螢幕座標（滑鼠按住＝持續朝該方向移動＋轉向） |
| `COLLECT_POINTS` | 具名採集按鈕的螢幕座標，`MATERIALS` 用 `collect_action` 指定要點哪一個 |
| `JUMP_POINT` | 選用的跳躍按鈕座標，脫困時用；沒有就留 `None` |
| `SCAN_WHILE_MOVING` | 邊走邊重新掃描素材位置的頻率（秒） |
| `REACH_RADIUS` | 距離角色（畫面中心）幾 px 內視為已到達素材旁邊 |
| `COLLECT_VERIFY_DELAY` / `COLLECT_RETRY_MAX` | 按完採集鈕等幾秒確認消失／最多重試幾次 |
| `REALIGN_BACK_DURATION` / `REALIGN_STRAFE_DURATION` | 重對準時退後／側移或轉向的按住時長 |
| `CHARACTER_CROP` / `FACING_IMAGES` | 進階、選用：設定角色在螢幕上的範圍 + 朝上下左右的定格截圖，開啟後同一顆素材連續失敗多次時會改用截圖判定面向（沒設定就一直用按鈕估計） |
| `SAME_MATERIAL_TOLERANCE` | 幾 px 內視為「同一顆」素材（用來累計持續失敗次數） |
| `STUCK_FAIL_THRESHOLD` | 同一顆累積失敗幾次後，優先改用截圖判定面向 |
| `STUCK_GIVE_UP_THRESHOLD` / `STUCK_QUARANTINE_SECONDS` | 累積失敗幾次後暫時放棄、放棄後幾秒內不再選它 |
| `STUCK_TIMEOUT` / `STUCK_MOVEMENT_THRESHOLD` / `STUCK_ESCAPE_DURATION` / `STUCK_MAX_ATTEMPTS` | 移動中卡住的偵測與脫困參數 |
| `SCAN_INTERVAL` | 找不到素材、用遊走模式時，每輪掃描間隔 |
| `RESPAWN_WAIT` | 採集成功後原地等待刷新的秒數 |
| `RETURN_HOME_WHEN_IDLE` / `IDLE_SCAN_INTERVAL` | 找不到素材時是否回中心待機、待機時多久掃描一次 |
| `HOME_LANDMARK_IMAGE` / `HOME_LANDMARK_OFFSET` / `HOME_REACH_RADIUS` | 選用：用截圖地標導航回中心（見上面「中心點是什麼」），沒設定 `HOME_LANDMARK_IMAGE` 就用估計位置法 |
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

- 沒設定 `HOME_LANDMARK_IMAGE` 時，角色位置是用「往某方向按住按鈕的秒數」累加估算，不是真的座標，
  長時間跑下來可能會累積誤差（例如卡地形、被打斷移動時）。詳見上面「中心點是什麼」，建議改用地標導航。
- 角色面向預設用按鈕估計；`CHARACTER_CROP`/`FACING_IMAGES` 是可選的加強，沒截圖設定就不會啟用。
- 滑鼠只有一個游標，同一時間只能按住一個方向按鈕，沒辦法像鍵盤那樣同時按兩個方向做真正的斜向移動，
  只能用「先修正距離較遠的那一軸」來逼近。
- `MOVE_POINTS`/`COLLECT_POINTS`/`JUMP_POINT`/`HOME_LANDMARK_OFFSET` 的座標／偏移量都綁定目前的螢幕
  解析度和遊戲視窗位置/大小，換了就要用 `F3`（Debug 座標）重新抓一次；地標圖也要在解析度不變的前提下
  用才準。
