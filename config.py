# ── 所有可調整設定 ─────────────────────────────────────────

# 熱鍵
HOTKEY_START = "f1"
HOTKEY_STOP  = "f2"

# ── 素材設定（每種素材獨立設定） ──────────────────────────
# 樹只設「大樹」（小樹/中樹不採），礦石四種共用同一顆採集鍵。
# image 路徑請用 capture_helper.py 截圖後，把存出的 captured_N.png（+ _mask.png）
# 改名成對應檔名放進 images/ 資料夾。
#
# image 也可以放一個清單，代表「同一顆素材的多張模板」，例如素材有搖晃動畫、
# 或不同光影下外觀不太一樣，就多截幾張都放進去，比對時任一張命中就算數：
#   "image": ["images/tree_big_1.png", "images/tree_big_2.png"],
MATERIALS = [
    {
        "image":            "images/tree_big.png",   # 大樹
        "collect_key":      "2",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            "images/ore_stone.png",  # 石礦
        "collect_key":      "3",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            "images/ore_copper.png", # 銅礦
        "collect_key":      "3",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            "images/ore_silver.png", # 銀礦
        "collect_key":      "3",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            "images/ore_gold.png",   # 金礦
        "collect_key":      "3",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
]

# 圖像辨識信心門檻 0.0~1.0
MATCH_THRESHOLD = 0.75

# 掃描範圍：None = 全螢幕，或 (left, top, right, bottom)
SCAN_REGION = None

# ── 移動設定 ──────────────────────────────────────────────
# 這款遊戲用方向鍵移動，且移動方向 = 角色面向（沒有獨立的轉向鍵）
MOVE_KEYS = {
    "up":    "up",
    "down":  "down",
    "left":  "left",
    "right": "right",
}

# 邊走邊掃描頻率（秒），建議 0.05~0.15
SCAN_WHILE_MOVING = 0.08

# 距離螢幕中心幾 px 內視為「已到達」
REACH_RADIUS = 100

# ── 採集驗證 ──────────────────────────────────────────────
COLLECT_VERIFY_DELAY = 0.8   # 按完採集鍵後等幾秒確認素材消失
COLLECT_RETRY_MAX    = 2     # 採集失敗最多重試幾次

# ── 採集失敗重對準 ─────────────────────────────────────────
# 移動方向鍵同時就是角色面向，重對準時會先補按「該面向素材的方向鍵」轉正，
# 若已經面向正確但還是採不到，才輪流嘗試側移／前進後退甩開卡位。
REALIGN_BACK_DURATION   = 0.4    # 退後時長（秒）
REALIGN_STRAFE_DURATION = 0.25   # 側移／轉向時長（秒）

# ── 角色面向偵測（進階、選用） ────────────────────────────
# 平常面向是用「最後按的方向鍵」去估計，通常夠用。
# 但如果角色被地形卡住、按了方向鍵卻沒轉向/沒移動，估計值就會跟實際不符。
# 想要更準的話，用 capture_helper.py 分別截「角色朝上/下/左/右」時的定格畫面，
# 存成下面四個檔名，並填好 CHARACTER_CROP（角色在螢幕上的範圍），
# 兩者都設定好才會啟用截圖比對，沒設定就自動維持用按鍵估計。
# 跟 MATERIALS 一樣，每個方向也可以放清單（例如站立/走路動畫多幀）：
#   "up": ["images/facing_up_1.png", "images/facing_up_2.png"],
CHARACTER_CROP = None     # 例如 (860, 440, 1060, 640)
FACING_IMAGES = {
    # "up":    "images/facing_up.png",
    # "down":  "images/facing_down.png",
    # "left":  "images/facing_left.png",
    # "right": "images/facing_right.png",
}

# ── 同一位置持續採集失敗 ──────────────────────────────────
# 平常都用「按鍵估計面向」重對準，比較省效能；
# 只有同一顆素材（位置在誤差內）連續失敗達 STUCK_FAIL_THRESHOLD 次，
# 才改用截圖判定面向（若有設定 CHARACTER_CROP/FACING_IMAGES，兩套算是並存，
# 平常用估計、卡住才切換去查截圖）。
# 如果連截圖判定都救不回來、失敗次數達 STUCK_GIVE_UP_THRESHOLD，就暫時放棄
# 這個位置，STUCK_QUARANTINE_SECONDS 秒內不再把它當成目標，改找別的素材。
SAME_MATERIAL_TOLERANCE  = 40    # 幾 px 內視為同一顆素材
STUCK_FAIL_THRESHOLD     = 2     # 同一顆累積失敗幾次後，優先改用截圖判定面向
STUCK_GIVE_UP_THRESHOLD  = 4     # 累積失敗達幾次後，暫時放棄這顆
STUCK_QUARANTINE_SECONDS = 120   # 放棄後，這個位置多久內不會再被選為目標（秒）

# ── 卡住偵測 ──────────────────────────────────────────────
STUCK_TIMEOUT           = 3.0   # 幾秒沒動視為卡住
STUCK_MOVEMENT_THRESHOLD = 5    # 幾 px 以下算沒動
STUCK_ESCAPE_DURATION   = 0.4   # 脫困每個方向走多久（秒）
STUCK_MAX_ATTEMPTS      = 3     # 最多脫困幾次

JUMP_KEY = "space"

# ── 循環設定 ──────────────────────────────────────────────
SCAN_INTERVAL   = 1.0    # 每輪掃描間隔（秒）
RESPAWN_WAIT    = 30     # 採集完後等待刷新（秒）

# ── 找不到素材時的待機 ────────────────────────────────────
# True：回到啟動時的位置（視為中心點）待機，每隔 IDLE_SCAN_INTERVAL 秒才重新掃描一次
# False：用舊的 SEARCH_PATTERN 到處遊走找素材
RETURN_HOME_WHEN_IDLE = True
IDLE_SCAN_INTERVAL    = 20   # 待機時多久掃描一次素材是否刷新（秒）

# 找不到素材且 RETURN_HOME_WHEN_IDLE = False 時使用
SEARCH_DURATION = 3.0    # 找不到素材時遊走時長（秒）
SEARCH_PATTERN  = ["up", "right", "down", "left"]
