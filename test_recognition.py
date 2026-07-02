"""
Test image recognition results (supports polygon masks).

Usage:
  python test_recognition.py screenshot.png images/material_1.png [threshold]

In-window controls:
  +  threshold +0.05, rerun
  -  threshold -0.05, rerun
  R  rerun with the current threshold
  Q  quit
"""

import sys
import cv2
import numpy as np

COLORS = [(0, 255, 0), (0, 200, 255), (0, 200, 255), (0, 200, 255)]


def nms(matches, min_dist):
    sorted_m = sorted(matches, key=lambda m: -m[2])
    kept = []
    for m in sorted_m:
        if all(((m[0]-k[0])**2 + (m[1]-k[1])**2)**0.5 >= min_dist for k in kept):
            kept.append(m)
    return kept


def run_test(screen, template, mask, threshold):
    sh, sw = screen.shape[:2]
    th, tw = template.shape[:2]
    cx_screen, cy_screen = sw // 2, sh // 2

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED,
                               mask=mask if mask is not None else None)
    _, max_val, _, _ = cv2.minMaxLoc(result)

    display = screen.copy()

    ys, xs = np.where(result >= threshold)
    raw = [(x + tw//2, y + th//2, float(result[y, x])) for x, y in zip(xs, ys)]
    matches = nms(raw, min_dist=min(tw, th) * 0.6)

    if not matches:
        msg = f"NOT FOUND  最高:{max_val:.2f}  門檻:{threshold:.2f}"
        cv2.putText(display, msg, (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        print(f"[失敗] {msg}")
        if max_val > threshold * 0.7:
            suggest = round(max_val - 0.03, 2)
            print(f"  → 試試門檻 {suggest}：按 - 鍵調低")
    else:
        matches.sort(key=lambda m: (m[0]-cx_screen)**2 + (m[1]-cy_screen)**2)
        print(f"[成功] 找到 {len(matches)} 個，門檻 {threshold:.2f}")
        for i, (cx, cy, conf) in enumerate(matches):
            color = COLORS[0] if i == 0 else COLORS[1]
            label = f"#{i+1} {conf:.2f}" + (" <bot" if i == 0 else "")
            print(f"  {label}  ({cx}, {cy})")
            x1, y1 = cx - tw//2, cy - th//2
            cv2.rectangle(display, (x1, y1), (x1+tw, y1+th), color, 2)
            cv2.drawMarker(display, (cx, cy), color, cv2.MARKER_CROSS, 16, 2)
            cv2.putText(display, label, (x1, max(y1-6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    # Character position (screen center)
    cv2.drawMarker(display, (cx_screen, cy_screen),
                   (255, 255, 255), cv2.MARKER_DIAMOND, 24, 2)

    # Status bar
    bar = f"門檻:{threshold:.2f}  找到:{len(matches)}個  +/-調整  R重跑  Q離開"
    cv2.rectangle(display, (0, sh-30), (sw, sh), (30, 30, 30), -1)
    cv2.putText(display, bar, (8, sh-8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    # Heatmap
    heatmap = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    heatmap_resized = cv2.resize(heatmap_color, (sw, sh))

    combined = np.hstack([display, heatmap_resized])
    max_w = 1600
    if combined.shape[1] > max_w:
        scale = max_w / combined.shape[1]
        combined = cv2.resize(combined, None, fx=scale, fy=scale)

    return combined


def main(screen_path, template_path, threshold):
    screen = cv2.imread(screen_path)
    template = cv2.imread(template_path)

    if screen is None:
        print(f"[錯誤] 找不到截圖：{screen_path}")
        return
    if template is None:
        print(f"[錯誤] 找不到模板：{template_path}")
        return

    # Mask priority order: alpha channel > _mask.png > no mask
    raw = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    template = cv2.imread(template_path)
    mask = None

    if raw is not None and len(raw.shape) == 3 and raw.shape[2] == 4:
        alpha = raw[:, :, 3]
        _, binarized = cv2.threshold(alpha, 128, 255, cv2.THRESH_BINARY)
        if np.count_nonzero(binarized) > 0:
            mask = binarized
            ratio = np.count_nonzero(binarized) * 100 // binarized.size
            print(f"使用 alpha 遮罩（去背素材，有效區域 {ratio}%）")

    if mask is None:
        mask_path = template_path.replace(".png", "_mask.png")
        m = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if m is not None and np.count_nonzero(m) > 0:
            mask = m
            print(f"使用多邊形遮罩：{mask_path}（{np.count_nonzero(m)*100//m.size}% 有效）")
        elif m is not None:
            print(f"[警告] 遮罩全黑，略過，重新用 capture_helper.py 截取")
        else:
            print("無遮罩（矩形匹配）")

    th, tw = template.shape[:2]
    sh, sw = screen.shape[:2]
    print(f"截圖 {sw}x{sh}  模板 {tw}x{th}")

    WIN = "辨識測試 | +/-調門檻  R重跑  Q離開"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)

    while True:
        print(f"\n--- 門檻 {threshold:.2f} ---")
        img = run_test(screen, template, mask, threshold)
        cv2.imshow(WIN, img)

        key = cv2.waitKey(0) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('+') or key == ord('='):
            threshold = min(threshold + 0.05, 0.99)
        elif key == ord('-'):
            threshold = max(threshold - 0.05, 0.10)
        elif key == ord('r'):
            pass  # Just rerun as-is

    cv2.destroyAllWindows()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：python3 test_recognition.py <截圖> <模板> [門檻]")
    else:
        t = float(sys.argv[3]) if len(sys.argv) > 3 else 0.75
        main(sys.argv[1], sys.argv[2], t)
