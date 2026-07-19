"""
Core automation logic: scan → move → collect (with verify & retry)
"""

import os
import sys
import json
import time
import random
import traceback
import cv2
import numpy as np
import pyautogui
import pydirectinput
from PIL import ImageGrab

import config

# pyautogui/pydirectinput both default to a 0.1s pause AFTER every call
# (moveTo, mouseDown, mouseUp, keyDown, keyUp, ...) meant for human-speed
# scripting — left at default, every _hold_point() call was silently holding
# the button ~0.1-0.2s longer than its requested duration (mouseDown() then
# moveTo() to the direction point each eat a 0.1s pause while the button is
# already down), which is proportionally huge for the short recorded moves
# FIXED_ROUTE_RECORDED_SCALE has been compensating for. Disable it — timing
# here is controlled explicitly via time.sleep(duration) instead.
pyautogui.PAUSE = 0
pydirectinput.PAUSE = 0

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

_scan_state = {"index": 0}   # Sticky index into config.MATERIALS — see find_nearest_material

def reset_scan_state():
    _scan_state["index"] = 0

def find_nearest_material(screen_bgr):
    """
    Scan for a material to target, one type at a time instead of always
    scanning every configured material (each type is a full-screen
    matchTemplate call, so scanning all of them every tick is the main
    cause of slow scans).

    Sticky behavior: stay on whichever material type last had a hit, and
    keep scanning only that type. Only when it comes up empty do we step
    to the next configured type, trying each in turn (at most once around
    the full list) until one has a match. Positions currently under
    quarantine are never selected as a target.
    """
    n = len(config.MATERIALS)
    start = _scan_state["index"] % n

    for step in range(n):
        idx = (start + step) % n
        mat = config.MATERIALS[idx]

        candidates = []
        for pos, conf in _find_matches_multi(screen_bgr, mat["image"]):
            if _is_quarantined(pos):
                continue
            candidates.append((pos, conf))

        if candidates:
            _scan_state["index"] = idx
            center = screen_center()
            nearest = min(candidates, key=lambda c: distance(c[0], center))
            return nearest[0], mat

    return None, None

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
# Plain simulated keyboard input doesn't register with this game, which is
# why movement/turning defaulted to holding the mouse button down on fixed
# on-screen direction buttons (config.MOVE_POINTS) instead of holding a
# keyboard key — config.USE_KEYBOARD_MOVEMENT switches to pydirectinput's
# scan-code-based key holds instead, still being tested against the mouse
# scheme (see that config comment for why scan codes might work where plain
# simulated keys didn't). Either way only one input can be held at a time
# (one mouse cursor, and _hold_point() only holds one key), so no diagonal
# (two directions at once) like a human player could do; the dominant axis
# is picked each tick instead (see _wanted_direction).
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
    """
    Hold `direction` — a single direction, or a list of directions to hold
    at once (e.g. ["up", "right"] for a real diagonal, the way a human
    player holding two WASD keys together actually moves) — for `duration`
    seconds, updating facing and the estimated position. Two mutually
    exclusive control schemes, picked by config.USE_KEYBOARD_MOVEMENT:
    - keyboard (config.MOVE_KEYS): holds every key in the list down at once
      via pydirectinput, which injects hardware scan codes through SendInput
      rather than the virtual-key codes plain keyboard-simulation libraries
      use — this game was found to ignore virtual-key simulated input but
      accepts real keyboard, so scan codes are worth testing as "close
      enough to real" before assuming keyboard control is impossible. True
      simultaneous multi-key holds are only possible here, not with mouse.
    - mouse (config.MOVE_POINTS): the original scheme — click-drag onto an
      on-screen D-pad button and hold the mouse down there. Only one button
      can be held at a time (one cursor), so multiple directions fall back
      to holding each one in turn for the full duration (same approximation
      config.py's algorithmic diamond-piece route already uses for its own
      diagonal steps) — this takes len(directions) times longer than the
      keyboard scheme's true simultaneous hold, not an equivalent substitute.
    """
    directions = [direction] if isinstance(direction, str) else list(direction)

    if config.USE_KEYBOARD_MOVEMENT:
        keys = [config.MOVE_KEYS[d] for d in directions]
        for key in keys:
            pydirectinput.keyDown(key, _pause=False)
        time.sleep(duration)
        for key in keys:
            pydirectinput.keyUp(key, _pause=False)
    else:
        for d in directions:
            pyautogui.moveTo(*config.MOVE_ORIGIN)
            pyautogui.mouseDown()
            pyautogui.moveTo(*config.MOVE_POINTS[d])
            time.sleep(duration)
            pyautogui.mouseUp()

    for d in directions:
        _track_move(d, duration)

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
    last_dist = None
    last_moved_at = time.time()
    stuck_attempts = 0
    miss_streak = 0

    MOVE_PULSE = getattr(config, "MOVE_PULSE", 0.08)

    try:
        while not stop_fn():
            screen = capture_screen()
            log_fn("capture_screen");
            pos = find_target_fn(screen)
            log_fn("find_target_fn");
            if pos is None:
                # Tolerate a couple of consecutive misses (occlusion by the character's
                # own sprite at close range, a stray animation frame) before giving up —
                # a single missed tick otherwise aborted the approach even when the
                # material was still right there.
                miss_streak += 1
                if miss_streak >= config.APPROACH_MISS_TOLERANCE:
                    # It was already fairly close on the last successful reading right
                    # before it vanished — most likely we've simply gotten close enough
                    # that our own character sprite is now covering it, not that it
                    # actually moved away. Treat that as arrival rather than failure.
                    if last_dist is not None and last_dist <= reach_radius * config.APPROACH_DISAPPEAR_ARRIVAL_FACTOR:
                        log_fn(arrived_msg.format(dist=last_dist) + "（消失前已在附近，視為抵達）")
                        return True
                    log_fn(lost_msg)
                    return False
                continue
            miss_streak = 0

            dist = distance(pos, screen_center())
            last_dist = dist
            if dist <= reach_radius:
                log_fn(arrived_msg.format(dist=dist))
                log_fn(f"　目標座標={pos}｜人物座標（估計，相對起點秒數）=({_position['x']:.2f}, {_position['y']:.2f})")
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

