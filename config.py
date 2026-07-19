# ── All adjustable settings ────────────────────────────────

# Hotkeys (these are read from your real keyboard by the `keyboard` library
# to control the bot/tooling — unrelated to the mouse-click controls below,
# which is what actually gets sent to the game)
HOTKEY_START = "f1"
HOTKEY_STOP  = "f2"
# Debug: after pressing this, hover the mouse over a button in the game and
# wait — the GUI logs the mouse's screen position so you can update
# MOVE_POINTS/COLLECT_POINTS/JUMP_POINT later without editing any code.
HOTKEY_DEBUG = "f3"
DEBUG_POSITION_DELAY = 3   # Seconds to wait after pressing the debug hotkey before reading the mouse position

# Fixed-route mode only: run just one piece (see FIXED_ROUTE_TOP/RIGHT/LEFT/BOTTOM
# below) on its own — for testing/tuning one piece at a time instead of
# waiting through the whole loop. F2 (HOTKEY_STOP) stops these the same way.
HOTKEY_TEST_TOP    = "f5"
HOTKEY_TEST_RIGHT  = "f6"
HOTKEY_TEST_LEFT   = "f7"
HOTKEY_TEST_BOTTOM = "f8"

# ── Material settings (each material configured independently) ──
# Only "big tree" is collected (small/medium trees are skipped); the four ore
# types share the same collect action.
# For image paths, use capture_helper.py to capture a screenshot — it will
# ask which material/facing you're capturing and name the files for you.
#
# "image" can also be a list, meaning "multiple templates for the same thing"
# — e.g. if a material has a sway animation or looks different under
# different lighting, capture a few more screenshots and list them all; a
# match against any one of them counts as a hit:
#   "image": ["images/tree_big_1.png", "images/tree_big_2.png"],
#
# "collect_action" refers to a name in COLLECT_POINTS below (the on-screen
# button to click), not a keyboard key.
MATERIALS = [
    {
        "image":            ["images/tree_big_1.png", "images/tree_big_2.png", "images/tree_big_3.png"],   # Big tree
        "collect_action":   "lumber",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            ["images/ore_stone_1.png"],  # Stone ore
        "collect_action":   "ore",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            ["images/ore_stone_1.png"], # Copper ore
        "collect_action":   "ore",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            ["images/ore_stone_1.png"], # Silver ore
        "collect_action":   "ore",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
    {
        "image":            ["images/ore_stone_1.png"],   # Gold ore
        "collect_action":   "ore",
        "collect_times":    5,
        "collect_interval": 0.4,
    },
]

# Image match confidence threshold, 0.0~1.0
MATCH_THRESHOLD = 0.75

# Scan region: None = full screen, or (left, top, right, bottom)
SCAN_REGION = None

# ── Control scheme: movement (keyboard or on-screen mouse buttons) ─────
# Plain simulated keyboard (pyautogui.keyDown/press, the `keyboard` package's
# .press()) gets ignored by this game — those send virtual-key-code input via
# SendInput, which this game (or its emulator layer) filters out. Real
# keyboard presses work fine (see record_route.py). USE_KEYBOARD_MOVEMENT
# lets _hold_point() (engine.py) try a third option: pydirectinput, which
# also uses SendInput but injects hardware SCAN codes instead of virtual-key
# codes — close enough to "real" that some games/emulators accept it even
# though they reject plain simulated keyboard. Flip to False to fall back to
# the original mouse-drag-on-a-virtual-D-pad scheme (MOVE_ORIGIN/MOVE_POINTS
# below) if scan-code input turns out not to register either.
USE_KEYBOARD_MOVEMENT = True
MOVE_KEYS = {"up": "w", "down": "s", "left": "a", "right": "d"}

# Only used when USE_KEYBOARD_MOVEMENT is False. Find each button's (x, y):
# move the mouse over it, wait a moment, then read pyautogui.position().
# These coordinates are tied to your current screen resolution and the game
# window's position/size — redo this if either changes.
#
# In this game, holding a direction button also turns the character to face
# that direction (there's no separate turn button).
MOVE_ORIGIN = (289, 877)
MOVE_POINTS = {
    "up":    (292, 811),
    "down":  (286, 944),
    "left":  (220, 880),
    "right": (355, 881),
}

MOVE_PULSE = 0.1

# Named collect-action buttons. Each material's "collect_action" above refers
# to one of these names.
COLLECT_POINTS = {
    "lumber": (1531, 881),   # 伐木
    "ore":    (1577, 773),   # 採礦
}

# Optional jump button used when trying to escape being stuck; leave as None
# to skip the jump step entirely (there's no keyboard jump fallback anymore).
JUMP_POINT = None   # e.g. (x, y)

# Scan frequency while moving (seconds), 0.05~0.15 recommended
SCAN_WHILE_MOVING = 0.02

# Within this many px of screen center counts as "arrived"
REACH_RADIUS = 100

# Consecutive scan misses tolerated while approaching before giving up on the
# target (a single missed tick — e.g. the character's own sprite briefly
# occluding it — shouldn't abort an otherwise-successful approach)
APPROACH_MISS_TOLERANCE = 2

# If the target permanently disappears (misses exceed APPROACH_MISS_TOLERANCE)
# but it was already within REACH_RADIUS * this factor on the last successful
# reading, treat that as arrival instead of failure — most likely it vanished
# because we got close enough for our own character sprite to cover it, not
# because it actually moved away. Applies to both material approach and
# landmark-based go_home navigation (they share this same movement loop).
APPROACH_DISAPPEAR_ARRIVAL_FACTOR = 2.0

# ── Collect verification ────────────────────────────────────
COLLECT_VERIFY_DELAY = 0.8   # Seconds to wait after pressing the collect key before checking if the material vanished
COLLECT_RETRY_MAX    = 2     # Max re tries if collecting fails

# ── Realign after a failed collect ──────────────────────────
# The movement buttons double as facing direction, so realigning first taps
# the direction button that faces the material; if already facing correctly
# but still can't collect, it runs one of the strategies below to try to
# shake free of a stuck position.
#
# Each strategy is a sequence of (role, duration_multiplier) steps, run in
# order. role is one of:
#   "toward" — the direction that faces the material (dominant axis)
#   "away"   — the opposite of "toward"
#   "side1"/"side2" — the two directions perpendicular to "toward"
# Duration for each step = REALIGN_STEP_DURATION * duration_multiplier
# seconds of button-hold time. Only one direction can be held at once (see
# MOVE_POINTS notes above), so a "diagonal" nudge is approximated as two
# sequential holds (e.g. toward then side1), not a simultaneous press.
#
# The same strategy is retried REALIGN_STRATEGY_REPEAT times (counted across
# collect_with_verify calls at the same spot, via the stuck tracker — not
# just within one round) before moving on to the next strategy in the list.
REALIGN_STEP_DURATION = 0.12   # Base hold duration unit (seconds) for realign strategies

REALIGN_STRATEGIES = [
    [("toward", 1.0)],                     # A：往素材方向走一小步（可能只是差一點距離）
    [("toward", 1.0), ("side1", 0.7)],     # B：往素材方向 + 往一側（近似斜向切入）
    [("toward", 1.0), ("away", 1.0)],      # C：前進後退，甩脫卡在邊緣的碰撞
    [("side1", 1.0), ("side2", 1.0)],      # D：左右／上下側移
    [("away", 1.0), ("side2", 1.0)],       # E：先退後，再往另一側
]
REALIGN_STRATEGY_REPEAT = 2   # 同一個策略連續嘗試幾次，才換下一個

# ── Character facing detection (advanced, optional) ─────────
# Normally facing is estimated from "the last direction button pressed",
# which is usually good enough. But if the character gets blocked by terrain
# and a direction press doesn't actually turn/move it, the estimate can drift
# from reality.
# For more accuracy, use capture_helper.py to capture freeze-frames of the
# character facing up/down/left/right, save them under the filenames below,
# and fill in CHARACTER_CROP (the character's area on screen). Both must be
# set to enable screenshot-based comparison; otherwise it keeps using the
# key-press estimate.
# Just like MATERIALS, each direction can also be a list (e.g. multiple
# frames of an idle/walk animation):
#   "up": ["images/facing_up_1.png", "images/facing_up_2.png"],
CHARACTER_CROP = None     # e.g. (860, 440, 1060, 640)
FACING_IMAGES = {
    # "up":    "images/facing_up.png",
    # "down":  "images/facing_down.png",
    # "left":  "images/facing_left.png",
    # "right": "images/facing_right.png",
}

# ── Persistent collect failure at the same spot ─────────────
# Normally realigning uses the cheap key-press facing estimate. Only once the
# same material (position within tolerance) has failed
# STUCK_FAIL_THRESHOLD times in a row does it switch to screenshot-based
# facing detection (if CHARACTER_CROP/FACING_IMAGES are set — the two
# approaches coexist: estimate by default, screenshot once stuck).
# If even screenshot detection can't save it and failures reach
# STUCK_GIVE_UP_THRESHOLD, that spot is temporarily abandoned — it won't be
# picked as a target again for STUCK_QUARANTINE_SECONDS, and the bot looks
# for another material instead.
SAME_MATERIAL_TOLERANCE  = 40    # Within this many px counts as the same material
STUCK_FAIL_THRESHOLD     = 2     # After this many consecutive failures at the same spot, prefer screenshot-based facing detection
STUCK_GIVE_UP_THRESHOLD  = 4     # After this many consecutive failures, temporarily give up on this spot
STUCK_QUARANTINE_SECONDS = 120   # How long (seconds) a given-up spot stays excluded from targeting

# ── Stuck detection ──────────────────────────────────────────
STUCK_TIMEOUT           = 3.0   # Seconds without movement before considered stuck
STUCK_MOVEMENT_THRESHOLD = 5    # Movement below this many px counts as "not moved"
STUCK_ESCAPE_DURATION   = 0.4   # How long to move in each escape direction (seconds)
STUCK_MAX_ATTEMPTS      = 3     # Max number of escape attempts

# ── Loop settings ────────────────────────────────────────────
SCAN_INTERVAL   = 1.0    # Interval between scans (seconds)

# ── Idling when no material is found ────────────────────────
# True: return to "home" and idle there, only re-scanning every
#       IDLE_SCAN_INTERVAL seconds
# False: use the old SEARCH_PATTERN to wander around looking for materials
RETURN_HOME_WHEN_IDLE = True
IDLE_SCAN_INTERVAL    = 1   # How often to scan for a respawned material while idling (seconds)

# ── How "home" is found ──────────────────────────────────────
# Option A (default, no setup): "home" is wherever the character stood when
# the bot started, tracked by accumulating button-hold seconds — an
# approximation that can drift over time (see README's "known limitations").
#
# Option B (more reliable, no config editing needed): capture a fixed,
# recognizable landmark near where you want to idle (a rock, building
# corner, distinctive ground texture — anything static and unique) with
# capture_helper.py's "home_landmark" category, while standing exactly where
# you want home to be. That tool automatically writes images/home_landmark.json
# (the image(s) + offset from screen center) — nothing to paste in here. Once
# that file exists, the bot walks by tracking the landmark's on-screen
# position instead of the accumulated estimate — no drift, but falls back to
# the estimate if the landmark isn't visible (e.g. too far away).
HOME_REACH_RADIUS = 40   # Within this many px of the target counts as "arrived home"

# Used when no material is found and RETURN_HOME_WHEN_IDLE = False
SEARCH_DURATION = 3.0    # How long to wander when no material is found (seconds)
SEARCH_PATTERN  = ["up", "right", "down", "left"]

# ── Fixed movement route (alternative to image-recognition mode) ──────
# A literal, hand-authored script — walk a fixed direction for a fixed
# duration, then collect, repeat, until the whole area has been swept once —
# with no image matching involved at all (unlike MATERIALS above). Pick this
# mode from the GUI's mode dropdown when you'd rather author the exact path
# yourself than rely on detection (e.g. a densely-packed area).
#
# Each step is one of:
#   {"type": "move", "direction": "up"/"down"/"left"/"right", "duration": <seconds>}
#   {"type": "collect", "action": <name in COLLECT_POINTS>, "times": <clicks>, "interval": <seconds between clicks>}
#
# Movement duration works the same way as everywhere else in this file: it's
# seconds of button-hold time, not a pixel distance — so a step's real-world
# length only ever needs re-tuning if your character's move speed changes.
#
# After the list finishes once, the bot walks back to wherever it started
# (same "回中心" logic as image-recognition mode's idle return — landmark
# navigation if images/home_landmark.json exists, otherwise the estimated
# button-hold-seconds position) and starts the list again from the top,
# looping until you press stop.
#
# ── Example: a diamond-shaped area, cut into 4 by its own diagonals (an "X") ──
# Moving in a diagonal pair like "left then up" repeated traces a line
# parallel to one edge of a diamond; "left then down" (the other diagonal)
# traces a line parallel to the other edge. Those same two diagonal axes are
# also exactly the diamond's own two diagonals (connecting midpoints of
# opposite edges through the center) — cutting along both at once is an "X"
# through the center, and splits the diamond into 4 *smaller diamonds*, each
# pointing at one of the 4 original vertices (top/right/bottom/left) — not
# the 4 compass quadrants you'd get by cutting along plain up/down/left/right.
#
# top + right = trees, left + bottom = ore, each swept independently from the
# center outward, then back to center (same "回中心" logic used elsewhere —
# landmark navigation if images/home_landmark.json exists, otherwise the
# estimated position) before moving to the next one. Order: top -> right ->
# left -> bottom, then the whole thing loops from the top.
#
# Tune these per area — the route is generated from them, edit these instead
# of the generated steps directly. The step durations especially need real
# testing before trusting a full sweep: temporarily set both RADIUS values to
# 1 (a quick few-stop sweep per piece) and watch how far one step actually
# moves the character, then tune duration and only bump RADIUS back up once a
# single step looks right — too long a duration way overshoots each cell.
FIXED_ROUTE_TREE_RADIUS      = 2        # Top/right (tree) pieces: steps from center to that piece's tip — trees are laid out 3x3 (radius+1 per side)
FIXED_ROUTE_TREE_STEP        = 0.15     # Seconds held per half-step in the tree pieces (down/left/right)
FIXED_ROUTE_TREE_STEP_UP     = 0.22     # "up" specifically — in testing, plain up/down/left/right steps landed fine for the first few
                                         # cells, but by the row furthest from center the position had drifted short, always short in
                                         # the "up" direction specifically. Real movement apparently covers less distance per held-
                                         # second going up than the other 3 directions, so "up" gets its own, longer duration here
                                         # rather than inflating every direction (which would overshoot down/left/right instead).
FIXED_ROUTE_TREE_ACTION      = "lumber" # Name in COLLECT_POINTS for the tree pieces
FIXED_ROUTE_ORE_RADIUS       = 3        # Left/bottom (ore) pieces: steps from center to that piece's tip
FIXED_ROUTE_ORE_STEP         = 0.08     # Smaller than the tree step — ore is packed tighter
FIXED_ROUTE_ORE_ACTION       = "ore"    # Name in COLLECT_POINTS for the ore pieces
FIXED_ROUTE_COLLECT_TIMES    = 5
FIXED_ROUTE_COLLECT_INTERVAL = 0.4

FIXED_ROUTE_REST_SECONDS      = 780  # Single-piece test (F5/F6/F7/F8): pause after that one piece returns to origin, before looping it again (13 min, for now)
FIXED_ROUTE_FULL_REST_SECONDS = 780  # Full route (F1, all 4 pieces): pause after the whole TOP+RIGHT+LEFT+BOTTOM lap returns to origin, before starting the next lap (13 min, for now)

def _step_durations(base, up=None, down=None, left=None, right=None):
    """Per-cardinal-direction step duration map, defaulting unset directions to `base`."""
    return {
        "up": base if up is None else up,
        "down": base if down is None else down,
        "left": base if left is None else left,
        "right": base if right is None else right,
    }

FIXED_ROUTE_TREE_STEP_DURATIONS = _step_durations(FIXED_ROUTE_TREE_STEP, up=FIXED_ROUTE_TREE_STEP_UP)
FIXED_ROUTE_ORE_STEP_DURATIONS  = _step_durations(FIXED_ROUTE_ORE_STEP)

# Per-piece pre-sweep offset — one-off moves executed once, BEFORE that
# piece's very first collect (the center itself is never actually reachable —
# the nearest material always sits some distance out, so every piece has to
# step out before attempting to collect at all, not just the trees). Two
# things go here, and they need independent tuning per piece (what fixes one
# piece does nothing — or the wrong amount — for another, since each piece's
# own move sequence accumulates real-world drift differently):
#  1. Closing the gap between center and where that piece's resources
#     actually start — each piece's natural outward direction (the one
#     pointing straight at that piece's own diamond vertex — see the vertex
#     names in the FIXED_ROUTE assembly below) gets one big plain step here,
#     instead of changing FIXED_ROUTE_TREE_STEP/ORE_STEP, which would also
#     change the spacing between every cell in the grid, not just this gap.
#  2. Real-world movement drift compensation, stacked after the gap step
#     above — in testing, a piece's whole executed footprint landed shifted
#     from where the button sequence should have put it (the generated step
#     counts are exactly symmetric, so this is a real movement bias, not a
#     bug in the sweep pattern).
# Each is a list of (direction, duration) tuples, applied in order; empty
# list = no offset. This offset is real movement (goes through the same
# button-hold tracking as everything else), so `go_home` between pieces
# already accounts for it automatically.
FIXED_ROUTE_TOP_OFFSET    = [("up", 0.45)]                  # gap to the trees — still tuning, bump further if still short
FIXED_ROUTE_RIGHT_OFFSET  = [("right", 0.3), ("up", 0.15)]  # gap to the trees, then a small drift correction (cancels the "too far down-right" you saw)
FIXED_ROUTE_LEFT_OFFSET   = [("left", 0.2)]                 # gap to the ore — untested guess, tune once you see this piece run
FIXED_ROUTE_BOTTOM_OFFSET = [("down", 0.2)]                 # gap to the ore — untested guess, tune once you see this piece run

# The four diagonals, each as two sequential cardinal half-steps — only one
# direction button can be held at a time (see MOVE_POINTS notes above), so a
# true simultaneous diagonal press isn't possible; two quick holds in a row
# approximates it well enough.
_NE = ("up", "right")
_SW = ("down", "left")
_NW = ("up", "left")
_SE = ("down", "right")

def _diag_step(cardinal_pair, step_durations):
    return [{"type": "move", "direction": d, "duration": step_durations[d]} for d in cardinal_pair]

def _collect_step(action, times, interval):
    return [{"type": "collect", "action": action, "times": times, "interval": interval}]

def _build_diamond_piece_route(radius, row_dir, sweep_a, sweep_b, step_durations, collect_action, offset):
    """
    Sweep one of the 4 pieces the X-cut makes. In the diagonal (NE/SW,
    NW/SE) axes each piece is simply a plain (radius+1) x (radius+1) square
    with the center as one of its corners — no spiraling/widening rows
    needed (unlike a triangle): a standard boustrophedon starting right at
    that corner covers it exactly. row_dir moves to the next row (further
    from center, along whichever diagonal axis isn't being swept within a
    row); sweep_a/sweep_b are the two directions of the other diagonal axis,
    alternating each row. Every move is immediately followed by a collect,
    except `offset` (a gap-closing / drift-correction pre-move — see above).
    step_durations is a {"up"/"down"/"left"/"right": seconds} map, since the
    same hold duration doesn't necessarily cover the same real distance in
    every direction (see FIXED_ROUTE_TREE_STEP_UP above).
    """
    def diag(pair):
        return _diag_step(pair, step_durations)

    def collect():
        return _collect_step(collect_action, FIXED_ROUTE_COLLECT_TIMES, FIXED_ROUTE_COLLECT_INTERVAL)

    # Pre-sweep offset first — a plain gap-closing/calibration move, not a grid cell, so no collect after it
    route = [{"type": "move", "direction": d, "duration": dur} for d, dur in offset]
    route += collect()   # the center itself (now shifted by the offset above) — one corner of this piece
    sweep_toward_a = True
    for row in range(radius + 1):
        if row > 0:
            route += diag(row_dir)
            route += collect()
        sweep_dir = sweep_a if sweep_toward_a else sweep_b
        for _ in range(radius):
            route += diag(sweep_dir)
            route += collect()
        sweep_toward_a = not sweep_toward_a

    return route

# Each piece exposed on its own (not just baked into FIXED_ROUTE below) so a
# single piece can be run in isolation — see HOTKEY_TEST_TOP/RIGHT/LEFT/BOTTOM.
# Every piece is a full there-and-back sequence: real moves out, then a
# literal reversed-move sequence back to center — no image recognition
# involved at all anymore (go_home()'s landmark matching proved too
# unreliable in testing, so it's temporarily out of the picture for
# FIXED_ROUTE entirely). The return path is just every outbound move step
# played back in reverse order with the opposite direction, so it's
# automatically correct for however the outbound path actually went — you
# don't hand-author a separate return route.
_OPPOSITE_DIRECTION = {"up": "down", "down": "up", "left": "right", "right": "left"}

def _scale_moves(route, scale):
    """Copy of route with every move step's duration multiplied by scale (collect steps untouched)."""
    return [
        {**step, "duration": round(step["duration"] * scale, 3)} if step["type"] == "move" else step
        for step in route
    ]

def _opposite(direction):
    """direction is a single direction string, or a list (simultaneous keys held together, e.g. a recorded diagonal)."""
    if isinstance(direction, str):
        return _OPPOSITE_DIRECTION[direction]
    return [_OPPOSITE_DIRECTION[d] for d in direction]

def _reverse_home_moves(route):
    """
    Literal 'walk back to center' moves: every move step in route, reversed
    order and direction, same duration, no image recognition. Movement
    distance is proportional to hold duration the same way in all 4
    directions, so mirroring direction+duration exactly is enough to cancel
    out any outbound displacement. Diagonal (multi-direction) steps mirror
    the same way, just with every direction in the list flipped.
    """
    reversed_moves = []
    for step in reversed(route):
        if step["type"] != "move":
            continue
        reversed_moves.append({
            "type": "move",
            "direction": _opposite(step["direction"]),
            "duration": step["duration"],
        })
    return reversed_moves

# Recorded move durations are measured from real keyboard presses
# (record_route.py). Under the old mouse-drag replay scheme (USE_KEYBOARD_MOVEMENT
# = False), replay covered more distance per held-second than the recording
# implied, so this got tuned down through 0.8 → 0.7 → 0.6 → 0.5 → 0.55 → 0.7
# → 0.6 trying to compensate (see git history) — none of that tuning applies
# now that USE_KEYBOARD_MOVEMENT replays through real key holds instead of a
# simulated mouse drag: it's keyboard-recorded, keyboard-replayed, so distance
# should already track duration directly. Reset to 1.0 under the keyboard
# scheme, then retuned down to 0.9 after real-game testing still overshot a
# little.
FIXED_ROUTE_RECORDED_SCALE = 0.98

# TOP is still the algorithmically-generated diamond-piece route (tune via
# FIXED_ROUTE_TREE_*/FIXED_ROUTE_TOP_OFFSET above).
_TOP_OUTBOUND = _build_diamond_piece_route(
    FIXED_ROUTE_TREE_RADIUS, _NE, _NW, _SE, FIXED_ROUTE_TREE_STEP_DURATIONS, FIXED_ROUTE_TREE_ACTION, FIXED_ROUTE_TOP_OFFSET
)
FIXED_ROUTE_TOP = [
    {"type": "move", "direction": "left", "duration": 0.02},
    {"type": "move", "direction": ["left", "up"], "duration": 0.454},
    {"type": "move", "direction": ["left", "up"], "duration": 0.029},
    {"type": "move", "direction": ["left", "up"], "duration": 0.017},
    {"type": "move", "direction": "left", "duration": 0.002},
    {"type": "move", "direction": "up", "duration": 0.007},
    {"type": "move", "direction": ["right", "up"], "duration": 0.37},
    {"type": "move", "direction": "up", "duration": 0.014},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.304},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.14},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.017},
    {"type": "move", "direction": ["left", "up"], "duration": 0.446},
    {"type": "move", "direction": "up", "duration": 0.001},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.014},
    {"type": "move", "direction": ["left", "up"], "duration": 0.071},
    {"type": "move", "direction": "up", "duration": 0.009},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.009},
    {"type": "move", "direction": ["right", "up"], "duration": 0.152},
    {"type": "move", "direction": "up", "duration": 0.023},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.059},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.007},
    {"type": "move", "direction": ["down", "right"], "duration": 0.195},
    {"type": "move", "direction": "right", "duration": 0.007},
    {"type": "move", "direction": "right", "duration": 0.117},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.009},
    {"type": "move", "direction": ["down", "right"], "duration": 0.247},
    {"type": "move", "direction": "right", "duration": 0.001},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.088},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.211},
    {"type": "move", "direction": "right", "duration": 0.164},
    {"type": "move", "direction": "right", "duration": 0.069},
    {"type": "move", "direction": "right", "duration": 0.077},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.228},
    {"type": "move", "direction": "up", "duration": 0.204},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.013},
    {"type": "move", "direction": ["left", "up"], "duration": 0.125},
    {"type": "move", "direction": "up", "duration": 0.013},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.011},
    {"type": "move", "direction": ["left", "up"], "duration": 0.052},
    {"type": "move", "direction": "up", "duration": 0.006},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.001},
    {"type": "move", "direction": ["left", "up"], "duration": 0.054},
    {"type": "move", "direction": "up", "duration": 0.013},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.013},
    {"type": "move", "direction": ["right", "down"], "duration": 0.054},
    {"type": "move", "direction": "right", "duration": 0.001},
    {"type": "move", "direction": "down", "duration": 0.006},
    {"type": "move", "direction": ["right", "down"], "duration": 0.052},
    {"type": "move", "direction": "right", "duration": 0.011},
    {"type": "move", "direction": "down", "duration": 0.013},
    {"type": "move", "direction": ["right", "down"], "duration": 0.125},
    {"type": "move", "direction": "right", "duration": 0.013},
    {"type": "move", "direction": "down", "duration": 0.204},
    {"type": "move", "direction": "right", "duration": 0.228},
    {"type": "move", "direction": "left", "duration": 0.077},
    {"type": "move", "direction": "left", "duration": 0.069},
    {"type": "move", "direction": "left", "duration": 0.164},
    {"type": "move", "direction": "down", "duration": 0.211},
    {"type": "move", "direction": "left", "duration": 0.088},
    {"type": "move", "direction": "left", "duration": 0.001},
    {"type": "move", "direction": ["up", "left"], "duration": 0.247},
    {"type": "move", "direction": "up", "duration": 0.009},
    {"type": "move", "direction": "left", "duration": 0.117},
    {"type": "move", "direction": "left", "duration": 0.007},
    {"type": "move", "direction": ["up", "left"], "duration": 0.195},
    {"type": "move", "direction": "up", "duration": 0.007},
    {"type": "move", "direction": "down", "duration": 0.059},
    {"type": "move", "direction": "down", "duration": 0.023},
    {"type": "move", "direction": ["left", "down"], "duration": 0.152},
    {"type": "move", "direction": "down", "duration": 0.009},
    {"type": "move", "direction": "down", "duration": 0.009},
    {"type": "move", "direction": ["right", "down"], "duration": 0.071},
    {"type": "move", "direction": "right", "duration": 0.014},
    {"type": "move", "direction": "down", "duration": 0.001},
    {"type": "move", "direction": ["right", "down"], "duration": 0.446},
    {"type": "move", "direction": "right", "duration": 0.017},
    {"type": "move", "direction": "up", "duration": 0.14},
    {"type": "move", "direction": "left", "duration": 0.304},
    {"type": "move", "direction": "down", "duration": 0.014},
    {"type": "move", "direction": ["left", "down"], "duration": 0.37},
    {"type": "move", "direction": "down", "duration": 0.007},
    {"type": "move", "direction": "right", "duration": 0.002},
    {"type": "move", "direction": ["right", "down"], "duration": 0.017},
    {"type": "move", "direction": ["right", "down"], "duration": 0.029},
    {"type": "move", "direction": ["right", "down"], "duration": 0.454},
    {"type": "move", "direction": "right", "duration": 0.02},
]

