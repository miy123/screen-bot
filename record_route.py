"""
Record a real playthrough of a route (one piece at a time) and convert it
into FIXED_ROUTE steps.

The game accepts genuine hardware keyboard input for movement (it only
rejects simulated/automated key presses — same reason bot.py needs admin
rights, see its own comment). So instead of guessing FIXED_ROUTE's
move/collect durations by trial and error, physically play through a piece
of the route once with this running: it records exactly how long you held
each direction key and how many times / how far apart you pressed the
collect key(s), then prints that timeline straight out in FIXED_ROUTE's
own step format. Holding two move keys together (e.g. W+D for a real
diagonal) is captured correctly too — as one step with a list of directions
held simultaneously — instead of being flattened into two sequential
full-duration moves that would lose the diagonal (see _merge_move_segments).
Each recorded piece automatically gets a literal reverse path appended
(every recorded move played back in reverse order with the opposite
direction(s)) to walk back to center — no image recognition / go_home() call
involved, since that proved unreliable in testing. The recorded move
durations are also scaled by config.FIXED_ROUTE_RECORDED_SCALE first, in
case replay doesn't cover quite the same distance per held-second as these
real keyboard presses did.

Run: python record_route.py
  Pick which piece (top/right/left/bottom, or finish) from the menu
  F1 (config.HOTKEY_START) : start recording that piece
  F2 (config.HOTKEY_STOP)  : stop recording that piece
  Repeat for as many pieces as you want to record in this session, then
  choose "finish" to print/save everything recorded so far — you'll then be
  asked whether to apply the results straight into config.py's
  FIXED_ROUTE_TOP/RIGHT/LEFT/BOTTOM (replacing whatever was there before,
  generated or previously recorded) instead of pasting them in by hand.

Before running, adjust config.RECORD_MOVE_KEYS / RECORD_COLLECT_KEYS to
match your own in-game keybinds.

Needs administrator rights for the same reason bot.py does — the `keyboard`
package needs it to reliably hook global key events.
"""

import ctypes
import sys


def _relaunch_as_admin():
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return
    except Exception:
        return   # Not on Windows / API unavailable — nothing we can do here

    if getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(sys.argv[1:])
    else:
        exe, params = sys.executable, " ".join([f'"{__file__}"', *sys.argv[1:]])

    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    if result <= 32:
        ctypes.windll.user32.MessageBoxW(
            0,
            "需要系統管理員權限才能讓按鍵錄製正常運作，請重新執行並在 UAC 視窗按「是」。",
            "Screen Bot - Record Route",
            0x10,  # MB_ICONERROR
        )
    sys.exit(0)


_relaunch_as_admin()

import ast
import time
import keyboard

import config

OUTPUT_PATH = "recorded_route.txt"
CONFIG_PATH = "config.py"

# Menu order matters here — it's also the canonical order pieces are combined
# in for the final FIXED_ROUTE suggestion, matching config.py's own
# 上 -> 右 -> 左 -> 下 assembly order.
PIECES = [
    ("1", "TOP", "上"),
    ("2", "RIGHT", "右"),
    ("3", "LEFT", "左"),
    ("4", "BOTTOM", "下"),
]


def _choose_piece():
    print("\n現在要錄哪一塊？")
    for key, _, label in PIECES:
        print(f"  {key}. {label}")
    print("  q. 結束錄製，輸出目前錄好的內容")
    while True:
        raw = input("輸入編號：").strip().lower()
        if raw == "q":
            return None
        for key, name, label in PIECES:
            if raw == key:
                return name, label
        print("輸入無效，請重新輸入")


def _record_events():
    """
    Hook every configured move/collect key and log (timestamp, key, "down"/"up")
    for each, from the moment HOTKEY_START is pressed until HOTKEY_STOP is.
    """
    events = []
    state = {"active": False, "done": False}
    watched_keys = set(config.RECORD_MOVE_KEYS) | set(config.RECORD_COLLECT_KEYS)

    def on_event(e):
        if state["active"] and e.name in watched_keys and e.event_type in ("down", "up"):
            events.append((e.time, e.name, e.event_type))

    def start():
        if state["active"]:
            return
        events.clear()
        state["active"] = True
        print(f"開始錄製！照實際想要的路線操作一次，操作完按 {config.HOTKEY_STOP.upper()} 結束。")

    def stop():
        if not state["active"]:
            return
        state["active"] = False
        state["done"] = True

    keyboard.hook(on_event)
    keyboard.add_hotkey(config.HOTKEY_START, start)
    keyboard.add_hotkey(config.HOTKEY_STOP, stop)

    print(f"準備好後按 {config.HOTKEY_START.upper()} 開始錄製。")
    while not state["done"]:
        time.sleep(0.05)

    keyboard.unhook_all()
    print("錄製結束，轉換中...")
    return events


