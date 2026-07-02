"""
核心自動化邏輯：掃描 → 移動 → 採集（含驗證重試）
"""

import os
import sys
import time
import random
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

import config

# ── 路徑解析（exe 打包後仍正確找到圖片） ─────────────────
def _resolve(path):
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, path)

# ── 螢幕擷取 ──────────────────────────────────────────────
def capture_screen():
    shot = ImageGrab.grab(bbox=config.SCAN_REGION)
    return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)

def screen_center():
    if config.SCAN_REGION:
        l, t, r, b = config.SCAN_REGION
        return ((l + r) // 2, (t + b) // 2)
    w, h = pyautogui.size()
    return (w // 2, h // 2)

# ── 圖像辨識 ──────────────────────────────────────────────
# config 裡的 "image" 欄位可以是單一路徑字串，也可以是路徑清單 —— 放清單時代表
# 「同一個東西的多張模板」（例如動畫的不同幀、不同光影），比對時任一張命中就算數。
_template_cache = {}

def _image_paths(image_field):
    if isinstance(image_field, (list, tuple)):
        return list(image_field)
    return [image_field]

def _load_template_and_mask(img_path):
    """
    載入模板，遮罩優先順序：
    1. alpha 通道（去背素材）
    2. 同名 _mask.png（多邊形截圖）
    3. 無遮罩
    載入結果會快取，同一次執行不會重複讀檔。
    """
    full_path = _resolve(img_path)
    if full_path in _template_cache:
        return _template_cache[full_path]

    img = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
    result = (None, None)
    if img is not None:
        alpha_mask = None
        if len(img.shape) == 3 and img.shape[2] == 4:
            _, alpha_mask = cv2.threshold(img[:, :, 3], 128, 255, cv2.THRESH_BINARY)
            if np.count_nonzero(alpha_mask) == 0:
                alpha_mask = None

        if alpha_mask is not None:
            result = (img[:, :, :3], alpha_mask)
        else:
            template_bgr = img[:, :, :3] if len(img.shape) == 3 else img
            mask_path = _resolve(img_path.replace(".png", "_mask.png"))
            mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if mask is not None and np.count_nonzero(mask) == 0:
                mask = None
            result = (template_bgr, mask)

    _template_cache[full_path] = result
    return result

def _find_all_matches(screen_bgr, template, mask):
    result = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED,
                               mask=mask)
    h, w = template.shape[:2]
    ys, xs = np.where(result >= config.MATCH_THRESHOLD)
    matches = []
    for x, y in zip(xs, ys):
        cx = x + w // 2
        cy = y + h // 2
        if config.SCAN_REGION:
            cx += config.SCAN_REGION[0]
            cy += config.SCAN_REGION[1]
        matches.append(((cx, cy), float(result[y, x])))
    return matches

def _nms(matches, min_dist):
    sorted_m = sorted(matches, key=lambda m: -m[1])
    kept = []
    for m in sorted_m:
        if all(distance(m[0], k[0]) >= min_dist for k in kept):
            kept.append(m)
    return kept

def _find_matches_multi(screen_bgr, image_field):
    """對 image 欄位（單張或多張模板）逐一比對，回傳 NMS 合併後的 (pos, conf) 清單。"""
    all_matches = []
    min_side = None
    for img_path in _image_paths(image_field):
        template, mask = _load_template_and_mask(img_path)
        if template is None:
            continue
        h, w = template.shape[:2]
        min_side = min(w, h) if min_side is None else min(min_side, w, h)
        all_matches.extend(_find_all_matches(screen_bgr, template, mask))

    if not all_matches:
        return []
    return _nms(all_matches, min_dist=min_side * 0.6)

def find_nearest_material(screen_bgr):
    """
    掃描所有素材，回傳距螢幕中心最近的 (pos, material_dict)。
    material_dict 包含 image/collect_key/collect_times/collect_interval。
    暫時放棄（quarantine）中的位置不會被選為目標。
    """
    all_candidates = []
    for mat in config.MATERIALS:
        for pos, conf in _find_matches_multi(screen_bgr, mat["image"]):
            if _is_quarantined(pos):
                continue
            all_candidates.append((pos, conf, mat))

    if not all_candidates:
        return None, None

    center = screen_center()
    nearest = min(all_candidates, key=lambda m: distance(m[0], center))
    return nearest[0], nearest[2]   # (pos, material_dict)

def material_visible(screen_bgr, mat):
    """確認特定素材是否仍在畫面上。"""
    return len(_find_matches_multi(screen_bgr, mat["image"])) > 0

# ── 距離工具 ──────────────────────────────────────────────
def distance(pos_a, pos_b):
    return ((pos_a[0] - pos_b[0]) ** 2 + (pos_a[1] - pos_b[1]) ** 2) ** 0.5

# ── 同一位置持續採集失敗判定 ────────────────────────────────
# _stuck_tracker 記錄「目前卡著的那顆素材位置」跟連續失敗次數；
# 位置差在 SAME_MATERIAL_TOLERANCE 內都視為同一顆，換了位置就重新計次。
_stuck_tracker = {"pos": None, "count": 0}
# _quarantine 記錄「暫時放棄」的位置跟解除時間，過期前 find_nearest_material 不會選它
_quarantine = {"pos": None, "until": 0.0}

def _stuck_count_for(mat_pos):
    """回傳這個位置目前累積的連續失敗次數（不同位置視為 0）。"""
    prev = _stuck_tracker["pos"]
    if prev is not None and distance(mat_pos, prev) <= config.SAME_MATERIAL_TOLERANCE:
        return _stuck_tracker["count"]
    return 0

def _record_attempt(mat_pos, success):
    """紀錄這次完整採集（含重試）的結果，回傳更新後的累積失敗次數。"""
    if success:
        _stuck_tracker["pos"] = None
        _stuck_tracker["count"] = 0
        return 0
    same_spot = (_stuck_tracker["pos"] is not None and
                 distance(mat_pos, _stuck_tracker["pos"]) <= config.SAME_MATERIAL_TOLERANCE)
    _stuck_tracker["count"] = _stuck_tracker["count"] + 1 if same_spot else 1
    _stuck_tracker["pos"] = mat_pos
    return _stuck_tracker["count"]

def _quarantine_position(mat_pos):
    _quarantine["pos"] = mat_pos
    _quarantine["until"] = time.time() + config.STUCK_QUARANTINE_SECONDS
    _stuck_tracker["pos"] = None
    _stuck_tracker["count"] = 0

def _is_quarantined(mat_pos):
    if _quarantine["pos"] is None:
        return False
    if time.time() > _quarantine["until"]:
        return False
    return distance(mat_pos, _quarantine["pos"]) <= config.SAME_MATERIAL_TOLERANCE

# ── 移動 ──────────────────────────────────────────────────
# 這款遊戲移動方向鍵同時就是角色面向（沒有獨立轉向鍵），所以：
# - 目前面向：預設用「最後按下的方向鍵」估計，不需要截圖；
#   若設定了 CHARACTER_CROP + FACING_IMAGES，會改用截圖比對（更準，能抓到
#   「按了方向鍵但被地形卡住、其實沒轉向」的情況），沒設定就自動退回估計值。
# - 目前位置：沒有座標可讀，用「往某方向按鍵的秒數」累加當作相對於出生點（中心）的位移，
#   回中心待機時再用相反方向、等長時間按回去（近似值，非絕對精準）

_position = {"x": 0.0, "y": 0.0}   # 相對中心的估計位移（單位：按鍵秒數）
_facing = {"dir": None}            # 按鍵估計的面向："up"/"down"/"left"/"right"

def reset_position():
    _position["x"] = 0.0
    _position["y"] = 0.0

def detect_facing(screen_bgr):
    """
    用截圖比對偵測角色目前面向。需設定 CHARACTER_CROP 和 FACING_IMAGES，
    兩者缺一則回傳 None（呼叫端會自動退回用按鍵估計的面向）。
    每個方向可以放單張圖或一個清單（例如同一面向的待機/走路動畫多幀），
    清單內任一張比對分數最高就採用。
    """
    if not config.CHARACTER_CROP or not config.FACING_IMAGES:
        return None

    l, t, r, b = config.CHARACTER_CROP
    crop = screen_bgr[t:b, l:r]
    if crop.size == 0:
        return None

    best_dir, best_val = None, -1
    for direction, image_field in config.FACING_IMAGES.items():
        for img_path in _image_paths(image_field):
            template, mask = _load_template_and_mask(img_path)
            if template is None:
                continue
            if template.shape[0] > crop.shape[0] or template.shape[1] > crop.shape[1]:
                continue
            result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED,
                                       mask=mask)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val = max_val
                best_dir = direction

    return best_dir if best_val > 0.6 else None

