from __future__ import annotations

import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import font as tkfont
import uuid


def work_area(x, y):
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    user32 = ctypes.windll.user32
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    handle = user32.MonitorFromPoint(wintypes.POINT(x, y), 2)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
        raise OSError("无法读取显示器工作区")
    r = info.rcWork
    return r.left, r.top, r.right, r.bottom


def bubble_position(pet, size, area, position="auto"):
    px, py, pw, ph = pet
    width, height = size
    left, top, right, bottom = area
    prefer_left = position == "left_top" or (position == "auto" and px + pw + width > right)
    x = px - width + pw // 2 if prefer_left else px + pw // 2
    if x < left or x + width > right:
        alternative = px + pw // 2 if prefer_left else px - width + pw // 2
        if left <= alternative <= right - width:
            x = alternative
    return max(left, min(x, right - width)), max(top, min(py - height - 4, bottom - height))


def paginate(text, measure, width, max_lines=5):
    lines, line = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(line)
            line = ""
        elif line and measure(line + ch) > width:
            lines.append(line)
            line = ch
        else:
            line += ch
    if line or not lines:
        lines.append(line)
    return ["\n".join(lines[i:i + max_lines]) for i in range(0, len(lines), max_lines)]


class SpeechBubble:
    def __init__(self, root):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True, "-transparentcolor", "#ff00ff")
        self.window.configure(bg="#ff00ff")
        self.canvas = tk.Canvas(self.window, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()
        self.timer = None
        self.message_id = None
        self.pages = []
        self.index = 0
        self.settings = {}
        self.size = (340, 180)
        self.window.bind("<Escape>", lambda e: self.hide())

    def show(self, payload, settings):
        self.hide()
        if not settings["enabled"] or not payload["text"].strip():
            return False
        self.message_id = payload.get("id", uuid.uuid4().hex)
        self.settings = dict(settings)
        self.text = payload["text"]
        self.font = tkfont.Font(family="Microsoft YaHei UI", size=-settings["font_size"])
        self.pages = paginate(self.text, self.font.measure, 302)
        self.index = 0
        self.render()
        self.window.deiconify()
        self.window.update_idletasks()
        return True

    def render(self):
        if self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None
        lines = self.pages[self.index].count("\n") + 1
        height = max(94, lines * self.font.metrics("linespace") + 72)
        width = 340
        self.size = width, height
        self.canvas.configure(width=width, height=height)
        self.canvas.delete("all")
        x0, y0, x1, y1, radius = 2, 2, width - 2, height - 15, 14
        points = [x0+radius,y0,x1-radius,y0,x1,y0,x1,y0+radius,x1,y1-radius,x1,y1,x1-radius,y1,x0+radius,y1,x0,y1,x0,y1-radius,x0,y0+radius,x0,y0]
        self.canvas.create_polygon(points, smooth=True, splinesteps=20, fill=self.settings["background"], outline=self.settings["border"], width=1)
        self.canvas.create_text(18, 17, text=self.pages[self.index], anchor="nw", font=self.font, fill=self.settings["text_color"])
        self.canvas.create_text(width-17, 13, text="×", font=("Segoe UI", 12), fill=self.settings["border"], tags="close")
        self.canvas.tag_bind("close", "<Button-1>", lambda e: self.hide())
        if len(self.pages) > 1:
            self.canvas.create_text(22, y1-17, text="‹", font=("Segoe UI", 15), fill=self.settings["text_color"], tags="previous")
            self.canvas.create_text(width-25, y1-17, text="›", font=("Segoe UI", 15), fill=self.settings["text_color"], tags="next")
            self.canvas.create_text(width//2, y1-17, text=f"{self.index+1} / {len(self.pages)}", font=("Segoe UI", 9), fill=self.settings["border"])
            self.canvas.tag_bind("previous", "<Button-1>", lambda e: self.page(-1))
            self.canvas.tag_bind("next", "<Button-1>", lambda e: self.page(1))
        self.follow()
        owner = self.message_id
        self.timer = self.root.after(self.settings["duration_seconds"] * 1000, lambda: self.expire(owner))

    def page(self, step):
        self.index = max(0, min(self.index + step, len(self.pages)-1))
        self.render()

    def expire(self, owner):
        if owner != self.message_id:
            return
        if self.index + 1 < len(self.pages):
            self.page(1)
        else:
            self.hide()

    def follow(self):
        if not self.message_id:
            return
        px, py = self.root.winfo_x(), self.root.winfo_y()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        try:
            area = work_area(px + pw//2, py + ph//2)
        except OSError:
            area = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        x, y = bubble_position((px, py, pw, ph), self.size, area, self.settings["position"])
        # Tk's negative geometry means right/bottom-relative; native positioning preserves signed coordinates.
        if getattr(self, "_layout_size", None) != self.size:
            self.window.geometry(f"{self.size[0]}x{self.size[1]}")
            self._layout_size = self.size
        self.window.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        hwnd = user32.GetParent(self.window.winfo_id())
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos(hwnd, None, x, y, 0, 0, 0x0015)
        tip = max(20, min(px + pw//2 - x, self.size[0]-20))
        self.canvas.delete("tip")
        self.canvas.create_polygon(tip-9, self.size[1]-16, tip, self.size[1]-3, tip+9, self.size[1]-16,
                                   fill=self.settings["background"], outline=self.settings["border"], tags="tip")

    def apply(self, settings):
        if self.message_id:
            self.show({"id": self.message_id, "text": self.text}, settings)

    def hide(self):
        if self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.message_id = None
        self.window.withdraw()

    def close(self):
        self.hide()
        self.window.destroy()
