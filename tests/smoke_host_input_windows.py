"""Interactive Windows E2E: route real pointer and keyboard events through host_agent."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

import tkinter as tk
import pyautogui
import host_agent

host_agent.set_windows_dpi_awareness()
pyautogui.FAILSAFE = False

root = tk.Tk()
root.title("Remote Desk Pro Input Dispatch E2E")
root.geometry("640x320+120+120")
root.attributes("-topmost", True)
clicked = {"value": False}
tk.Label(root, text="Remote Desk Pro real input dispatch test", font=("Segoe UI", 14)).pack(pady=20)
button = tk.Button(root, text="Click target", command=lambda: clicked.__setitem__("value", True), width=24)
button.pack(pady=12)
entry = tk.Entry(root, width=36, font=("Segoe UI", 12))
entry.pack(pady=12)
root.update()
screen = pyautogui.size()

def point_for(widget):
    root.update()
    x = widget.winfo_rootx() + widget.winfo_width() / 2
    y = widget.winfo_rooty() + widget.winfo_height() / 2
    return {"x": x / max(1, screen.width - 1), "y": y / max(1, screen.height - 1)}

try:
    host_agent.apply_control({"event": "mouse_move", **point_for(button)})
    host_agent.apply_control({"event": "mouse_down", "button": 0})
    host_agent.apply_control({"event": "mouse_up", "button": 0})
    time.sleep(0.15)
    root.update()
    assert clicked["value"], "Real mouse click did not activate the Tk button"

    host_agent.apply_control({"event": "mouse_move", **point_for(entry)})
    host_agent.apply_control({"event": "mouse_down", "button": 0})
    host_agent.apply_control({"event": "mouse_up", "button": 0})
    host_agent.apply_control({"event": "key_down", "key": "a"})
    host_agent.apply_control({"event": "key_up", "key": "a"})
    time.sleep(0.15)
    root.update()
    assert entry.get() == "a", f"Real key dispatch failed: {entry.get()!r}"
    print("WINDOWS HOST INPUT E2E: PASS (real mouse move/click + key down/up)")
finally:
    host_agent.release_all_inputs()
    root.destroy()
