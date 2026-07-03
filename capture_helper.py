"""
Screenshot capture helper - polygon selection, automatic background removal

At startup (and any time you press M), it asks which material or character
facing you're capturing and names the saved files for you, continuing the
numbering after anything you've already captured — no more manually renaming
captured_N.png afterward.

Controls:
  Left click     = add a vertex
  Right click / Enter = finish selection, save
  Backspace      = remove the last vertex
  R              = restart (clear all vertices)
  S              = force-save as a rectangle (legacy mode)
  G              = re-grab the screen (for capturing another animation frame/moment)
  M              = switch which material/facing you're capturing
  Q              = quit

Saves two files per capture, named after what you're currently capturing:
  images/<name>_<N>.png       template image
  images/<name>_<N>_mask.png  mask (white = recognized area, black = ignored background)
"""

import os
import re
import time
import cv2
import numpy as np
from PIL import ImageGrab

os.makedirs("images", exist_ok=True)

# What you can capture. Keep this in sync with the material/facing names used
# in config.py's MATERIALS / FACING_IMAGES.
CATEGORIES = [
    "tree_big",
    "ore_stone",
    "ore_copper",
    "ore_silver",
    "ore_gold",
    "facing_up",
    "facing_down",
    "facing_left",
    "facing_right",
]

WINDOW_ID = "screen-bot-capture"
current_name = None
next_index = 1
points = []
orig = None
display = None


def _next_index_for(name):
    """Scan images/ so a new capture continues numbering instead of overwriting existing files."""
    pattern = re.compile(rf"^{re.escape(name)}_(\d+)\.png$")
    used = [int(m.group(1)) for f in os.listdir("images") if (m := pattern.match(f))]
    return max(used, default=0) + 1


def choose_category():
    global current_name, next_index
    print("\n要截哪個素材／面向？")
    for i, name in enumerate(CATEGORIES, 1):
        print(f"  {i}. {name}")
    while True:
        raw = input("輸入編號：").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(CATEGORIES):
            current_name = CATEGORIES[int(raw) - 1]
            next_index = _next_index_for(current_name)
            print(f"目前截取：{current_name}（下一張會存成 {current_name}_{next_index}.png）")
            return
        print("輸入無效，請重新輸入編號")


def window_title():
    return (f"截圖工具 | 目前：{current_name} 下一張 #{next_index} | "
            "左鍵加點 右鍵/Enter完成 Backspace刪點 R重來 G重截圖 M換素材 Q離開")


def redraw():
    global display
    display = orig.copy()

    if len(points) >= 2:
        for i in range(len(points) - 1):
            cv2.line(display, points[i], points[i+1], (0, 255, 0), 2)
        if len(points) >= 3:
            cv2.line(display, points[-1], points[0], (0, 200, 0), 1)  # dashed preview of the closing edge

    for i, p in enumerate(points):
        cv2.circle(display, p, 5, (0, 255, 255), -1)
        cv2.putText(display, str(i+1), (p[0]+6, p[1]-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    hint = f"頂點數：{len(points)}  {'右鍵/Enter完成' if len(points) >= 3 else '需要至少3個點'}"
    cv2.putText(display, hint, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imshow(WINDOW_ID, display)
    cv2.setWindowTitle(WINDOW_ID, window_title())


def grab_screen():
    global orig, display, points
    print("3 秒後截圖，請先切換到遊戲視窗...")
    time.sleep(3)
    shot = ImageGrab.grab()
    orig = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
    display = orig.copy()
    points = []


def save_polygon():
    global next_index, points
    if len(points) < 3:
        print("[警告] 需要至少 3 個頂點")
        return

    pts = np.array(points, dtype=np.int32)
    x, y, w, h = cv2.boundingRect(pts)

    # Crop out the template (bounding box)
    crop = orig[y:y+h, x:x+w]

    # Build the mask (white inside the polygon, black outside)
    mask_full = np.zeros(orig.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask_full, [pts], 255)   # Fill using original screen coordinates
    mask_crop = mask_full[y:y+h, x:x+w]  # Crop to the bounding box too

    template_path = f"images/{current_name}_{next_index}.png"
    mask_path     = f"images/{current_name}_{next_index}_mask.png"
    ok1 = cv2.imwrite(template_path, crop)
    ok2 = cv2.imwrite(mask_path, mask_crop)
    if not ok1 or not ok2:
      raise RuntimeError("cv2.imwrite 失敗，檢查權限或路徑")

    print(f"已存 {template_path}（{w}x{h} px）+ 遮罩 {mask_path}")
    next_index += 1
    print(f"下一張會存成 {current_name}_{next_index}.png（按 M 可換素材，按 G 可重新截圖）")

    # Visual feedback
    feedback = display.copy()
    cv2.polylines(feedback, [pts], True, (0, 255, 0), 3)
    cv2.putText(feedback, "已存！", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.imshow(WINDOW_ID, feedback)
    cv2.waitKey(600)

    points = []
    redraw()


def save_rect():
    """Legacy mode: save the whole bounding box directly (no mask)"""
    global next_index, points
    if len(points) < 2:
        return
    pts = np.array(points)
    x1, y1 = pts.min(axis=0)
    x2, y2 = pts.max(axis=0)
    crop = orig[y1:y2, x1:x2]
    path = f"images/{current_name}_{next_index}.png"
    cv2.imwrite(path, crop)
    print(f"已存矩形 {path}")
    next_index += 1
    points = []
    redraw()


def on_mouse(event, x, y, flags, param):
    global points
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        redraw()
    elif event == cv2.EVENT_RBUTTONDOWN:
        save_polygon()


def main():
    global points

    choose_category()
    grab_screen()

    cv2.namedWindow(WINDOW_ID, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW_ID, on_mouse)
    redraw()

    while True:
        key = cv2.waitKey(50) & 0xFF
        if key == ord('q'):
            break
        elif key == 13 or key == 10:   # Enter
            save_polygon()
        elif key == 8:                  # Backspace
            if points:
                points.pop()
                redraw()
        elif key == ord('r'):
            points = []
            redraw()
        elif key == ord('s'):
            save_rect()
        elif key == ord('g'):
            grab_screen()
            redraw()
        elif key == ord('m'):
            choose_category()
            redraw()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