def current_facing(force_detect=False):
    """
    平常回傳按鍵估計的面向（便宜、不用截圖）。
    force_detect=True 且設定了 CHARACTER_CROP/FACING_IMAGES 時，才改用截圖比對
    （用在同一顆素材已經連續失敗好幾次，懷疑估計值不準的時候）。
    """
    if force_detect and config.CHARACTER_CROP and config.FACING_IMAGES:
        detected = detect_facing(capture_screen())
        if detected:
            return detected
    return _facing["dir"]

def _key_to_dir(key):
    for d, k in config.MOVE_KEYS.items():
        if k == key:
            return d
    return None

def _track_move(direction, duration):
    if direction is None:
        return
    _facing["dir"] = direction
    if direction == "right":
        _position["x"] += duration
    elif direction == "left":
        _position["x"] -= duration
    elif direction == "down":
        _position["y"] += duration
    elif direction == "up":
        _position["y"] -= duration

def _hold_key(key, duration):
    """按住方向鍵 duration 秒，同時更新面向與估計位置。"""
    pyautogui.keyDown(key)
    time.sleep(duration)
    pyautogui.keyUp(key)
    _track_move(_key_to_dir(key), duration)

def _wanted_keys(mat_pos):
    cx, cy = screen_center()
    dx = mat_pos[0] - cx
    dy = mat_pos[1] - cy
    keys = set()
    if abs(dx) > config.REACH_RADIUS * 0.4:
        keys.add(config.MOVE_KEYS["right" if dx > 0 else "left"])
    if abs(dy) > config.REACH_RADIUS * 0.4:
        keys.add(config.MOVE_KEYS["down" if dy > 0 else "up"])
    return keys