# RIGHT/LEFT/BOTTOM are real recordings from record_route.py (see its own
# comments). _RECORDED_RAW keeps the values exactly as recorded (unscaled);
# FIXED_ROUTE_RECORDED_SCALE is applied on top via code so retuning the scale
# doesn't mean re-pasting hundreds of lines. FIXED_ROUTE_RIGHT_OFFSET/
# ORE_RADIUS/ORE_STEP/etc. above no longer apply to these three unless you
# revert a piece back to _build_diamond_piece_route(...).
_RIGHT_RECORDED_RAW = [
    {"type": "move", "direction": "right", "duration": 0.294},
    {"type": "move", "direction": "up", "duration": 0.089},
    {"type": "move", "direction": "right", "duration": 0.106},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.27},
    {"type": "move", "direction": "down", "duration": 0.179},
    {"type": "move", "direction": "right", "duration": 0.105},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.201},
    {"type": "move", "direction": "right", "duration": 0.272},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.197},
    {"type": "move", "direction": "right", "duration": 0.341},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.197},
    {"type": "move", "direction": "up", "duration": 0.133},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.313},
    {"type": "move", "direction": "up", "duration": 0.236},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.252},
    {"type": "move", "direction": "right", "duration": 0.212},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.073},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.129},
    {"type": "move", "direction": "right", "duration": 0.24},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.196},
    {"type": "move", "direction": "right", "duration": 0.331},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.069},
    {"type": "move", "direction": "down", "duration": 0.15},
    {"type": "move", "direction": "left", "duration": 0.014},
    {"type": "move", "direction": "down", "duration": 0.049},
    {"type": "move", "direction": "left", "duration": 0.077},
    {"type": "move", "direction": "right", "duration": 0.059},
    {"type": "move", "direction": "up", "duration": 0.054},
]
_right_outbound = _scale_moves(_RIGHT_RECORDED_RAW, FIXED_ROUTE_RECORDED_SCALE)
FIXED_ROUTE_RIGHT = [
    {"type": "move", "direction": "down", "duration": 0.023},
    {"type": "move", "direction": ["down", "right"], "duration": 0.262},
    {"type": "move", "direction": "right", "duration": 0.016},
    {"type": "move", "direction": "down", "duration": 0.014},
    {"type": "move", "direction": ["down", "right"], "duration": 0.35},
    {"type": "move", "direction": "right", "duration": 0.01},
    {"type": "move", "direction": "down", "duration": 0.001},
    {"type": "move", "direction": ["down", "right"], "duration": 0.222},
    {"type": "move", "direction": "down", "duration": 0.005},
    {"type": "move", "direction": "up", "duration": 0.016},
    {"type": "move", "direction": ["right", "up"], "duration": 0.333},
    {"type": "move", "direction": "up", "duration": 0.017},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.22},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.028},
    {"type": "move", "direction": ["left", "up"], "duration": 0.468},
    {"type": "move", "direction": "up", "duration": 0.011},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.206},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.004},
    {"type": "move", "direction": ["down", "right"], "duration": 0.234},
    {"type": "move", "direction": "right", "duration": 0.01},
    {"type": "move", "direction": "right", "duration": 0.025},
    {"type": "move", "direction": ["right", "up"], "duration": 0.16},
    {"type": "move", "direction": "right", "duration": 0.001},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.193},
    {"type": "move", "direction": "right", "duration": 0.352},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.174},
    {"type": "move", "direction": "up", "duration": 0.141},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.219},
    {"type": "move", "direction": "up", "duration": 0.209},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.22},
    {"type": "move", "direction": "right", "duration": 0.428},
    {"type": "move", "direction": "right", "duration": 0.147},
    {"type": "collect", "action": "lumber", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.147},
    {"type": "move", "direction": "left", "duration": 0.428},
    {"type": "move", "direction": "up", "duration": 0.22},
    {"type": "move", "direction": "down", "duration": 0.209},
    {"type": "move", "direction": "right", "duration": 0.219},
    {"type": "move", "direction": "down", "duration": 0.141},
    {"type": "move", "direction": "down", "duration": 0.174},
    {"type": "move", "direction": "left", "duration": 0.352},
    {"type": "move", "direction": "up", "duration": 0.193},
    {"type": "move", "direction": "left", "duration": 0.001},
    {"type": "move", "direction": ["left", "down"], "duration": 0.16},
    {"type": "move", "direction": "left", "duration": 0.025},
    {"type": "move", "direction": "left", "duration": 0.01},
    {"type": "move", "direction": ["up", "left"], "duration": 0.234},
    {"type": "move", "direction": "left", "duration": 0.004},
    {"type": "move", "direction": "down", "duration": 0.206},
    {"type": "move", "direction": "down", "duration": 0.011},
    {"type": "move", "direction": ["right", "down"], "duration": 0.468},
    {"type": "move", "direction": "right", "duration": 0.028},
    {"type": "move", "direction": "left", "duration": 0.22},
    {"type": "move", "direction": "down", "duration": 0.017},
    {"type": "move", "direction": ["left", "down"], "duration": 0.333},
    {"type": "move", "direction": "down", "duration": 0.016},
    {"type": "move", "direction": "up", "duration": 0.005},
    {"type": "move", "direction": ["up", "left"], "duration": 0.222},
    {"type": "move", "direction": "up", "duration": 0.001},
    {"type": "move", "direction": "left", "duration": 0.01},
    {"type": "move", "direction": ["up", "left"], "duration": 0.35},
    {"type": "move", "direction": "up", "duration": 0.014},
    {"type": "move", "direction": "left", "duration": 0.016},
    {"type": "move", "direction": ["up", "left"], "duration": 0.262},
    {"type": "move", "direction": "up", "duration": 0.023},
]

