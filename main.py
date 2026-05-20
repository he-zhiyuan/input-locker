import ctypes
import ctypes.wintypes
import sys
import winreg
import threading
import time
import atexit
import traceback
import json
import os
from tkinter import messagebox
import customtkinter as ctk

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14

WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105

ES_CONTINUOUS = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002
ES_SYSTEM_REQUIRED = 0x00000001

VK_CAPITAL = 0x14
VK_BACK = 0x08
VK_RETURN = 0x0D
VK_SHIFT = 0x10

LETTER_KEYS = set(range(0x41, 0x5B))
NUMBER_KEYS = set(range(0x30, 0x3A))

CAPS_LOCK_TRIGGER_COUNT = 3
CAPS_LOCK_TRIGGER_WINDOW = 2.0

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "config.json")
DEFAULT_PASSWORD = "123456"


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"password": DEFAULT_PASSWORD}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_int),
        ("scanCode", ctypes.c_int),
        ("flags", ctypes.c_int),
        ("time", ctypes.c_int),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_void_p))
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.c_int * 2),
        ("hwnd", ctypes.c_void_p),
        ("wHitTestCode", ctypes.c_int),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_void_p))
    ]


KBDHOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(KBDLLHOOKSTRUCT)
)
MOUSEHOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(MSLLHOOKSTRUCT)
)


