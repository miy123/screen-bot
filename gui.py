"""
Small GUI control panel (tkinter, always on top)
"""

import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk
import keyboard
import pyautogui

import config
from engine import BotEngine, FixedRouteEngine, _resolve

LOG_FILE = _resolve("bot_log.txt")

# Mode name (shown in the GUI dropdown) -> engine class. Both engines expose
# the same start()/stop()/state interface, so start_bot/stop_bot below don't
# need to know which one is currently selected.
MODES = {
    "影像辨識": BotEngine,
    "固定路線": FixedRouteEngine,
}

class BotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screen Bot")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)      # Always stay on top
        self.root.attributes("-alpha", 0.92)         # Slightly transparent

        self._engine = None
        self._thread = None
        self._build_ui()
        self._setup_hotkeys()
        
    # ── Build UI ─────────────────────────────────────────
    def _build_ui(self):
        PAD = dict(padx=8, pady=4)

        # Title bar
        title = tk.Label(self.root, text="Screen Bot", font=("Arial", 13, "bold"))
        title.pack(**PAD)

        # Status
        self.status_var = tk.StringVar(value="閒置")
        status_frame = tk.Frame(self.root)
        status_frame.pack(fill="x", **PAD)
        tk.Label(status_frame, text="狀態：").pack(side="left")
        tk.Label(status_frame, textvariable=self.status_var,
                 fg="#2196F3", font=("Arial", 10, "bold")).pack(side="left")

        # Mode selector — switches which engine start_bot()/stop_bot() (and F1/F2) drive
        mode_frame = tk.Frame(self.root)
        mode_frame.pack(fill="x", **PAD)
        tk.Label(mode_frame, text="模式：").pack(side="left")
        self.mode_var = tk.StringVar(value="固定路線")
        self.mode_combo = ttk.Combobox(mode_frame, textvariable=self.mode_var,
                                        values=list(MODES.keys()), state="readonly", width=12)
        self.mode_combo.pack(side="left")

        # Buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", **PAD)
        self.start_btn = tk.Button(btn_frame, text=f"啟動 ({config.HOTKEY_START.upper()})",
                                   bg="#4CAF50", fg="white", width=14,
                                   command=self.start_bot)
        self.start_btn.pack(side="left", padx=2)
        self.stop_btn = tk.Button(btn_frame, text=f"停止 ({config.HOTKEY_STOP.upper()})",
                                  bg="#F44336", fg="white", width=14,
                                  command=self.stop_bot, state="disabled")
        self.stop_btn.pack(side="left", padx=2)
        self.debug_btn = tk.Button(btn_frame, text=f"Debug 座標 ({config.HOTKEY_DEBUG.upper()})",
                                   bg="#9C27B0", fg="white",
                                   command=self.debug_position)
        self.debug_btn.pack(side="left", padx=2)

        # Log box
        self.log_box = scrolledtext.ScrolledText(
            self.root, width=40, height=10, state="disabled",
            font=("Consolas", 9), bg="#1e1e1e", fg="#cccccc"
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Bottom hint
        tk.Label(self.root, text="滑鼠移到螢幕左上角可緊急停止",
                 fg="gray", font=("Arial", 8)).pack(pady=(0, 4))

    # ── Logging ──────────────────────────────────────────
    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"

        def _do():
            self.log_box.config(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.root.after(0, _do)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    # ── State updates ──────────────────────────────────────
    def set_state(self, state_str):
        self.root.after(0, lambda: self.status_var.set(state_str))

    # ── Bot control ──────────────────────────────────────
    def _start_engine(self, engine):
        if self._thread and self._thread.is_alive():
            return

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.mode_combo.config(state="disabled")

        self._engine = engine
        self._thread = threading.Thread(target=self._engine.start, daemon=True)
        self._thread.start()

    def start_bot(self):
        engine_cls = MODES[self.mode_var.get()]
        self._start_engine(engine_cls(log_fn=self.log, state_fn=self.set_state))

    def start_test_piece(self, label, route):
        """Fixed-route mode only: run a single piece (config.FIXED_ROUTE_TOP/RIGHT/LEFT/BOTTOM)
        on its own, regardless of which mode is currently selected in the dropdown."""
        self.log(f"單獨測試「{label}」路線")
        self._start_engine(FixedRouteEngine(log_fn=self.log, state_fn=self.set_state, route=route))

    def stop_bot(self):
        if self._engine:
            self._engine.stop()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.mode_combo.config(state="readonly")

    # ── Debug: read a screen coordinate under the mouse ────
    def debug_position(self):
        if getattr(self, "_debug_running", False):
            return
        self._debug_running = True
        self.log(f"Debug：{config.DEBUG_POSITION_DELAY} 秒後讀取滑鼠座標，請把滑鼠移到目標按鈕上")
        threading.Thread(target=self._debug_position_worker, daemon=True).start()

    def _debug_position_worker(self):
        time.sleep(config.DEBUG_POSITION_DELAY)
        pos = pyautogui.position()
        self.log(f"Debug：滑鼠座標 = {pos}")
        self._debug_running = False

    # ── Hotkeys ──────────────────────────────────────────
    def _setup_hotkeys(self):
        keyboard.add_hotkey(config.HOTKEY_START, lambda: self.root.after(0, self.start_bot))
        keyboard.add_hotkey(config.HOTKEY_STOP,  lambda: self.root.after(0, self.stop_bot))
        keyboard.add_hotkey(config.HOTKEY_DEBUG, lambda: self.root.after(0, self.debug_position))

        # Fixed-route mode: test one piece on its own, independent of the mode dropdown
        keyboard.add_hotkey(config.HOTKEY_TEST_TOP,
                             lambda: self.root.after(0, lambda: self.start_test_piece("上", config.FIXED_ROUTE_TOP)))
        keyboard.add_hotkey(config.HOTKEY_TEST_RIGHT,
                             lambda: self.root.after(0, lambda: self.start_test_piece("右", config.FIXED_ROUTE_RIGHT)))
        keyboard.add_hotkey(config.HOTKEY_TEST_LEFT,
                             lambda: self.root.after(0, lambda: self.start_test_piece("左", config.FIXED_ROUTE_LEFT)))
        keyboard.add_hotkey(config.HOTKEY_TEST_BOTTOM,
                             lambda: self.root.after(0, lambda: self.start_test_piece("下", config.FIXED_ROUTE_BOTTOM)))

    # ── Run ──────────────────────────────────────────────
    def run(self):
        pyautogui.FAILSAFE = True
        self.log(f"就緒。{config.HOTKEY_START.upper()} 啟動 / {config.HOTKEY_STOP.upper()} 停止 / {config.HOTKEY_DEBUG.upper()} 讀取滑鼠座標")
        self.log(f"固定路線單塊測試：{config.HOTKEY_TEST_TOP.upper()}=上 "
                  f"{config.HOTKEY_TEST_RIGHT.upper()}=右 {config.HOTKEY_TEST_LEFT.upper()}=左 "
                  f"{config.HOTKEY_TEST_BOTTOM.upper()}=下（{config.HOTKEY_STOP.upper()} 停止）")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.stop_bot()
        self.root.destroy()