_LEFT_RECORDED_RAW = [
    {"type": "move", "direction": "left", "duration": 0.116},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.12},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.137},
    {"type": "move", "direction": "left", "duration": 0.112},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.164},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.228},
    {"type": "move", "direction": "up", "duration": 0.132},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.119},
    {"type": "move", "direction": "left", "duration": 0.112},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.072},
    {"type": "move", "direction": "left", "duration": 0.184},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.149},
    {"type": "move", "direction": "down", "duration": 0.141},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.216},
    {"type": "move", "direction": "down", "duration": 0.108},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.146},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.156},
    {"type": "move", "direction": "down", "duration": 0.106},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.114},
    {"type": "move", "direction": "right", "duration": 0.135},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.184},
    {"type": "move", "direction": "down", "duration": 0.106},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.197},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.195},
    {"type": "move", "direction": "down", "duration": 0.137},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.118},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.15},
    {"type": "move", "direction": "left", "duration": 0.121},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.188},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.181},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.099},
    {"type": "move", "direction": "left", "duration": 0.18},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.112},
    {"type": "move", "direction": "left", "duration": 0.222},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.136},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.168},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.1},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.153},
    {"type": "move", "direction": "right", "duration": 0.139},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.143},
    {"type": "move", "direction": "right", "duration": 0.26},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.131},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.49},
    {"type": "move", "direction": "right", "duration": 0.443},
    {"type": "move", "direction": "up", "duration": 0.199},
    {"type": "move", "direction": "right", "duration": 0.426},
    {"type": "move", "direction": "down", "duration": 0.193},
    {"type": "move", "direction": "right", "duration": 0.094},
    {"type": "move", "direction": "up", "duration": 0.088},
]
_left_outbound = _scale_moves(_LEFT_RECORDED_RAW, FIXED_ROUTE_RECORDED_SCALE)
FIXED_ROUTE_LEFT = [
    {"type": "move", "direction": "left", "duration": 0.225},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.205},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.123},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.274},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.166},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.206},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.164},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.218},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.164},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.233},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.133},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.213},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.179},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.165},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.141},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.172},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.135},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.158},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.133},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.137},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.172},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.172},
    {"type": "move", "direction": "down", "duration": 0.137},
    {"type": "move", "direction": "left", "duration": 0.133},
    {"type": "move", "direction": "up", "duration": 0.158},
    {"type": "move", "direction": "left", "duration": 0.135},
    {"type": "move", "direction": "up", "duration": 0.172},
    {"type": "move", "direction": "up", "duration": 0.141},
    {"type": "move", "direction": "left", "duration": 0.165},
    {"type": "move", "direction": "up", "duration": 0.179},
    {"type": "move", "direction": "right", "duration": 0.213},
    {"type": "move", "direction": "up", "duration": 0.133},
    {"type": "move", "direction": "right", "duration": 0.233},
    {"type": "move", "direction": "up", "duration": 0.164},
    {"type": "move", "direction": "right", "duration": 0.218},
    {"type": "move", "direction": "down", "duration": 0.164},
    {"type": "move", "direction": "right", "duration": 0.206},
    {"type": "move", "direction": "down", "duration": 0.166},
    {"type": "move", "direction": "right", "duration": 0.274},
    {"type": "move", "direction": "down", "duration": 0.123},
    {"type": "move", "direction": "right", "duration": 0.205},
    {"type": "move", "direction": "right", "duration": 0.225},
]

