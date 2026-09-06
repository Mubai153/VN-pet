"""A separate GUI process owns WebView2's main thread."""
from __future__ import annotations

import multiprocessing
import threading


def run(origin, token, connection):
    import webview
    allow_close = threading.Event()
    close_requested = threading.Event()

    class Bridge:
        def bootstrap(self):
            if window.get_current_url() not in {origin, origin + "/"}:
                return {}
            return {"token": token}

        def close(self):
            # Do not destroy WebView2 from inside a JS bridge callback. The
            # callback can be reached from the native closing event, which
            # would re-enter that event and occasionally crash the window.
            close_requested.set()

    window = webview.create_window("VN 桌宠 · 设置", origin, js_api=Bridge(), width=1160, height=820,
                                   min_size=(800, 580), background_color="#f6f3ed", text_select=True)

    def closing():
        if allow_close.is_set():
            return True
        if close_requested.is_set():
            return False
        try:
            handled = window.evaluate_js("Boolean(window.requestSettingsClose && (window.requestSettingsClose(), true))")
            return not handled
        except Exception:
            return True
    window.events.closing += closing

    def control():
        try:
            while not close_requested.is_set():
                if connection.poll(0.1):
                    action = connection.recv()
                    if action == "close":
                        close_requested.set()
                        break
                    if action == "focus":
                        window.restore()
                        window.show()
                        window.on_top = True
                        window.on_top = False
                parent = multiprocessing.parent_process()
                if parent and not parent.is_alive():
                    close_requested.set()
                    break
        except (EOFError, OSError):
            close_requested.set()

        allow_close.set()
        try:
            window.destroy()
        except Exception:
            pass

    webview.start(control, gui="edgechromium", private_mode=True)


class SettingsWindow:
    def __init__(self, server):
        self.server = server
        self.process = None
        self.connection = None

    def open(self):
        if self.process and self.process.is_alive():
            try:
                self.connection.send("focus")
                return
            except (BrokenPipeError, EOFError, OSError):
                self.close()
        if self.connection:
            self.connection.close()
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=run, args=(self.server.origin, self.server.token, child), daemon=True, name="VN-settings")
        self.process.start()
        child.close()

    def close(self):
        if self.process and self.process.is_alive():
            try:
                self.connection.send("close")
            except (OSError, EOFError):
                pass
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
        if self.connection:
            self.connection.close()
        self.connection = None
        self.process = None
