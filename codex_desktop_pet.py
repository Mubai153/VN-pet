import os
import ctypes
import logging
import multiprocessing
import queue
import random
import time
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

from vn_pet.activity import Companion
from vn_pet.bubble import SpeechBubble
from vn_pet.server import LocalServer
from vn_pet.settings import Store
from vn_pet.settings_window import SettingsWindow


ASSET = os.path.join(os.path.dirname(__file__), "codex_pet_v2.png")
EGG_ANIMATION_ASSET = os.path.join(os.path.dirname(__file__), "codex_pet_egg_animation.png")
TRANSPARENT = "#ff00ff"
RANDOM_EGG_COOLDOWN = 120.0
CLICK_WINDOW = 1.2
ANIMATION_SCALE = 1.17
EGG_ANIMATION_FRAMES = 15


def update_click_sequence(count, last_click, now):
    if now - last_click > CLICK_WINDOW:
        count = 0
    count += 1
    return count, now, count >= 3


def split_egg_strip(strip, size):
    frame_width = strip.width // EGG_ANIMATION_FRAMES
    if frame_width * EGG_ANIMATION_FRAMES != strip.width:
        raise ValueError("Egg animation strip must contain 15 equal frames")
    return [
        strip.crop((i * frame_width, 0, (i + 1) * frame_width, strip.height))
        .resize(size, Image.Resampling.NEAREST)
        for i in range(EGG_ANIMATION_FRAMES)
    ]


