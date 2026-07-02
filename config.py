# ── 所有可調整設定 ─────────────────────────────────────────

# 熱鍵
HOTKEY_START = "f1"
HOTKEY_STOP  = "f2"

# ── 素材設定（每種素材獨立設定） ──────────────────────────
MATERIALS = [
    {
        "image":            "images/material_1.png",  # 素材圖片
        "collect_key":      "f",                       # 採集按鍵
        "collect_times":    5,                         # 按幾次
        "collect_interval": 0.4,                       # 每次間隔（秒）
    },
    # {
    #     "image":            "images/material_2.png",
    #     "collect_key":      "r",
    #     "collect_times":    3,
    #     "collect_interval": 0.5,
    # },
]

# 圖像辨識信心門檻 0.0~1.0
MATCH_THRESHOLD = 0.75

# 掃描範圍：None = 全螢幕，或 (left, top, right, bottom)
SCAN_REGION = None

# ── 移動設定 ──────────────────────────────────────────────
MOVE_KEYS = {
    "up":    "w",
    "down":  "s",
    "left":  "a",
    "right": "d",
}

# 邊走邊掃描頻率（秒），建議 0.05~0.15
SCAN_WHILE_MOVING = 0.08

# 距離螢幕中心幾 px 內視為「已到達」
REACH_RADIUS = 100

# ── 採集驗證 ──────────────────────────────────────────────
COLLECT_VERIFY_DELAY = 0.8   # 按完採集鍵後等幾秒確認素材消失
COLLECT_RETRY_MAX    = 2     # 採集失敗最多重試幾次

# ── 採集失敗重對準 ─────────────────────────────────────────
REALIGN_BACK_DURATION   = 0.4    # 退後時長（秒）
REALIGN_STRAFE_DURATION = 0.25   # 側移時長（秒）

# 旋轉鍵：遊戲有旋轉鍵填入，沒有留 None（改用側移代替）
ROTATE_LEFT_KEY  = None   # 例如 "q"
ROTATE_RIGHT_KEY = None   # 例如 "e"
ROTATE_DURATION  = 0.3    # 每次旋轉時長（秒）

# ── 角色面向偵測（進階，不設定則停用） ───────────────────
# 角色在截圖中的位置範圍 (left, top, right, bottom)
CHARACTER_CROP = None     # 例如 (860, 440, 1060, 640)

# 各面向的參考圖片（用 capture_helper 截角色各方向的圖存入 images/）
FACING_IMAGES = {
    # "north": "images/facing_north.png",
    # "south": "images/facing_south.png",
    # "east":  "images/facing_east.png",
    # "west":  "images/facing_west.png",
}

# ── 卡住偵測 ──────────────────────────────────────────────
STUCK_TIMEOUT           = 3.0   # 幾秒沒動視為卡住
STUCK_MOVEMENT_THRESHOLD = 5    # 幾 px 以下算沒動
STUCK_ESCAPE_DURATION   = 0.4   # 脫困每個方向走多久（秒）
STUCK_MAX_ATTEMPTS      = 3     # 最多脫困幾次

JUMP_KEY = "space"

# ── 循環設定 ──────────────────────────────────────────────
SCAN_INTERVAL   = 1.0    # 每輪掃描間隔（秒）
RESPAWN_WAIT    = 30     # 採集完後等待刷新（秒）
SEARCH_DURATION = 3.0    # 找不到素材時遊走時長（秒）
SEARCH_PATTERN  = ["up", "right", "down", "left"]