def approach_material(mat, stop_fn, log_fn=print):
    """
    Keep moving toward one specific material (the one already chosen — not
    re-picked every tick), with stuck detection.

    Tracks that one instance by proximity continuity between ticks (nearest
    to where we last saw it), not "nearest to screen center" every tick: with
    two instances of the same material both roughly ahead, nearest-to-center
    can flip between them from one tick to the next as their exact detected
    position jitters slightly, which made the character zig-zag between two
    different trees/ores instead of walking straight at the one it found.
    """
    tracked = {"pos": None}

    def find(screen):
        candidates = [pos for pos, _ in _find_matches_multi(screen, mat["image"]) if not _is_quarantined(pos)]
        if not candidates:
            return None

        reference = tracked["pos"] if tracked["pos"] is not None else screen_center()
        target = min(candidates, key=lambda p: distance(p, reference))
        tracked["pos"] = target
        return target

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
#
# Realign strategies are data (config.REALIGN_STRATEGIES), not code: each is
# a sequence of (role, duration_multiplier) steps, where role is one of
# "toward"/"away"/"side1"/"side2" — resolved per-call from mat_pos via
# _realign_axes(), since the material's screen-space direction changes as the
# character (and camera) moves. All durations are expressed as a multiple of
# config.REALIGN_STEP_DURATION seconds of button-hold time, deliberately NOT
# derived from any pixel distance — the on-screen coordinate of a fixed
# object shifts as the character moves (the camera follows the character), so
# "hold time" is the only stable, movement-independent unit available here
# (same reasoning as the existing _position/_track_move estimate).
_OPPOSITE_DIR = {"up": "down", "down": "up", "left": "right", "right": "left"}

def _realign_axes(mat_pos):
    """Resolve toward/away/side1/side2 directions relative to mat_pos, dominant-axis first."""
    toward = _material_desired_direction(mat_pos)
    center = screen_center()
    dx = mat_pos[0] - center[0]
    dy = mat_pos[1] - center[1]
    if toward in ("left", "right"):
        side1, side2 = ("up", "down") if dy >= 0 else ("down", "up")
    else:
        side1, side2 = ("left", "right") if dx >= 0 else ("right", "left")
    return {"toward": toward, "away": _OPPOSITE_DIR[toward], "side1": side1, "side2": side2}

def _tactic_face_material(mat_pos, stop_fn, log_fn):
    desired = _material_desired_direction(mat_pos)
    log_fn(f"重對準：轉向面對素材（{desired}）")
    _hold_point(desired, config.REALIGN_STEP_DURATION)
    time.sleep(0.08)

def _run_realign_strategy(strategy, axes, stop_fn, log_fn):
    desc = " → ".join(f"{axes[role]}{config.REALIGN_STEP_DURATION * mult:.2f}s" for role, mult in strategy)
    log_fn(f"重對準：執行策略 {desc}")
    for role, mult in strategy:
        if stop_fn():
            return
        _hold_point(axes[role], config.REALIGN_STEP_DURATION * mult)
        time.sleep(0.08)