def _release_all_move_keys():
    for key in config.MOVE_KEYS.values():
        pyautogui.keyUp(key)

def _try_unstuck(stop_fn, log_fn):
    _release_all_move_keys()
    if stop_fn():
        return False
    pyautogui.press(config.JUMP_KEY)
    time.sleep(0.2)
    escape_key = random.choice(list(config.MOVE_KEYS.values()))
    _hold_key(escape_key, config.STUCK_ESCAPE_DURATION)
    time.sleep(0.1)
    return not stop_fn()

def approach_material(stop_fn, log_fn=print):
    """持續移動靠近最近素材，含卡住偵測。"""
    held_keys = set()
    last_mat_pos = None
    last_moved_at = time.time()
    stuck_attempts = 0

    try:
        while not stop_fn():
            screen = capture_screen()
            mat_pos, _ = find_nearest_material(screen)

            if mat_pos is None:
                log_fn("移動中素材消失")
                break

            dist = distance(mat_pos, screen_center())
            if dist <= config.REACH_RADIUS:
                log_fn(f"到達（距離 {dist:.0f}px）")
                break

            if last_mat_pos is not None:
                moved = distance(mat_pos, last_mat_pos)
                if moved > config.STUCK_MOVEMENT_THRESHOLD:
                    last_moved_at = time.time()
                    stuck_attempts = 0
                elif time.time() - last_moved_at > config.STUCK_TIMEOUT:
                    stuck_attempts += 1
                    if stuck_attempts > config.STUCK_MAX_ATTEMPTS:
                        log_fn(f"脫困失敗 {stuck_attempts} 次，放棄")
                        break
                    log_fn(f"卡住，第 {stuck_attempts} 次脫困")
                    if not _try_unstuck(stop_fn, log_fn):
                        break
                    last_moved_at = time.time()
                    last_mat_pos = None
                    held_keys = set()
                    continue

            last_mat_pos = mat_pos
            wanted = _wanted_keys(mat_pos)
            for k in held_keys - wanted:
                pyautogui.keyUp(k)
            for k in wanted - held_keys:
                pyautogui.keyDown(k)
            held_keys = wanted
            for k in held_keys:
                _track_move(_key_to_dir(k), config.SCAN_WHILE_MOVING)
            time.sleep(config.SCAN_WHILE_MOVING)

    finally:
        _release_all_move_keys()

def _material_desired_direction(mat_pos):
    """根據素材位置，回傳角色該面向哪個方向鍵（"up"/"down"/"left"/"right"）。"""
    cx, cy = screen_center()
    dx = mat_pos[0] - cx
    dy = mat_pos[1] - cy
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"

# ── 採集失敗重對準 ─────────────────────────────────────────
# 這款遊戲用移動鍵當轉向，所以「轉向」就是輕點一下該方向鍵。
def _tactic_face_material(mat_pos, stop_fn, log_fn):
    desired = _material_desired_direction(mat_pos)
    log_fn(f"重對準：轉向面對素材（{desired}）")
    _hold_key(config.MOVE_KEYS[desired], config.REALIGN_STRAFE_DURATION)
    time.sleep(0.1)