_BOTTOM_RECORDED_RAW = [
    {"type": "move", "direction": "down", "duration": 0.099},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.186},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.149},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.214},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.133},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.147},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.135},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.182},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.202},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.182},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.153},
    {"type": "move", "direction": "up", "duration": 0.118},
    {"type": "move", "direction": "left", "duration": 0.122},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.199},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.178},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.171},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.158},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.252},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.167},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.153},
    {"type": "move", "direction": "down", "duration": 0.14},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.124},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.168},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.211},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.199},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.141},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.158},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.144},
    {"type": "move", "direction": "right", "duration": 0.127},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.152},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.167},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.138},
    {"type": "move", "direction": "left", "duration": 0.128},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.135},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.179},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.136},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.26},
    {"type": "move", "direction": "left", "duration": 0.112},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.13},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.104},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.157},
    {"type": "move", "direction": "right", "duration": 0.14},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.098},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.199},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.147},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.133},
    {"type": "move", "direction": "down", "duration": 0.193},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.156},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.107},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.053},
    {"type": "move", "direction": "right", "duration": 0.091},
    {"type": "move", "direction": "right", "duration": 0.06},
    {"type": "move", "direction": "up", "duration": 0.986},
    {"type": "move", "direction": "left", "duration": 0.044},
    {"type": "move", "direction": "left", "duration": 0.057},
    {"type": "move", "direction": "up", "duration": 0.328},
    {"type": "move", "direction": "up", "duration": 0.138},
    {"type": "move", "direction": "right", "duration": 0.064},
    {"type": "move", "direction": "up", "duration": 0.046},
]
_bottom_outbound = _scale_moves(_BOTTOM_RECORDED_RAW, FIXED_ROUTE_RECORDED_SCALE)
FIXED_ROUTE_BOTTOM = [
    {"type": "move", "direction": "down", "duration": 0.224},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.188},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.117},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.102},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.175},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.112},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.133},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.132},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.087},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.124},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.123},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.173},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.139},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.163},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.159},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.162},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.164},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.089},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.129},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.13},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.118},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.128},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.147},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "right", "duration": 0.155},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.139},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "left", "duration": 0.158},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "down", "duration": 0.141},
    {"type": "collect", "action": "ore", "times": 1, "interval": 0.4},
    {"type": "move", "direction": "up", "duration": 0.141},
    {"type": "move", "direction": "right", "duration": 0.158},
    {"type": "move", "direction": "up", "duration": 0.139},
    {"type": "move", "direction": "left", "duration": 0.155},
    {"type": "move", "direction": "left", "duration": 0.147},
    {"type": "move", "direction": "left", "duration": 0.128},
    {"type": "move", "direction": "left", "duration": 0.118},
    {"type": "move", "direction": "up", "duration": 0.13},
    {"type": "move", "direction": "up", "duration": 0.129},
    {"type": "move", "direction": "right", "duration": 0.089},
    {"type": "move", "direction": "right", "duration": 0.164},
    {"type": "move", "direction": "right", "duration": 0.162},
    {"type": "move", "direction": "right", "duration": 0.159},
    {"type": "move", "direction": "right", "duration": 0.163},
    {"type": "move", "direction": "right", "duration": 0.139},
    {"type": "move", "direction": "right", "duration": 0.173},
    {"type": "move", "direction": "up", "duration": 0.123},
    {"type": "move", "direction": "left", "duration": 0.124},
    {"type": "move", "direction": "up", "duration": 0.087},
    {"type": "move", "direction": "left", "duration": 0.132},
    {"type": "move", "direction": "up", "duration": 0.133},
    {"type": "move", "direction": "left", "duration": 0.112},
    {"type": "move", "direction": "up", "duration": 0.175},
    {"type": "move", "direction": "left", "duration": 0.102},
    {"type": "move", "direction": "left", "duration": 0.117},
    {"type": "move", "direction": "up", "duration": 0.188},
    {"type": "move", "direction": "up", "duration": 0.224},
]