def _realign_toward(mat_pos, strategy_attempts, force_detect, stop_fn, log_fn):
    """
    Realign toward the material after a failed collect:
    1. Determine whether the current facing is toward the material:
       force_detect=False uses the (cheap) button-hold estimate; force_detect=True
       (same spot has failed several times in a row) prefers screenshot
       detection instead — if not facing it, just turn and return (the next
       attempt re-checks from scratch rather than also moving this round).
    2. If already facing correctly, run the current realign strategy from
       config.REALIGN_STRATEGIES. strategy_attempts is the *total* tries at
       this spot (carried across collect_with_verify calls via the stuck
       tracker, not just this round's retry count) — each strategy gets
       config.REALIGN_STRATEGY_REPEAT tries before moving on to the next one,
       so a promising adjustment isn't abandoned after a single attempt but a
       consistently-failing one doesn't get retried forever either.
    """
    if stop_fn():
        return

    axes = _realign_axes(mat_pos)
    desired = axes["toward"]
    facing = current_facing(force_detect)
    if facing != desired:
        source = "截圖判定" if force_detect else "按鍵估計"
        log_fn(f"面向（{source}）：目前 {facing or '未知'}，需要 {desired}")
        _tactic_face_material(mat_pos, stop_fn, log_fn)
        return

    strategies = config.REALIGN_STRATEGIES
    idx = (strategy_attempts // config.REALIGN_STRATEGY_REPEAT) % len(strategies)
    log_fn(f"重對準：策略 {idx + 1}/{len(strategies)}（此位置已嘗試 {strategy_attempts} 次）")
    _run_realign_strategy(strategies[idx], axes, stop_fn, log_fn)

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
    If it's still there: realign (turn to face it, then run a realign
    strategy — see config.REALIGN_STRATEGIES) → approach again → retry.
    Retries at most COLLECT_RETRY_MAX times.

    Returns True only on an actual successful collect (material vanished);
    False if retries were exhausted (or the bot was stopped) — the caller
    uses this to skip the respawn wait and retry immediately when stuck.

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
    log_fn(f"鎖定採集目標，座標={site_pos}")
    prior_fails = _stuck_count_for(site_pos) if site_pos else 0
    force_detect = prior_fails >= config.STUCK_FAIL_THRESHOLD
    if force_detect:
        log_fn(f"這個位置已連續失敗 {prior_fails} 次，重對準改用截圖判定面向")

    # Used only for the "still there" sanity check below — NOT site_pos.
    # The screen's origin moves with the character, so once realign/approach
    # has moved us, the same physical material's on-screen coordinate shifts
    # too; comparing against the very first lock (site_pos) would misreport a
    # real re-detection as "a different material" just because we walked.
    # site_pos itself stays fixed — it's the key for cross-round stuck/quarantine
    # tracking, which is intentionally independent of this per-attempt drift.
    last_known_pos = site_pos

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
            same_spot = last_known_pos is not None and distance(mat_pos, last_known_pos) <= config.SAME_MATERIAL_TOLERANCE
            spot_tag = "同一位置" if same_spot else "⚠️不同位置，疑似掃到別的素材"
            log_fn(f"素材仍在，座標={mat_pos}（上次座標={last_known_pos}，{spot_tag}），重對準後重試")
            _realign_toward(mat_pos, prior_fails + attempt, force_detect, stop_fn, log_fn)
            approach_material(mat, stop_fn, log_fn)
            if stop_fn():
                return False
            # Screen moved during realign/approach — refresh the baseline so
            # the next attempt's comparison isn't against a stale coordinate.
            screen = capture_screen()
            refreshed_pos, _ = find_nearest_material(screen)
            if refreshed_pos is not None:
                last_known_pos = refreshed_pos
        else:
            log_fn("採集達重試上限，繼續下一輪")

    if site_pos:
        fail_count = _record_attempt(site_pos, False)
        if fail_count >= config.STUCK_GIVE_UP_THRESHOLD:
            log_fn(f"這個位置累積失敗 {fail_count} 次，暫時放棄 {config.STUCK_QUARANTINE_SECONDS} 秒")
            _quarantine_position(site_pos)

    return False

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
        reset_scan_state()
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

        try:
            self._run_loop_body()
        except Exception:
            # An unhandled exception here would otherwise silently kill this
            # background thread — the GUI just stops updating with no
            # indication why, indistinguishable from "still working". Log it
            # and stop cleanly instead.
            self.log("發生未預期的錯誤，Bot 已自動停止：\n" + traceback.format_exc())
            self._running = False
            self.state = self.IDLE

    def _run_loop_body(self):
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
            self.log(f"發現 {mat['image']}，距離 {dist:.0f}px，座標={mat_pos}")

            if dist > config.REACH_RADIUS:
                self.state = self.APPROACHING
                approach_material(mat, self._stopped, self.log)

            if not self._running:
                return

            self.state = self.COLLECTING
            collected = collect_with_verify(mat, self._stopped, self.log)

            if not self._running:
                return

            # No respawn wait either way — go straight back to searching. There's
            # usually other materials already available elsewhere, so idling here
            # on the assumption *this* spot will respawn soon just wastes time.
            self.log("採集成功，繼續尋找下一個目標" if collected else "採集失敗，繼續尋找下一個目標")

            self.state = self.SEARCHING


