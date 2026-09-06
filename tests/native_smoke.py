"""Windows integration check using an isolated data directory and real GUI windows."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk

from PIL import ImageGrab

from vn_pet.settings import Store
from vn_pet.settings_window import run as original_settings_run


def inspected_settings_run(origin, token, connection):
    import webview
    import win32gui
    create = webview.create_window
    directory = Path(os.environ["VN_SMOKE_OUTPUT"])
    def capture(*args, **kwargs):
        window = create(*args, **kwargs)
        def inspect():
            for _ in range(40):
                time.sleep(.25)
                try:
                    result = window.evaluate_js("({heading:document.querySelector('h1')?.textContent, nav:document.querySelectorAll('nav button').length, error:document.querySelector('.fatal')?.textContent})")
                    if result.get("heading") and result["nav"] == 5:
                        handle = int(window.native.Handle.ToInt64())
                        rect = win32gui.GetWindowRect(handle)
                        result["rect"] = rect
                        result["viewport"] = window.evaluate_js("({width:innerWidth,height:innerHeight})")
                        if rect[2] - rect[0] < 800 or rect[3] - rect[1] < 580:
                            continue
                        ImageGrab.grab(bbox=rect).save(directory / "native-settings.png")
                        (directory / "native-ui.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                        return
                except Exception:
                    continue
        window.events.loaded += lambda: threading.Thread(target=inspect, daemon=True).start()
        return window
    webview.create_window = capture
    original_settings_run(origin, token, connection)


def main():
    import codex_desktop_pet as app_module
    import vn_pet.settings_window as windows
    directory = Path.cwd() / ".runtime"
    directory.mkdir(exist_ok=True)
    receipt = directory / "native-ui.json"
    receipt.unlink(missing_ok=True)
    os.environ["VN_SMOKE_OUTPUT"] = str(directory)
    with tempfile.TemporaryDirectory(prefix="vn-native-") as data:
        app_module.Store = lambda: Store(Path(data))
        windows.run = inspected_settings_run
        root = tk.Tk()
        pet = app_module.DesktopPet(root)
        result = {"passed": False}
        labels = []
        class MenuProbe:
            def __init__(self, *a, **kw): pass
            def add_command(self, **kw): labels.append(kw["label"])
            def tk_popup(self, *a): pass
            def grab_release(self): pass
        old_menu = tk.Menu
        tk.Menu = MenuProbe
        pet.menu(type("Event", (), {"x_root": 0, "y_root": 0})())
        tk.Menu = old_menu
        assert labels == ["设置", "退出"]
        deadline = time.monotonic() + 45
        def start():
            pet.bubble.show({"id": "old", "text": "旧气泡"}, pet.store.snapshot("pet"))
            pet.bubble.show({"id": "new", "text": "忙了一会儿，也记得让眼睛歇一歇。我在这里陪着你。"}, pet.store.snapshot("pet"))
            pet.bubble.expire("old")
            assert pet.bubble.message_id == "new"
            root.update()
            import win32gui
            handle = win32gui.GetParent(pet.bubble.window.winfo_id())
            ImageGrab.grab(bbox=win32gui.GetWindowRect(handle)).save(directory / "native-bubble.png")
            pet.open_settings()
            root.after(100, poll)
        def poll():
            if receipt.exists():
                first_pid = pet.settings_window.process.pid
                pet.open_settings()
                assert pet.settings_window.process.pid == first_pid
                assert root.winfo_viewable() and pet.frame > 3
                pet.settings_window.close()
                assert not pet.settings_window.process
                # Closing settings must not close the pet; then verify reopening.
                assert root.winfo_viewable()
                receipt.unlink()
                pet.open_settings()
                root.after(100, finish)
            elif time.monotonic() > deadline:
                pet.close()
                raise RuntimeError("Native settings window did not become ready")
            else:
                root.after(100, poll)
        def finish():
            if receipt.exists():
                result.update(passed=True, menu=labels, frames=pet.frame, settings=json.loads(receipt.read_text(encoding="utf-8")))
                pet.close()
            elif time.monotonic() > deadline:
                pet.close()
                raise RuntimeError("Native settings reopen failed")
            else:
                root.after(100, finish)
        root.after(700, start)
        root.mainloop()
        assert result["passed"], result
        assert not pet.server.thread.is_alive()
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
