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

# ── Control scheme: on-screen buttons clicked with the mouse ─────
# The game doesn't accept simulated keyboard input, so movement/turning and
# collect actions are done by clicking/holding fixed on-screen button
# coordinates with pyautogui's mouse functions instead of keyDown/press.
#
# Find each button's (x, y): move the mouse over it, wait a moment, then read
# pyautogui.position(). These coordinates are tied to your current screen
# resolution and the game window's position/size — redo this if either changes.
#
# In this game, holding a direction button also turns the character to face
# that direction (there's no separate turn button).
MOVE_POINTS = {
    "up":    (292, 811),
    "down":  (286, 944),
    "left":  (220, 880),
    "right": (355, 881),
}

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
SCAN_WHILE_MOVING = 0.08

# Within this many px of screen center counts as "arrived"
REACH_RADIUS = 100

# ── Collect verification ────────────────────────────────────
COLLECT_VERIFY_DELAY = 0.8   # Seconds to wait after pressing the collect key before checking if the material vanished
COLLECT_RETRY_MAX    = 2     # Max re tries if collecting fails

# ── Realign after a failed collect ──────────────────────────
# The movement buttons double as facing direction, so realigning first taps
# the direction button that faces the material; if already facing correctly
# but still can't collect, it cycles through strafing / advance-retreat to
# shake free of a stuck position.
REALIGN_BACK_DURATION   = 0.4    # Back-off duration (seconds)
REALIGN_STRAFE_DURATION = 0.25   # Strafe/turn duration (seconds)

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
RESPAWN_WAIT    = 30     # Wait time after collecting, for respawn (seconds)

# ── Idling when no material is found ────────────────────────
# True: return to "home" and idle there, only re-scanning every
#       IDLE_SCAN_INTERVAL seconds
# False: use the old SEARCH_PATTERN to wander around looking for materials
RETURN_HOME_WHEN_IDLE = True
IDLE_SCAN_INTERVAL    = 20   # How often to scan for a respawned material while idling (seconds)

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