def _merge_move_segments(events):
    """
    Sweep the move-key press/release events into maximal segments of constant
    "which directions are currently held" — two move keys held together (e.g.
    W+D for a real diagonal) become ONE segment covering both directions,
    instead of two separate full-duration segments that would silently lose
    the diagonal and double the actual time spent moving. With no overlap
    this produces exactly the old one-segment-per-press/release behavior.
    Returns a list of (start_time, end_time, frozenset(directions)).
    """
    held = set()
    seg_start = None
    segments = []
    for t, key, kind in events:
        if key not in config.RECORD_MOVE_KEYS:
            continue
        if held and t > seg_start:
            segments.append((seg_start, t, frozenset(held)))
        direction = config.RECORD_MOVE_KEYS[key]
        if kind == "down":
            held.add(direction)
        else:
            held.discard(direction)
        seg_start = t
    # Any keys still held when recording stopped are dropped — release all
    # move keys before pressing HOTKEY_STOP for a clean recording.
    return segments


def _build_route(events):
    """Convert the raw (timestamp, key, down/up) timeline into FIXED_ROUTE steps."""
    route = []
    collect_burst = None    # {"action": str, "presses": [timestamp, ...]}

    def flush_collect_burst():
        nonlocal collect_burst
        if collect_burst is None:
            return
        presses = collect_burst["presses"]
        times = len(presses)
        if times > 1:
            gaps = [presses[i + 1] - presses[i] for i in range(times - 1)]
            interval = round(sum(gaps) / len(gaps), 3)
        else:
            interval = 0.4
        route.append({
            "type": "collect",
            "action": collect_burst["action"],
            "times": times,
            "interval": interval,
        })
        collect_burst = None

    # Move segments (already overlap-aware, see _merge_move_segments) and
    # collect key presses need to end up interleaved in the same chronological
    # order they actually happened in — a movement always ends any
    # in-progress collect burst, same as before.
    timeline = [(start, "move", (end - start, sorted(directions)))
                for start, end, directions in _merge_move_segments(events)]
    timeline += [(t, "collect", key) for t, key, kind in events
                 if key in config.RECORD_COLLECT_KEYS and kind == "down"]
    timeline.sort(key=lambda item: item[0])

    for t, kind, payload in timeline:
        if kind == "move":
            flush_collect_burst()
            duration, directions = payload
            duration = round(duration, 3)
            if duration > 0:
                route.append({
                    "type": "move",
                    "direction": directions[0] if len(directions) == 1 else directions,
                    "duration": duration,
                })
        else:
            action = config.RECORD_COLLECT_KEYS[payload]
            if (collect_burst is not None and collect_burst["action"] == action
                    and t - collect_burst["presses"][-1] <= config.RECORD_COLLECT_GROUP_GAP):
                collect_burst["presses"].append(t)
            else:
                flush_collect_burst()
                collect_burst = {"action": action, "presses": [t]}

    flush_collect_burst()
    return route


def _format_step(step):
    if step["type"] == "move":
        direction = step["direction"]
        direction_repr = (f'"{direction}"' if isinstance(direction, str)
                           else "[" + ", ".join(f'"{d}"' for d in direction) + "]")
        return f'{{"type": "move", "direction": {direction_repr}, "duration": {step["duration"]}}}'
    if step["type"] == "go_home":
        return '{"type": "go_home"}'
    return (
        f'{{"type": "collect", "action": "{step["action"]}", '
        f'"times": {step["times"]}, "interval": {step["interval"]}}}'
    )


def _format_route(var_name, route):
    lines = [f"{var_name} = ["]
    lines += [f"    {_format_step(step)}," for step in route]
    lines.append("]")
    return "\n".join(lines)


# Same reverse-path/scale logic as config.py (the functions are duplicated
# since they're that module's private helpers) — see config.py's own comments
# for why: no image recognition for the return trip, just play every outbound
# move back in reverse order with the opposite direction and the same
# duration (movement distance is proportional to hold duration the same way
# in all 4 directions, so this exactly cancels out). Scale-vs-replay overshoot
# (FIXED_ROUTE_RECORDED_SCALE) is a separate concern — see below.
_OPPOSITE_DIRECTION = {"up": "down", "down": "up", "left": "right", "right": "left"}


