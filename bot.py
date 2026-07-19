"""
Screen Bot entry point
Run: python bot.py
"""

import ctypes
import sys


def _relaunch_as_admin():
    """
    Global hotkeys (the `keyboard` lib) need real administrator rights to
    reliably reach an elevated/fullscreen game window (see README). Rather
    than rely on remembering to right-click -> "以系統管理員身分執行" every
    time, check here and silently re-launch elevated via UAC if not already
    admin. Must run before importing gui (which imports keyboard/pyautogui).
    """
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
    if result <= 32:   # ShellExecute failed or the UAC prompt was declined
        ctypes.windll.user32.MessageBoxW(
            0,
            "需要系統管理員權限才能讓熱鍵正常運作，請重新執行並在 UAC 視窗按「是」。",
            "Screen Bot",
            0x10,  # MB_ICONERROR
        )
    sys.exit(0)


_relaunch_as_admin()

from gui import BotGUI

if __name__ == "__main__":
    BotGUI().run()