FIXED_ROUTE = FIXED_ROUTE_TOP + FIXED_ROUTE_RIGHT + FIXED_ROUTE_LEFT + FIXED_ROUTE_BOTTOM

# ── Route recorder (record_route.py) ──────────────────────────────────
# The game accepts genuine hardware keyboard input for movement (it only
# rejects *simulated*/automated key presses — see bot.py's admin-elevation
# comment), so instead of guessing FIXED_ROUTE hold-durations by trial and
# error, record_route.py lets you physically play through a route once and
# records exactly how long you held each direction key and how many times /
# how far apart you pressed the collect key(s), then prints that timeline
# straight out in FIXED_ROUTE's own step format — paste the result over the
# FIXED_ROUTE assembly above (or a piece of it) to use it as-is.
#
# Adjust these to match your own in-game keybinds before recording — key
# names follow the `keyboard` package's naming (arrow keys are "up"/"down"/
# "left"/"right"; letter keys are just the letter, e.g. "w").
RECORD_MOVE_KEYS = {
    "w": "up", "a": "left", "s": "down", "d": "right",   # 移動用 WASD
}
RECORD_COLLECT_KEYS = {
    "2": "lumber",   # 採集樹木
    "3": "ore",      # 採集礦石
}
# Consecutive presses of the *same* collect key within this many seconds of
# each other are grouped into a single recorded {"type": "collect", "times":
# N, ...} step (one burst of clicks at one spot), instead of N separate steps.
RECORD_COLLECT_GROUP_GAP = 1.0
