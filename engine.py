"""
Core automation logic: scan → move → collect (with verify & retry)
"""

import os
import sys
import json
import time
import random
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

import config

# ── Path resolution (still finds images correctly after exe packaging) ──
def _resolve(path):
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, path)

# ── Screen capture ────────────────────────────────────────
def capture_screen():
    shot = ImageGrab.grab(bbox=config.SCAN_REGION)
    return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)

def screen_center():
    if config.SCAN_REGION:
        l, t, r, b = config.SCAN_REGION
        return ((l + r) // 2, (t + b) // 2)
    w, h = pyautogui.size()
    return (w // 2, h // 2)

# ── Image recognition ───────────────────────────────────────
# The "image" field in config can be a single path string or a list of paths
# — a list means "multiple templates for the same thing" (e.g. different
# animation frames, different lighting); a match against any one counts as a hit.
_template_cache = {}

def _image_paths(image_field):
    if isinstance(image_field, (list, tuple)):
        return list(image_field)
    return [image_field]

def _load_template_and_mask(img_path):
    """
    Load a template. Mask priority order:
    1. Alpha channel (background-removed material)
    2. Matching _mask.png (polygon capture)
    3. No mask
    Results are cached, so a file is never read twice in the same run.
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
    """Match against every template in the image field (single or list), returning the NMS-merged (pos, conf) list."""
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
    Scan for all materials, return the (pos, material_dict) closest to screen center.
    material_dict contains image/collect_action/collect_times/collect_interval.
    Positions currently under quarantine are never selected as a target.
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
    """Check whether a specific material is still on screen."""
    return len(_find_matches_multi(screen_bgr, mat["image"])) > 0

# ── Distance helper ──────────────────────────────────────────
def distance(pos_a, pos_b):
    return ((pos_a[0] - pos_b[0]) ** 2 + (pos_a[1] - pos_b[1]) ** 2) ** 0.5

# ── Persistent collect failure at the same spot ─────────────
# _stuck_tracker records "the position of the material we're currently stuck
# on" and its consecutive failure count; positions within
# SAME_MATERIAL_TOLERANCE are treated as the same material, a different
# position resets the count.
_stuck_tracker = {"pos": None, "count": 0}
# _quarantine records a "temporarily given up" position and when it expires;
# find_nearest_material won't pick it until then.
_quarantine = {"pos": None, "until": 0.0}

def _stuck_count_for(mat_pos):
    """Return the current consecutive failure count for this position (0 for a different position)."""
    prev = _stuck_tracker["pos"]
    if prev is not None and distance(mat_pos, prev) <= config.SAME_MATERIAL_TOLERANCE:
        return _stuck_tracker["count"]
    return 0

def _record_attempt(mat_pos, success):
    """Record the outcome of this full collect attempt (including retries); returns the updated failure count."""
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

# ── Movement ──────────────────────────────────────────────
# The game doesn't accept simulated keyboard input, so movement/turning is
# done by holding the mouse button down on fixed on-screen direction buttons
# (config.MOVE_POINTS) instead of holding a keyboard key. Since there's only
# one mouse cursor, only one direction can be held at a time — no diagonal
# (two direction buttons at once) like the old keyboard version could do;
# the dominant axis is picked each tick instead (see _wanted_direction).
#
# In this game holding a direction button also turns the character to face
# that direction (there's no separate turn button), so:
# - Current facing: estimated by default from "the last direction button
#   held", no screenshot needed. If CHARACTER_CROP + FACING_IMAGES are
#   set, screenshot comparison is used instead (more accurate, catches the
#   case of "held a direction button but terrain blocked it, so it didn't
#   actually turn"); falls back to the estimate automatically when unset.
# - Current position: there's no readable coordinate, so "seconds spent
#   holding a direction button" is accumulated as a relative offset from the
#   spawn point (home); returning home holds the opposite direction for the
#   same duration (an approximation, not exact).

_position = {"x": 0.0, "y": 0.0}   # Estimated offset from home (unit: button-hold seconds)
_facing = {"dir": None}            # Estimated facing: "up"/"down"/"left"/"right"

def reset_position():
    _position["x"] = 0.0
    _position["y"] = 0.0

def detect_facing(screen_bgr):
    """
    Detect the character's current facing via screenshot comparison.
    Requires CHARACTER_CROP and FACING_IMAGES; missing either returns None
    (callers automatically fall back to the button-estimated facing).
    Each direction can be a single image or a list (e.g. multiple frames of
    an idle/walk animation for that facing) — the highest-scoring match in
    the list wins.
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
    Normally returns the button-estimated facing (cheap, no screenshot).
    When force_detect=True and CHARACTER_CROP/FACING_IMAGES are set, uses
    screenshot comparison instead (used once the same material has failed
    several times in a row and the estimate is suspected to be wrong).
    """
    if force_detect and config.CHARACTER_CROP and config.FACING_IMAGES:
        detected = detect_facing(capture_screen())
        if detected:
            return detected
    return _facing["dir"]

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

def _hold_point(direction, duration):
    """Hold the mouse down on the on-screen button for `direction` for `duration` seconds, updating facing and the estimated position."""
    pyautogui.moveTo(*config.MOVE_ORIGIN)
    pyautogui.mouseDown()
    pyautogui.moveTo(*config.MOVE_POINTS[direction], duration=0.05)

    time.sleep(duration)

    pyautogui.mouseUp()
    _track_move(direction, duration)

def _release_mouse():
    pyautogui.mouseUp()
    pyautogui.moveTo(*config.MOVE_ORIGIN, duration=0.02)

def _wanted_direction(target_pos, reach_radius=None):
    """Pick a single direction to hold toward target_pos (only one mouse button can be held at a time)."""
    if reach_radius is None:
        reach_radius = config.REACH_RADIUS
    cx, cy = screen_center()
    dx = target_pos[0] - cx
    dy = target_pos[1] - cy
    want_x = abs(dx) > reach_radius * 0.4
    want_y = abs(dy) > reach_radius * 0.4
    if not want_x and not want_y:
        return None
    if want_x and (not want_y or abs(dx) >= abs(dy)):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"

def _try_unstuck(stop_fn, log_fn):
    _release_mouse()
    if stop_fn():
        return False
    if config.JUMP_POINT:
        pyautogui.click(*config.JUMP_POINT)
        time.sleep(0.2)
    escape_dir = random.choice(list(config.MOVE_POINTS.keys()))
    _hold_point(escape_dir, config.STUCK_ESCAPE_DURATION)
    time.sleep(0.1)
    return not stop_fn()

def _move_toward(find_target_fn, reach_radius, stop_fn, log_fn, arrived_msg, lost_msg):
    held_dir = None
    last_pos = None
    last_moved_at = time.time()
    stuck_attempts = 0

    MOVE_PULSE = getattr(config, "MOVE_PULSE", 0.08)

    try:
        while not stop_fn():
            screen = capture_screen()
            log_fn("capture_screen");
            pos = find_target_fn(screen)
            log_fn("find_target_fn");
            if pos is None:
                log_fn(lost_msg)
                return False

            dist = distance(pos, screen_center())
            if dist <= reach_radius:
                log_fn(arrived_msg.format(dist=dist))
                return True

            # ── stuck detection（保留原邏輯） ─────────────────────
            if last_pos is not None:
                moved = distance(pos, last_pos)

                if moved > config.STUCK_MOVEMENT_THRESHOLD:
                    last_moved_at = time.time()
                    stuck_attempts = 0

                elif time.time() - last_moved_at > config.STUCK_TIMEOUT:
                    stuck_attempts += 1
                    if stuck_attempts > config.STUCK_MAX_ATTEMPTS:
                        log_fn(f"脫困失敗 {stuck_attempts} 次，放棄")
                        return False

                    log_fn(f"卡住，第 {stuck_attempts} 次脫困")
                    if not _try_unstuck(stop_fn, log_fn):
                        return False

                    last_moved_at = time.time()
                    last_pos = None
                    held_dir = None
                    continue

            last_pos = pos

            wanted = _wanted_direction(pos, reach_radius)

            # ── 🔥 核心改動：脈衝式輸入 ─────────────────────
            if wanted is not None:
                pyautogui.moveTo(*config.MOVE_ORIGIN)
                pyautogui.mouseDown()
                pyautogui.moveTo(
                    *config.MOVE_POINTS[wanted],
                    duration=0.03
                )
                time.sleep(MOVE_PULSE)
                pyautogui.mouseUp()
                _track_move(wanted, MOVE_PULSE)
            else:
                _release_mouse()

            held_dir = wanted

            time.sleep(config.SCAN_WHILE_MOVING)
        return False

    finally:
        _release_mouse()

def approach_material(stop_fn, log_fn=print):
    """Keep moving toward the nearest material, with stuck detection."""
    def find(screen):
        pos, _ = find_nearest_material(screen)
        return pos
    return _move_toward(find, config.REACH_RADIUS, stop_fn, log_fn,
                         "到達（距離 {dist:.0f}px）", "移動中素材消失")

def _material_desired_direction(mat_pos):
    """Given a material's position, return the direction the character should face ("up"/"down"/"left"/"right")."""
    cx, cy = screen_center()
    dx = mat_pos[0] - cx
    dy = mat_pos[1] - cy
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"

# ── Realign after a failed collect ──────────────────────────
# In this game the movement buttons double as turning, so "turning" is just
# a quick hold of the relevant direction button.
def _tactic_face_material(mat_pos, stop_fn, log_fn):
    desired = _material_desired_direction(mat_pos)
    log_fn(f"重對準：轉向面對素材（{desired}）")
    _hold_point(desired, config.REALIGN_STRAFE_DURATION)
    time.sleep(0.1)

def _tactic_strafe(cross_dirs, stop_fn, log_fn):
    log_fn("重對準：側移")
    for d in cross_dirs:
        if stop_fn():
            return
        _hold_point(d, config.REALIGN_STRAFE_DURATION)
        time.sleep(0.1)

def _tactic_advance_retreat(mat_pos, stop_fn, log_fn):
    """Step forward then back, to shake free of being stuck at the edge/inside the material's hit detection."""
    log_fn("重對準：前進後退（甩脫卡位）")
    toward_dir = _material_desired_direction(mat_pos)
    back_dir = {"up": "down", "down": "up", "left": "right", "right": "left"}[toward_dir]

    _hold_point(toward_dir, config.REALIGN_STRAFE_DURATION)
    time.sleep(0.1)
    if stop_fn():
        return
    _hold_point(back_dir, config.REALIGN_STRAFE_DURATION)
    time.sleep(0.1)

def _realign_toward(mat_pos, attempt, force_detect, stop_fn, log_fn):
    """
    Realign toward the material after a failed collect:
    1. Back off first, to avoid being stuck inside the material's hit area
    2. Determine whether the current facing is toward the material:
       force_detect=False uses the (cheap) button-hold estimate; force_detect=True
       (same spot has failed several times in a row) prefers screenshot
       detection instead — if not facing it, hold the direction button to correct it
    3. If already facing correctly but still can't collect → cycle through
       strafing / advance-retreat by retry count to shake free of a stuck position
    """
    if stop_fn():
        return

    center = screen_center()
    dx = mat_pos[0] - center[0]
    dy = mat_pos[1] - center[1]

    away_dir = "left" if dx > 0 else "right"
    cross_dirs = [
        "up"   if dy > 0 else "down",
        "down" if dy > 0 else "up",
    ]

    log_fn("重對準：退後")
    _hold_point(away_dir, config.REALIGN_BACK_DURATION)
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
        lambda: _tactic_strafe(cross_dirs, stop_fn, log_fn),
        lambda: _tactic_advance_retreat(mat_pos, stop_fn, log_fn),
    ]
    tactics[attempt % len(tactics)]()

_HOME_META_PATH = _resolve("images/home_landmark.json")

def _load_home_landmark():
    """
    Load the home landmark image(s) + offset written by capture_helper.py's
    "home_landmark" category, if any. Nothing to configure by hand — capturing
    the landmark is enough. Returns (images, offset) or (None, None).
    """
    try:
        with open(_HOME_META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        images = data.get("images")
        offset = data.get("offset")
        if images and offset:
            return images, tuple(offset)
    except (OSError, ValueError, KeyError):
        pass
    return None, None

def _landmark_virtual_target(screen_bgr, images, offset):
    """
    Locate the home landmark and translate its offset from where it should
    appear when the character is home into a "virtual material position" —
    feeding this into the same _move_toward machinery used for materials
    walks the character back to wherever the landmark was captured from.
    """
    matches = _find_matches_multi(screen_bgr, images)
    if not matches:
        return None
    landmark_pos = max(matches, key=lambda m: m[1])[0]
    cx, cy = screen_center()
    ox, oy = offset
    target = (cx + ox, cy + oy)
    return (cx + (landmark_pos[0] - target[0]), cy + (landmark_pos[1] - target[1]))

def _go_home_by_estimate(stop_fn, log_fn):
    """Walk back using the accumulated button-hold-seconds estimate (approximate, drifts over time)."""
    if abs(_position["x"]) < 0.05 and abs(_position["y"]) < 0.05:
        return
    log_fn("回中心待機（估計位置）")
    if abs(_position["x"]) >= 0.05 and not stop_fn():
        d = "left" if _position["x"] > 0 else "right"
        _hold_point(d, abs(_position["x"]))
    if abs(_position["y"]) >= 0.05 and not stop_fn():
        d = "up" if _position["y"] > 0 else "down"
        _hold_point(d, abs(_position["y"]))

def go_home(stop_fn, log_fn):
    """
    Return to "home" to idle. If images/home_landmark.json exists (written by
    capture_helper.py's "home_landmark" category), navigates by tracking that
    landmark's on-screen position (accurate, doesn't drift); otherwise (or if
    the landmark can't currently be found) falls back to the accumulated
    button-hold-seconds estimate.
    """
    images, offset = _load_home_landmark()
    if images:
        log_fn("回中心待機（地標導航）")
        arrived = _move_toward(lambda screen: _landmark_virtual_target(screen, images, offset),
                                config.HOME_REACH_RADIUS, stop_fn, log_fn,
                                "已回到中心（距離 {dist:.0f}px）", "地標消失，改用估計位置回中心")
        if arrived or stop_fn():
            return

    _go_home_by_estimate(stop_fn, log_fn)

def search_wander(stop_fn, log_fn=print):
    log_fn("搜尋中：遊走一圈")
    step = config.SEARCH_DURATION / len(config.SEARCH_PATTERN)
    for d in config.SEARCH_PATTERN:
        if stop_fn():
            break
        _hold_point(d, step)

# ── Collect (with facing verification and retry) ────────────
def collect_with_verify(mat, stop_fn, log_fn=print):
    """
    Click the collect button → wait → scan for whether the material vanished.
    If it's still there: realign (back off + turn/strafe/advance-retreat) →
    approach again → retry. Retries at most COLLECT_RETRY_MAX times.

    Persistent failure at the "same spot" accumulates across rounds (see
    _stuck_tracker):
    - Reaching STUCK_FAIL_THRESHOLD → realign switches to screenshot-based
      facing detection (if configured)
    - Reaching STUCK_GIVE_UP_THRESHOLD → temporarily give up on this spot and
      look for another material instead
    """
    action = mat["collect_action"]
    point  = config.COLLECT_POINTS[action]
    times  = mat["collect_times"]
    ivl    = mat["collect_interval"]

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
        log_fn(f"採集{tag}：點擊 {action} × {times}")
        for _ in range(times):
            if stop_fn():
                return False
            pyautogui.click(*point)
            time.sleep(ivl)

        time.sleep(config.COLLECT_VERIFY_DELAY)
        screen = capture_screen()

        if not material_visible(screen, mat):
            log_fn("採集成功（素材消失）")
            if site_pos:
                _record_attempt(site_pos, True)
            return True

        if attempt < config.COLLECT_RETRY_MAX:
            # Re-scan the material's current position to pass to the realign function
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

# ── Main state machine ───────────────────────────────────────
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