def _tactic_strafe(cross_keys, stop_fn, log_fn):
    log_fn("重對準：側移")
    for ck in cross_keys:
        if stop_fn():
            return
        _hold_key(ck, config.REALIGN_STRAFE_DURATION)
        time.sleep(0.1)

def _tactic_advance_retreat(mat_pos, stop_fn, log_fn):
    """前進一小步再退回，甩開卡在素材判定範圍邊緣/內部的情形。"""
    log_fn("重對準：前進後退（甩脫卡位）")
    toward_dir = _material_desired_direction(mat_pos)
    back_dir = {"up": "down", "down": "up", "left": "right", "right": "left"}[toward_dir]

    _hold_key(config.MOVE_KEYS[toward_dir], config.REALIGN_STRAFE_DURATION)
    time.sleep(0.1)
    if stop_fn():
        return
    _hold_key(config.MOVE_KEYS[back_dir], config.REALIGN_STRAFE_DURATION)
    time.sleep(0.1)

def _realign_toward(mat_pos, attempt, force_detect, stop_fn, log_fn):
    """
    採集失敗後重對準素材：
    1. 先退後，避免卡在素材判定範圍內
    2. 算出目前面向是否對著素材：force_detect=False 用按鍵估計（便宜），
       force_detect=True 時（同一顆已連續失敗多次）優先用截圖判定 → 不對就補按方向鍵轉正
    3. 若已經面向正確但還是採不到 → 依重試次數輪流嘗試側移／前進後退甩開卡位
    """
    if stop_fn():
        return

    center = screen_center()
    dx = mat_pos[0] - center[0]
    dy = mat_pos[1] - center[1]

    away_key  = config.MOVE_KEYS["left"  if dx > 0 else "right"]
    cross_keys = [
        config.MOVE_KEYS["up"   if dy > 0 else "down"],
        config.MOVE_KEYS["down" if dy > 0 else "up"  ],
    ]

    log_fn("重對準：退後")
    _hold_key(away_key, config.REALIGN_BACK_DURATION)
    time.sleep(0.1)
    if stop_fn():
        return

    desired = _material_desired_direction(mat_pos)
    facing = current_facing(force_detect)
    if facing != desired:
        source = "截圖判定" if force_detect else "按鍵估計"
        log_fn(f"面向（{source}）：目前 {facing or '未知'}，需要 {desired}")
        _tactic_face_material(mat_pos, stop_fn, log_fn)
        return

    tactics = [
        lambda: _tactic_strafe(cross_keys, stop_fn, log_fn),
        lambda: _tactic_advance_retreat(mat_pos, stop_fn, log_fn),
    ]
    tactics[attempt % len(tactics)]()

def go_home(stop_fn, log_fn):
    """走回啟動時的位置（中心點）待機，用累積移動秒數估算的相對位置換算回程。"""
    if abs(_position["x"]) < 0.05 and abs(_position["y"]) < 0.05:
        return
    log_fn("回中心待機")
    if abs(_position["x"]) >= 0.05 and not stop_fn():
        key = config.MOVE_KEYS["left" if _position["x"] > 0 else "right"]
        _hold_key(key, abs(_position["x"]))
    if abs(_position["y"]) >= 0.05 and not stop_fn():
        key = config.MOVE_KEYS["up" if _position["y"] > 0 else "down"]
        _hold_key(key, abs(_position["y"]))

def search_wander(stop_fn, log_fn=print):
    log_fn("搜尋中：遊走一圈")
    step = config.SEARCH_DURATION / len(config.SEARCH_PATTERN)
    for d in config.SEARCH_PATTERN:
        if stop_fn():
            break
        _hold_key(config.MOVE_KEYS[d], step)