class SystemLocker:
    def __init__(self):
        self.kb_hook_handle = None
        self.mouse_hook_handle = None
        self.lock_active = False
        self.unlock_password = load_config().get("password", DEFAULT_PASSWORD)

        self._kb_hook_proc = None
        self._mouse_hook_proc = None
        self._msg_thread = None

        self.caps_lock_press_times = []
        self.unlock_mode = False
        self._unlock_mode_changed = False

        self._original_screensaver_active = None
        self._original_screensaver_timeout = None

    def set_password(self, new_password):
        self.unlock_password = new_password
        save_config({"password": new_password})

    def _get_screensaver_settings(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
            active, _ = winreg.QueryValueEx(key, "ScreenSaveActive")
            timeout, _ = winreg.QueryValueEx(key, "ScreenSaveTimeOut")
            winreg.CloseKey(key)
            return str(active), str(timeout)
        except:
            return "1", "600"

    def _set_screensaver_settings(self, active, timeout):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "ScreenSaveActive", 0, winreg.REG_SZ, str(active))
            winreg.SetValueEx(key, "ScreenSaveTimeOut", 0, winreg.REG_SZ, str(timeout))
            winreg.CloseKey(key)
        except:
            pass

    def _enable_screen_always_on(self):
        self._original_screensaver_active, self._original_screensaver_timeout = self._get_screensaver_settings()
        self._set_screensaver_settings("0", "0")
        kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)

    def _restore_screen_settings(self):
        if self._original_screensaver_active is not None and self._original_screensaver_timeout is not None:
            self._set_screensaver_settings(self._original_screensaver_active, self._original_screensaver_timeout)
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    def _disable_usb_storage(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\USBSTOR", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, 4)
            winreg.CloseKey(key)
        except:
            pass

    def _enable_usb_storage(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\USBSTOR", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, 3)
            winreg.CloseKey(key)
        except:
            pass

    def _kb_hook_callback(self, nCode, wParam, lParam):
        if nCode >= 0 and self.lock_active:
            try:
                vk_code = lParam.contents.vkCode

                if vk_code == VK_CAPITAL and (wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN):
                    now = time.time()
                    self.caps_lock_press_times.append(now)
                    self.caps_lock_press_times = [
                        t for t in self.caps_lock_press_times
                        if now - t < CAPS_LOCK_TRIGGER_WINDOW
                    ]
                    if len(self.caps_lock_press_times) >= CAPS_LOCK_TRIGGER_COUNT:
                        self.caps_lock_press_times.clear()
                        self.unlock_mode = not self.unlock_mode
                        self._unlock_mode_changed = True
                    return 1

                if self.unlock_mode:
                    allowed = LETTER_KEYS | NUMBER_KEYS | {VK_BACK, VK_RETURN, VK_SHIFT}
                    if vk_code in allowed:
                        return user32.CallNextHookEx(
                            self.kb_hook_handle, nCode, wParam,
                            ctypes.cast(lParam, ctypes.POINTER(ctypes.c_void_p))
                        )
                    return 1

                return 1

            except:
                return 1

        return user32.CallNextHookEx(
            self.kb_hook_handle, nCode, wParam,
            ctypes.cast(lParam, ctypes.POINTER(ctypes.c_void_p))
        )

    def _mouse_hook_callback(self, nCode, wParam, lParam):
        if nCode >= 0 and self.lock_active:
            return 1

        return user32.CallNextHookEx(
            self.mouse_hook_handle, nCode, wParam,
            ctypes.cast(lParam, ctypes.POINTER(ctypes.c_void_p))
        )

    def _install_hooks(self):
        self._kb_hook_proc = KBDHOOKPROC(self._kb_hook_callback)
        self.kb_hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_hook_proc, 0, 0)
        if not self.kb_hook_handle:
            raise ctypes.WinError(ctypes.get_last_error())

        self._mouse_hook_proc = MOUSEHOOKPROC(self._mouse_hook_callback)
        self.mouse_hook_handle = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_hook_proc, 0, 0)
        if not self.mouse_hook_handle:
            self.remove_keyboard_hook()
            raise ctypes.WinError(ctypes.get_last_error())

    def remove_keyboard_hook(self):
        if self.kb_hook_handle:
            user32.UnhookWindowsHookEx(self.kb_hook_handle)
            self.kb_hook_handle = None

    def _remove_mouse_hook(self):
        if self.mouse_hook_handle:
            user32.UnhookWindowsHookEx(self.mouse_hook_handle)
            self.mouse_hook_handle = None

    def _message_loop(self):
        msg = ctypes.wintypes.MSG()
        while self.lock_active:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == 0x0012:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)

    def start_lock(self):
        try:
            self.lock_active = True
            self.unlock_mode = False
            self._unlock_mode_changed = False
            self.caps_lock_press_times.clear()

            self._enable_screen_always_on()
            self._disable_usb_storage()
            self._install_hooks()

            self._msg_thread = threading.Thread(target=self._message_loop, daemon=True)
            self._msg_thread.start()

            return True
        except Exception:
            self.lock_active = False
            self._remove_mouse_hook()
            self.remove_keyboard_hook()
            self._enable_usb_storage()
            self._restore_screen_settings()
            return False

    def stop_lock(self):
        try:
            self.lock_active = False
            self.unlock_mode = False
            self._unlock_mode_changed = False
            time.sleep(0.2)

            self.remove_keyboard_hook()
            self._remove_mouse_hook()
            self._enable_usb_storage()
            self._restore_screen_settings()

            return True
        except:
            return False

    def cancel_unlock_mode(self):
        self.unlock_mode = False
        self._unlock_mode_changed = True

    def emergency_restore(self):
        self.lock_active = False
        self.unlock_mode = False
        try:
            self.remove_keyboard_hook()
        except:
            pass
        try:
            self._remove_mouse_hook()
        except:
            pass
        try:
            self._enable_usb_storage()
        except:
            pass
        try:
            self._restore_screen_settings()
        except:
            pass