def _scale_moves(route, scale):
    return [
        {**step, "duration": round(step["duration"] * scale, 3)} if step["type"] == "move" else step
        for step in route
    ]


def _opposite(direction):
    """direction is a single direction string, or a list (two+ move keys held together, e.g. a recorded diagonal)."""
    if isinstance(direction, str):
        return _OPPOSITE_DIRECTION[direction]
    return [_OPPOSITE_DIRECTION[d] for d in direction]


def _reverse_home_moves(route):
    """Reversed move sequence, same duration, opposite direction(s)."""
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


def _apply_to_config(name, route):
    """
    Replace the FIXED_ROUTE_<name> = ... assignment in config.py in place —
    whatever it was before (a _build_diamond_piece_route(...) call, a
    hand-written list, or an earlier recording) gets overwritten outright.
    Uses `ast` to find the assignment's exact line range, so this works no
    matter how many lines the existing definition spans.
    """
    var_name = f"FIXED_ROUTE_{name}"
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        source = f.read()
    lines = source.splitlines(keepends=True)

    tree = ast.parse(source, filename=CONFIG_PATH)
    target = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == var_name):
            target = node
            break

    if target is None:
        print(f"在 {CONFIG_PATH} 裡找不到 {var_name} 的定義，這塊沒辦法自動套用，請手動貼上。")
        return False

    start, end = target.lineno - 1, target.end_lineno   # 0-indexed, half-open range
    lines[start:end] = [_format_route(var_name, route) + "\n"]

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"已套用到 {CONFIG_PATH} 的 {var_name}（原本第 {start + 1}~{end} 行）")
    return True


def main():
    recorded = {}   # piece name -> route (in PIECES menu order, not recording order)

    while True:
        choice = _choose_piece()
        if choice is None:
            break
        name, label = choice

        print(f"\n=== 錄製「{label}」===")
        events = _record_events()
        route = _build_route(events)
        if not route:
            print("這次沒有錄到任何有效的移動/採集操作，這塊不會被存起來，請確認按鍵設定或重錄一次。")
            continue

        # Scale to compensate for the bot's own replay (simulated mouse-hold)
        # covering more/less distance per held-second than these real keyboard
        # presses did, then append a literal reverse-path back to center —
        # no image recognition, no go_home() call at all.
        outbound = _scale_moves(route, config.FIXED_ROUTE_RECORDED_SCALE)
        route = outbound + _reverse_home_moves(outbound)
        recorded[name] = route
        print(f"「{label}」錄到 {len(route)} 個步驟（含自動算出的回原點路徑，已套用 "
              f"FIXED_ROUTE_RECORDED_SCALE={config.FIXED_ROUTE_RECORDED_SCALE}）")

    if not recorded:
        print("沒有錄製任何區塊。")
        return

    blocks = []
    combine_vars = []
    for _, name, label in PIECES:
        if name not in recorded:
            continue
        var_name = f"FIXED_ROUTE_{name}_RECORDED"
        blocks.append(f"# {label} ({name})\n" + _format_route(var_name, recorded[name]))
        combine_vars.append(var_name)

    combined = "FIXED_ROUTE = " + " + ".join(combine_vars)
    text = "\n\n".join(blocks) + "\n\n" + combined + "\n"

    print(f"\n錄好了 {len(recorded)} 塊，內容如下：\n")
    print(text)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"（同樣內容也存了一份到 {OUTPUT_PATH}）")
    if len(recorded) < len(PIECES):
        missing = [label for _, name, label in PIECES if name not in recorded]
        print(f"這次沒有錄到：{'、'.join(missing)}。")

    answer = input(f"\n要不要直接套用到 {CONFIG_PATH}，取代對應的 FIXED_ROUTE_上/右/左/下？(y/n)：").strip().lower()
    if answer != "y":
        print("好，沒有套用，你可以之後手動把上面印出來的內容貼進 config.py。")
        return

    applied = [label for _, name, label in PIECES if name in recorded and _apply_to_config(name, recorded[name])]
    if applied:
        print(f"\n「{'、'.join(applied)}」已套用完成！重新啟動 bot.py（或按 F1）就會用到新的路線。")


if __name__ == "__main__":
    main()