# ── Fixed movement route ─────────────────────────────────────
# Alternative to BotEngine: no image recognition at all — just a hand-authored
# script of move/collect steps (config.FIXED_ROUTE), repeated in a loop.
class FixedRouteEngine:
    IDLE      = "閒置"
    RUNNING   = "執行固定路線中"
    RETURNING = "回到起點中"

    def __init__(self, log_fn=print, state_fn=None, route=None):
        """route defaults to config.FIXED_ROUTE (the full loop); pass e.g.
        config.FIXED_ROUTE_TOP to run just one piece on its own (for testing/
        tuning), still looping + returning home the same way. Whether this is
        the full loop (vs a single-piece test) also decides how long to rest
        after each lap — see FIXED_ROUTE_FULL_REST_SECONDS/FIXED_ROUTE_REST_SECONDS."""
        self.log = log_fn
        self.set_state_cb = state_fn
        self._state = self.IDLE
        self._running = False
        self._is_full_route = route is None
        self._route = route if route is not None else config.FIXED_ROUTE

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
        self.log("固定路線 Bot 啟動")
        self._run_loop()

    def stop(self):
        self._running = False
        self.state = self.IDLE
        self.log("固定路線 Bot 暫停")

    def _stopped(self):
        return not self._running

    def _run_loop(self):
        self.state = self.RUNNING
        try:
            self._run_loop_body()
        except Exception:
            self.log("發生未預期的錯誤，Bot 已自動停止：\n" + traceback.format_exc())
            self._running = False
            self.state = self.IDLE

    def _run_loop_body(self):
        while self._running:
            for i, step in enumerate(self._route):
                if self._stopped():
                    return
                self._run_step(i, step)

            if self._stopped():
                return

            # Each route already ends with its own reverse-path move steps
            # (see config._reverse_home_moves) that walk back to the start —
            # no image-recognition go_home() here, just reset the drift
            # estimate since we should be back at zero.
            self.log("整個區塊跑完一輪")
            reset_position()

            if self._stopped():
                return

            rest_seconds = config.FIXED_ROUTE_FULL_REST_SECONDS if self._is_full_route else config.FIXED_ROUTE_REST_SECONDS
            self.state = self.RETURNING
            self.log(f"回到起點，休息 {rest_seconds} 秒")
            for remaining in range(rest_seconds, 0, -1):
                if self._stopped():
                    return
                if self.set_state_cb:
                    self.set_state_cb(f"休息中（{remaining}s）")
                time.sleep(1)

            if self._stopped():
                return
            self.state = self.RUNNING

    def _run_step(self, index, step):
        step_type = step["type"]
        total = len(self._route)
        if step_type == "move":
            direction, duration = step["direction"], step["duration"]
            direction_label = direction if isinstance(direction, str) else "+".join(direction)
            self.log(f"[{index+1}/{total}] 固定移動：{direction_label} {duration}s")
            _hold_point(direction, duration)
            time.sleep(0.1)
        elif step_type == "collect":
            action = step["action"]
            point = config.COLLECT_POINTS[action]
            times = step.get("times", 5)
            interval = step.get("interval", 0.4)
            self.log(f"[{index+1}/{total}] 固定採集：{action} × {times}")
            for _ in range(times):
                if self._stopped():
                    return
                pyautogui.click(*point)
                time.sleep(interval)
        elif step_type == "go_home":
            self.log(f"[{index+1}/{total}] 依偏移量回到原點")
            go_home(self._stopped, self.log)
            reset_position()   # we should be back at "home" now — treat this as the new zero
        else:
            raise ValueError(f"FIXED_ROUTE 步驟 {index} 的 type 不是 move/collect/go_home：{step_type!r}")