class LockApp:
    BG = "#1c1c1e"
    CARD_BG = "#2c2c2e"
    ACCENT = "#0a84ff"
    GREEN = "#30d158"
    RED = "#ff453a"
    TEXT = "#ffffff"
    SUBTEXT = "#8e8e93"
    BORDER = "#3a3a3c"

    def __init__(self, locker):
        self.locker = locker
        self._last_unlock_mode = False

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("System Locker")
        self.root.geometry("400x600")
        self.root.resizable(False, False)
        self.root.configure(fg_color=self.BG)

        self._build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Alt-F4>", lambda e: "break")

        self._poll_state()

    def _build_ui(self):
        container = ctk.CTkFrame(self.root, fg_color=self.BG)
        container.pack(fill="both", expand=True, padx=24, pady=24)

        icon_label = ctk.CTkLabel(
            container, text="🔒", font=ctk.CTkFont(size=48),
            text_color=self.TEXT
        )
        icon_label.pack(pady=(16, 4))

        ctk.CTkLabel(
            container, text="System Locker",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=self.TEXT
        ).pack(pady=(0, 4))

        self.status_label = ctk.CTkLabel(
            container, text="未锁定",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=self.GREEN
        )
        self.status_label.pack(pady=(0, 20))

        self.lock_button = ctk.CTkButton(
            container, text="锁定系统", command=self.lock,
            width=260, height=48, corner_radius=24,
            fg_color=self.ACCENT, hover_color="#0070e0",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold")
        )
        self.lock_button.pack(pady=(0, 12))

        self.msg_label = ctk.CTkLabel(
            container, text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.GREEN, wraplength=340
        )
        self.msg_label.pack(pady=(0, 12))

        self.unlock_frame = ctk.CTkFrame(container, fg_color="transparent")

        ctk.CTkLabel(
            self.unlock_frame, text="输入密码解锁",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=self.SUBTEXT
        ).pack(pady=(0, 10))

        self.password_entry = ctk.CTkEntry(
            self.unlock_frame, show="•", width=260, height=44,
            corner_radius=12, placeholder_text="密码",
            fg_color=self.CARD_BG, border_color=self.BORDER,
            text_color=self.TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=15)
        )
        self.password_entry.pack(pady=(0, 12))

        self.unlock_button = ctk.CTkButton(
            self.unlock_frame, text="解锁", command=self.unlock,
            width=260, height=44, corner_radius=22,
            fg_color=self.GREEN, hover_color="#28b84c",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        )
        self.unlock_button.pack(pady=(0, 4))

        self.password_entry.bind("<Return>", lambda e: self.unlock())

        self.change_pw_button = ctk.CTkButton(
            container, text="修改密码", command=self._open_change_password,
            width=120, height=34, corner_radius=17,
            fg_color=self.CARD_BG, hover_color="#3a3a3c",
            text_color=self.SUBTEXT, border_width=1, border_color=self.BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.change_pw_button.pack(pady=(4, 16))

        hint_card = ctk.CTkFrame(container, fg_color=self.CARD_BG, corner_radius=12)
        hint_card.pack(fill="x", side="bottom", pady=(0, 4))

        is_first_run = not os.path.exists(CONFIG_FILE)

        hints = [
            "锁定后: 键盘/鼠标禁用，USB存储禁用，屏幕常亮",
            "解锁: 连按3次 CapsLock → 输入密码 → Enter",
            "解锁模式下密码错误自动关闭",
        ]
        if is_first_run:
            hints.append(f"初始密码: {self.locker.unlock_password}，请及时修改")

        for h in hints:
            ctk.CTkLabel(
                hint_card, text=h,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=self.SUBTEXT, anchor="w"
            ).pack(fill="x", padx=14, pady=2)

        ctk.CTkLabel(hint_card, text="").pack(pady=2)

    def _open_change_password(self):
        if self.locker.lock_active:
            return

        win = ctk.CTkToplevel(self.root)
        win.title("修改密码")
        win.geometry("360x380")
        win.resizable(False, False)
        win.configure(fg_color=self.BG)
        win.grab_set()

        ctk.CTkLabel(
            win, text="修改密码",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=self.TEXT
        ).pack(pady=(24, 20))

        form = ctk.CTkFrame(win, fg_color="transparent")
        form.pack(padx=32, fill="x")

        ctk.CTkLabel(
            form, text="当前密码",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.SUBTEXT, anchor="w"
        ).pack(fill="x", pady=(0, 4))
        old_entry = ctk.CTkEntry(
            form, show="•", height=40, corner_radius=10,
            fg_color=self.CARD_BG, border_color=self.BORDER,
            text_color=self.TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=14)
        )
        old_entry.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            form, text="新密码",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.SUBTEXT, anchor="w"
        ).pack(fill="x", pady=(0, 4))
        new_entry = ctk.CTkEntry(
            form, show="•", height=40, corner_radius=10,
            fg_color=self.CARD_BG, border_color=self.BORDER,
            text_color=self.TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=14)
        )
        new_entry.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            form, text="确认新密码",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.SUBTEXT, anchor="w"
        ).pack(fill="x", pady=(0, 4))
        confirm_entry = ctk.CTkEntry(
            form, show="•", height=40, corner_radius=10,
            fg_color=self.CARD_BG, border_color=self.BORDER,
            text_color=self.TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=14)
        )
        confirm_entry.pack(fill="x", pady=(0, 16))

        msg_label = ctk.CTkLabel(
            win, text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.RED
        )
        msg_label.pack()

        def do_change():
            old = old_entry.get()
            new = new_entry.get()
            confirm = confirm_entry.get()

            if old != self.locker.unlock_password:
                msg_label.configure(text="当前密码错误", text_color=self.RED)
                return

            if not new:
                msg_label.configure(text="新密码不能为空", text_color=self.RED)
                return

            if new != confirm:
                msg_label.configure(text="两次输入的新密码不一致", text_color=self.RED)
                return

            self.locker.set_password(new)
            messagebox.showinfo("成功", "密码已修改!", parent=win)
            win.destroy()

        ctk.CTkButton(
            win, text="确认修改", command=do_change,
            width=200, height=42, corner_radius=21,
            fg_color=self.ACCENT, hover_color="#0070e0",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        ).pack(pady=8)

    def _poll_state(self):
        try:
            if self.locker._unlock_mode_changed:
                self.locker._unlock_mode_changed = False
                new_mode = self.locker.unlock_mode
                if new_mode != self._last_unlock_mode:
                    self._last_unlock_mode = new_mode
                    self._update_unlock_ui(new_mode)
        except Exception:
            pass
        self.root.after(100, self._poll_state)

    def _update_unlock_ui(self, unlock_mode):
        if unlock_mode:
            self.unlock_frame.pack(after=self.msg_label, pady=8)
            self.password_entry.delete(0, 'end')
            try:
                self.password_entry._entry.focus_set()
            except Exception:
                self.password_entry.focus_set()
            self.msg_label.configure(text="解锁模式已开启 — 请输入密码", text_color=self.GREEN)
        else:
            self.unlock_frame.pack_forget()
            if self.locker.lock_active:
                self.msg_label.configure(text="已锁定 — 连按3次 CapsLock 解锁", text_color=self.GREEN)

    def lock(self):
        success = self.locker.start_lock()
        if success:
            self.status_label.configure(text="已锁定", text_color=self.RED)
            self.lock_button.configure(state="disabled", fg_color="#555555")
            self.change_pw_button.configure(state="disabled")
            self.root.attributes('-topmost', True)
            self.root.lift()
            self.root.focus_force()
            self.msg_label.configure(
                text="已锁定 — 连按3次 CapsLock 解锁",
                text_color=self.GREEN
            )
        else:
            self.msg_label.configure(text="锁定失败!", text_color=self.RED)

    def unlock(self):
        password = self.password_entry.get()
        if password == self.locker.unlock_password:
            if self.locker.stop_lock():
                self.status_label.configure(text="未锁定", text_color=self.GREEN)
                self.lock_button.configure(state="normal", fg_color=self.ACCENT)
                self.change_pw_button.configure(state="normal")
                self.root.attributes('-topmost', False)
                self.unlock_frame.pack_forget()
                self._last_unlock_mode = False
                self.msg_label.configure(text="已成功解锁", text_color=self.GREEN)
            else:
                self.msg_label.configure(text="解锁失败，请重试", text_color=self.RED)
        else:
            self.locker.cancel_unlock_mode()
            self.unlock_frame.pack_forget()
            self._last_unlock_mode = False
            self.password_entry.delete(0, 'end')
            self.msg_label.configure(text="密码错误 — 连按3次 CapsLock 重新解锁", text_color=self.RED)

    def on_close(self):
        if self.locker.lock_active:
            return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        if result <= 32:
            messagebox.showerror("错误", "需要管理员权限!\n\n请右键选择'以管理员身份运行'")
        sys.exit(0)

    locker = SystemLocker()
    atexit.register(locker.emergency_restore)
    app = LockApp(locker)

    try:
        app.run()
    except Exception:
        locker.emergency_restore()
        traceback.print_exc()


if __name__ == "__main__":
    main()
