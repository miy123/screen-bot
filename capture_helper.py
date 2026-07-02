"""
Screenshot capture helper - polygon selection, automatic background removal

Controls:
  Left click     = add a vertex
  Right click / Enter = finish selection, save
  Backspace      = remove the last vertex
  R              = restart (clear all vertices)
  S              = force-save as a rectangle (legacy mode)
  Q              = quit

Saves two files:
  images/captured_N.png       template image
  images/captured_N_mask.png  mask (white = recognized area, black = ignored background)
"""

import os
import time
import cv2
import numpy as np
from PIL import ImageGrab

os.makedirs("images", exist_ok=True)

TITLE = "截圖工具 | 左鍵加點 右鍵/Enter完成 Backspace刪點 R重來 Q離開"
saved_count = 0
points = []
orig = None
display = None


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
    cv2.imshow(TITLE, display)


def save_polygon():
    global saved_count, points
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

    template_path = f"images/captured_{saved_count}.png"
    mask_path     = f"images/captured_{saved_count}_mask.png"
    cv2.imwrite(template_path, crop)
    cv2.imwrite(mask_path, mask_crop)
    saved_count += 1

    print(f"已存 {template_path}（{w}x{h} px）+ 遮罩 {mask_path}")
    print(f"→ 在 config.py MATERIAL_IMAGES 加入 \"{template_path}\"")

    # Visual feedback
    feedback = display.copy()
    cv2.polylines(feedback, [pts], True, (0, 255, 0), 3)
    cv2.putText(feedback, "已存！", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.imshow(TITLE, feedback)
    cv2.waitKey(600)

    points = []
    redraw()


def save_rect():
    """Legacy mode: save the whole bounding box directly (no mask)"""
    global saved_count, points
    if len(points) < 2:
        return
    pts = np.array(points)
    x1, y1 = pts.min(axis=0)
    x2, y2 = pts.max(axis=0)
    crop = orig[y1:y2, x1:x2]
    path = f"images/captured_{saved_count}.png"
    cv2.imwrite(path, crop)
    saved_count += 1
    print(f"已存矩形 {path}")
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
    global orig, display, points

    print("3 秒後截圖，請先切換到遊戲視窗...")
    time.sleep(3)

    shot = ImageGrab.grab()
    orig = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
    display = orig.copy()

    cv2.imshow(TITLE, display)
    cv2.setMouseCallback(TITLE, on_mouse)

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

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