class DesktopPet:
    def __init__(self, root):
        self.root = root
        self.root.title("VN 桌宠")
        self.closing = False
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT)

        image = Image.open(ASSET).convert("RGBA")
        image = image.resize((image.width // 2, image.height // 2),
                             Image.Resampling.NEAREST)
        self.base_width, self.base_height = image.size
        self.split_y = int(self.base_height * 0.68)
        head = image.crop((0, 0, self.base_width, self.split_y))
        body = image.crop((0, self.split_y, self.base_width, self.base_height))
        self.head_photo = ImageTk.PhotoImage(head)
        self.body_photo = ImageTk.PhotoImage(body)
        egg_strip = Image.open(EGG_ANIMATION_ASSET).convert("RGBA")
        animation_size = (round(self.base_width * ANIMATION_SCALE),
                          round(self.base_height * ANIMATION_SCALE))
        self.egg_photos = [
            ImageTk.PhotoImage(frame)
            for frame in split_egg_strip(egg_strip, animation_size)
        ]
        self.width = max(self.base_width, animation_size[0])
        self.height = max(self.base_height, animation_size[1])
        self.base_x = (self.width - self.base_width) // 2

        self.canvas = tk.Canvas(root, width=self.width, height=self.height,
                                bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()
        self.body_item = self.canvas.create_image(
            self.base_x, self.split_y, anchor="nw", image=self.body_photo)
        self.head_item = self.canvas.create_image(
            self.base_x, 0, anchor="nw", image=self.head_photo)
        self.egg_item = self.canvas.create_image(
            0, 0, anchor="nw", image=self.egg_photos[0], state="hidden")

        self.drag_start = None
        self.click_start = None
        self.click_count = 0
        self.last_click = 0.0
        self.last_egg_trigger = 0.0
        self.egg_frame = None
        self.x = 0
        self.y = 0
        self.frame = 0

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Button-3>", self.menu)
        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.root.update_idletasks()
        self.x = root.winfo_screenwidth() - self.width - 40
        self.y = root.winfo_screenheight() - self.height - 100
        self.root.geometry(f"+{self.x}+{self.y}")
        self.events = queue.Queue()
        self.store = Store()
        self.companion = Companion(self.store, self.events)
        self.bubble = SpeechBubble(root)
        self.server = LocalServer(self.companion, self.events)
        self.settings_window = SettingsWindow(self.server)
        self.server.start()
        self.root.after(50, self.poll_events)
        self.root.after(random.randint(120000, 300000), self.random_egg)
        self.animate()

    def start_drag(self, event):
        self.x = self.root.winfo_x()
        self.y = self.root.winfo_y()
        self.drag_start = (event.x_root - self.x, event.y_root - self.y)
        self.click_start = (event.x_root, event.y_root)

    def drag(self, event):
        if self.drag_start:
            self.x = event.x_root - self.drag_start[0]
            self.y = event.y_root - self.drag_start[1]
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user32.SetWindowPos(user32.GetParent(self.root.winfo_id()), None, int(self.x), int(self.y), 0, 0, 0x0015)
            self.bubble.follow()

    def end_drag(self, _event):
        if self.click_start is not None:
            moved = max(abs(_event.x_root - self.click_start[0]),
                        abs(_event.y_root - self.click_start[1]))
            if moved <= 8:
                self.click_count, self.last_click, triple = update_click_sequence(
                    self.click_count, self.last_click, time.monotonic())
                if triple:
                    self.click_count = 0
                    self.trigger_egg("click")
            else:
                self.click_count = 0
        self.click_start = None
        self.drag_start = None

    def trigger_egg(self, source):
        if self.closing or self.egg_frame is not None:
            return False
        now = time.monotonic()
        if source == "random" and now - self.last_egg_trigger < RANDOM_EGG_COOLDOWN:
            return False
        self.last_egg_trigger = now
        self.egg_frame = 0
        return True

    def random_egg(self):
        if not self.closing:
            self.trigger_egg("random")
            self.root.after(random.randint(120000, 300000), self.random_egg)

    def animate(self):
        if self.closing:
            return
        if self.egg_frame is not None:
            self.canvas.itemconfigure(self.head_item, state="hidden")
            self.canvas.itemconfigure(self.body_item, state="hidden")
            self.canvas.itemconfigure(self.egg_item,
                                      image=self.egg_photos[self.egg_frame],
                                      state="normal")
            self.egg_frame += 1
            if self.egg_frame == len(self.egg_photos):
                self.egg_frame = None
        else:
            self.canvas.itemconfigure(self.head_item, state="normal")
            self.canvas.itemconfigure(self.body_item, state="normal")
            self.canvas.itemconfigure(self.egg_item, state="hidden")
            # Keep only a small idle head sway; the pet no longer walks automatically.
            head_shift = (-2, -1, 0, 1, 2, 1, 0, -1)[self.frame % 8]
            self.canvas.coords(self.head_item, self.base_x + head_shift, 0)
            self.canvas.coords(self.body_item, self.base_x, self.split_y)

        self.frame += 1
        self.root.after(120, self.animate)

    def menu(self, event):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="设置", command=self.open_settings)
        menu.add_command(label="退出", command=self.close)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def open_settings(self):
        if self.closing:
            return
        if not self.server.server.started:
            if not self.server.thread.is_alive():
                messagebox.showerror("VN 桌宠", "设置服务启动失败，请查看本地 app.log。")
                return
            self.root.after(100, self.open_settings)
            return
        self.settings_window.open()

    def poll_events(self):
        if self.closing:
            return
        for _ in range(30):
            try:
                kind, data, acknowledgement = self.events.get_nowait()
            except queue.Empty:
                break
            try:
                result = True
                if kind == "speech":
                    if acknowledgement.cancelled():
                        continue
                    result = self.companion.display(data, self.bubble.show)
                elif kind == "preview":
                    self.bubble.show(data, {**data["settings"], "enabled": True})
                elif kind == "clear":
                    self.bubble.hide()
                elif kind == "pet_settings":
                    self.bubble.apply(data)
                if acknowledgement and not acknowledgement.done():
                    acknowledgement.set_result(result)
            except Exception:
                logging.exception("Unable to display pet event")
                if acknowledgement and not acknowledgement.done():
                    acknowledgement.set_result(False)
        self.root.after(50, self.poll_events)

    def close(self):
        if self.closing:
            return
        self.closing = True
        with self.companion.guard:
            self.companion.closed = True
            self.companion.generation += 1
        self.bubble.close()
        self.settings_window.close()
        self.server.stop()
        self.root.destroy()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    mutex = kernel32.CreateMutexW(None, False, "Local\\VNDesktopPet.App")
    if kernel32.GetLastError() != 183:
        directory = Store().directory
        logging.basicConfig(filename=directory / "app.log", level=logging.WARNING, encoding="utf-8")
        try:
            app = tk.Tk()
            pet = DesktopPet(app)
            app.mainloop()
        except Exception:
            logging.exception("VN desktop startup failed")
            messagebox.showerror("VN 桌宠", "启动失败，请查看 %LOCALAPPDATA%\\VNDesktopPet\\app.log。")