# ── 採集（含方向驗證重試） ────────────────────────────────
def collect_with_verify(mat, stop_fn, log_fn=print):
    """
    按採集鍵 → 等待 → 掃描是否消失。
    若素材仍在：重對準（退後+轉向/側移/前進後退）→ 重新靠近 → 再試。
    最多重試 COLLECT_RETRY_MAX 次。

    「同一位置」的持續失敗會跨輪累計（見 _stuck_tracker）：
    - 累積達 STUCK_FAIL_THRESHOLD 次 → 重對準改用截圖判定面向（若有設定）
    - 累積達 STUCK_GIVE_UP_THRESHOLD 次 → 暫時放棄這個位置一段時間，改找別的素材
    """
    key   = mat["collect_key"]
    times = mat["collect_times"]
    ivl   = mat["collect_interval"]

    screen = capture_screen()
    site_pos, _ = find_nearest_material(screen)
    prior_fails = _stuck_count_for(site_pos) if site_pos else 0
    force_detect = prior_fails >= config.STUCK_FAIL_THRESHOLD
    if force_detect:
        log_fn(f"這個位置已連續失敗 {prior_fails} 次，重對準改用截圖判定面向")

    for attempt in range(1 + config.COLLECT_RETRY_MAX):
        if stop_fn():
            return False

        tag = f"（第 {attempt+1} 次）" if attempt > 0 else ""
        log_fn(f"採集{tag}：按 {key} × {times}")
        for _ in range(times):
            if stop_fn():
                return False
            pyautogui.press(key)
            time.sleep(ivl)

        time.sleep(config.COLLECT_VERIFY_DELAY)
        screen = capture_screen()

        if not material_visible(screen, mat):
            log_fn("採集成功（素材消失）")
            if site_pos:
                _record_attempt(site_pos, True)
            return True

        if attempt < config.COLLECT_RETRY_MAX:
            # 取得目前素材位置，傳給重對準函數
            mat_pos, _ = find_nearest_material(screen)
            if mat_pos is None:
                log_fn("素材已消失（重掃確認）")
                if site_pos:
                    _record_attempt(site_pos, True)
                return True
            log_fn("素材仍在，重對準後重試")
            _realign_toward(mat_pos, attempt, force_detect, stop_fn, log_fn)
            approach_material(stop_fn, log_fn)
        else:
            log_fn("採集達重試上限，繼續下一輪")

    if site_pos:
        fail_count = _record_attempt(site_pos, False)
        if fail_count >= config.STUCK_GIVE_UP_THRESHOLD:
            log_fn(f"這個位置累積失敗 {fail_count} 次，暫時放棄 {config.STUCK_QUARANTINE_SECONDS} 秒")
            _quarantine_position(site_pos)

    return not stop_fn()

# ── 主狀態機 ──────────────────────────────────────────────
class BotEngine:
    IDLE        = "閒置"
    SEARCHING   = "尋找素材中"
    APPROACHING = "移動靠近中"
    COLLECTING  = "採集中"
    WAITING     = "等待刷新"

    def __init__(self, log_fn=print, state_fn=None):
        self.log = log_fn
        self.set_state_cb = state_fn
        self._state = self.IDLE
        self._running = False

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, val):
        self._state = val
        if self.set_state_cb:
            self.set_state_cb(val)

    def start(self):
        self._running = True
        reset_position()
        self.log("Bot 啟動")
        self._run_loop()

    def stop(self):
        self._running = False
        self.state = self.IDLE
        self.log("Bot 暫停")

    def _stopped(self):
        return not self._running

    def _run_loop(self):
        self.state = self.SEARCHING

        while self._running:
            screen = capture_screen()
            mat_pos, mat = find_nearest_material(screen)

            if mat_pos is None:
                self.state = self.SEARCHING
                if config.RETURN_HOME_WHEN_IDLE:
                    go_home(self._stopped, self.log)
                    if not self._running:
                        return
                    self.state = self.WAITING
                    self.log(f"待機中，每 {config.IDLE_SCAN_INTERVAL} 秒掃描一次")
                    for remaining in range(config.IDLE_SCAN_INTERVAL, 0, -1):
                        if not self._running:
                            return
                        if self.set_state_cb:
                            self.set_state_cb(f"待機中（{remaining}s）")
                        time.sleep(1)
                else:
                    search_wander(self._stopped, self.log)
                    time.sleep(config.SCAN_INTERVAL)
                continue

            dist = distance(mat_pos, screen_center())
            self.log(f"發現 {mat['image']}，距離 {dist:.0f}px")

            if dist > config.REACH_RADIUS:
                self.state = self.APPROACHING
                approach_material(self._stopped, self.log)

            if not self._running:
                return

            self.state = self.COLLECTING
            collect_with_verify(mat, self._stopped, self.log)

            if not self._running:
                return

            self.state = self.WAITING
            self.log(f"等待刷新 {config.RESPAWN_WAIT} 秒")
            for remaining in range(config.RESPAWN_WAIT, 0, -1):
                if not self._running:
                    return
                if self.set_state_cb:
                    self.set_state_cb(f"{self.WAITING}（{remaining}s）")
                time.sleep(1)

            self.state = self.SEARCHING
