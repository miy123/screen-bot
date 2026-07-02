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
def _load_template_and_mask(img_path):
    """
    載入模板，遮罩優先順序：
    1. alpha 通道（去背素材）
    2. 同名 _mask.png（多邊形截圖）
    3. 無遮罩
    """
    full_path = _resolve(img_path)
    img = cv2.imread(full_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None, None

    if len(img.shape) == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        _, mask = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
        if np.count_nonzero(mask) > 0:
            return img[:, :, :3], mask

    template_bgr = img[:, :, :3] if len(img.shape) == 3 else img
    mask_path = _resolve(img_path.replace(".png", "_mask.png"))
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is not None and np.count_nonzero(mask) > 0:
        return template_bgr, mask

    return template_bgr, None

def _find_all_matches(screen_bgr, template, mask, img_path):
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

def find_nearest_material(screen_bgr):
    """
    掃描所有素材，回傳距螢幕中心最近的 (pos, material_dict)。
    material_dict 包含 image/collect_key/collect_times/collect_interval。
    """
    all_candidates = []
    for mat in config.MATERIALS:
        img_path = mat["image"]
        template, mask = _load_template_and_mask(img_path)
        if template is None:
            continue
        h, w = template.shape[:2]
        raw = _find_all_matches(screen_bgr, template, mask, img_path)
        deduped = _nms(raw, min_dist=min(w, h) * 0.6)
        for pos, conf in deduped:
            all_candidates.append((pos, conf, mat))

    if not all_candidates:
        return None, None

    center = screen_center()
    nearest = min(all_candidates, key=lambda m: distance(m[0], center))
    return nearest[0], nearest[2]   # (pos, material_dict)

def material_visible(screen_bgr, mat):
    """確認特定素材是否仍在畫面上。"""
    template, mask = _load_template_and_mask(mat["image"])
    if template is None:
        return False
    h, w = template.shape[:2]
    matches = _find_all_matches(screen_bgr, template, mask, mat["image"])
    return len(matches) > 0

# ── 距離工具 ──────────────────────────────────────────────
def distance(pos_a, pos_b):
    return ((pos_a[0] - pos_b[0]) ** 2 + (pos_a[1] - pos_b[1]) ** 2) ** 0.5

# ── 移動 ──────────────────────────────────────────────────
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
    pyautogui.keyDown(escape_key)
    time.sleep(config.STUCK_ESCAPE_DURATION)
    pyautogui.keyUp(escape_key)
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
            time.sleep(config.SCAN_WHILE_MOVING)

    finally:
        _release_all_move_keys()

# ── 面向偵測（進階，需要 config.FACING_IMAGES） ───────────
def detect_facing(screen_bgr):
    """
    偵測角色目前面向。需設定 CHARACTER_CROP 和 FACING_IMAGES。
    回傳方向字串（"north"/"south"/"east"/"west"）或 None。
    """
    if not config.CHARACTER_CROP or not config.FACING_IMAGES:
        return None

    l, t, r, b = config.CHARACTER_CROP
    crop = screen_bgr[t:b, l:r]
    if crop.size == 0:
        return None

    best_dir, best_val = None, -1
    for direction, img_path in config.FACING_IMAGES.items():
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

def _facing_to_key(facing):
    """面向字串轉成對應的移動鍵（角色正對方向）。"""
    return {
        "north": config.MOVE_KEYS["up"],
        "south": config.MOVE_KEYS["down"],
        "east":  config.MOVE_KEYS["right"],
        "west":  config.MOVE_KEYS["left"],
    }.get(facing)

def _material_desired_facing(mat_pos):
    """根據素材位置計算角色應該面向哪個方向。"""
    cx, cy = screen_center()
    dx = mat_pos[0] - cx
    dy = mat_pos[1] - cy
    if abs(dx) >= abs(dy):
        return "east" if dx > 0 else "west"
    return "south" if dy > 0 else "north"

# ── 採集失敗重對準 ─────────────────────────────────────────
def _realign_toward(mat_pos, stop_fn, log_fn):
    """
    採集失敗後重對準素材：
    1. 若有面向偵測 → 旋轉到正確面向
    2. 否則 → 退後 + 左右側移 + 若有旋轉鍵則左右轉
    """
    if stop_fn():
        return

    center = screen_center()
    dx = mat_pos[0] - center[0]
    dy = mat_pos[1] - center[1]

    # 遠離素材方向
    away_key  = config.MOVE_KEYS["left"  if dx > 0 else "right"]
    # 側向（垂直於素材方向）
    cross_keys = [
        config.MOVE_KEYS["up"   if dy > 0 else "down"],
        config.MOVE_KEYS["down" if dy > 0 else "up"  ],
    ]

    # ── 退後 ──
    log_fn("重對準：退後")
    pyautogui.keyDown(away_key)
    time.sleep(config.REALIGN_BACK_DURATION)
    pyautogui.keyUp(away_key)
    time.sleep(0.1)

    # ── 面向偵測（有設定才執行） ──
    screen = capture_screen()
    current_facing = detect_facing(screen)
    if current_facing:
        desired = _material_desired_facing(mat_pos)
        log_fn(f"面向偵測：目前 {current_facing}，需要 {desired}")
        if current_facing != desired and config.ROTATE_LEFT_KEY:
            # 先左轉一下，再右轉到位
            log_fn("旋轉對準")
            pyautogui.keyDown(config.ROTATE_LEFT_KEY)
            time.sleep(config.ROTATE_DURATION)
            pyautogui.keyUp(config.ROTATE_LEFT_KEY)
            time.sleep(0.05)
            pyautogui.keyDown(config.ROTATE_RIGHT_KEY or config.ROTATE_LEFT_KEY)
            time.sleep(config.ROTATE_DURATION * 2)
            pyautogui.keyUp(config.ROTATE_RIGHT_KEY or config.ROTATE_LEFT_KEY)
            return  # 讓 approach_material 重新靠近對齊

    # ── 無面向偵測：側移 + 旋轉（若有鍵） ──
    if config.ROTATE_LEFT_KEY:
        log_fn("重對準：左右轉")
        pyautogui.keyDown(config.ROTATE_LEFT_KEY)
        time.sleep(config.ROTATE_DURATION)
        pyautogui.keyUp(config.ROTATE_LEFT_KEY)
        time.sleep(0.05)
        pyautogui.keyDown(config.ROTATE_RIGHT_KEY or config.ROTATE_LEFT_KEY)
        time.sleep(config.ROTATE_DURATION * 2)
        pyautogui.keyUp(config.ROTATE_RIGHT_KEY or config.ROTATE_LEFT_KEY)
        time.sleep(0.1)
    else:
        log_fn("重對準：側移")
        for ck in cross_keys:
            if stop_fn():
                return
            pyautogui.keyDown(ck)
            time.sleep(config.REALIGN_STRAFE_DURATION)
            pyautogui.keyUp(ck)
            time.sleep(0.1)

def search_wander(stop_fn, log_fn=print):
    log_fn("搜尋中：遊走一圈")
    step = config.SEARCH_DURATION / len(config.SEARCH_PATTERN)
    for d in config.SEARCH_PATTERN:
        if stop_fn():
            break
        key = config.MOVE_KEYS[d]
        pyautogui.keyDown(key)
        time.sleep(step)
        pyautogui.keyUp(key)

# ── 採集（含方向驗證重試） ────────────────────────────────
def collect_with_verify(mat, stop_fn, log_fn=print):
    """
    按採集鍵 → 等待 → 掃描是否消失。
    若素材仍在：重對準（退後+側移/旋轉）→ 重新靠近 → 再試。
    最多重試 COLLECT_RETRY_MAX 次。
    """
    key   = mat["collect_key"]
    times = mat["collect_times"]
    ivl   = mat["collect_interval"]

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
            return True

        if attempt < config.COLLECT_RETRY_MAX:
            # 取得目前素材位置，傳給重對準函數
            mat_pos, _ = find_nearest_material(screen)
            if mat_pos is None:
                log_fn("素材已消失（重掃確認）")
                return True
            log_fn("素材仍在，重對準後重試")
            _realign_toward(mat_pos, stop_fn, log_fn)
            approach_material(stop_fn, log_fn)
        else:
            log_fn("採集達重試上限，繼續下一輪")

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
