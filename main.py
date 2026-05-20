import ctypes
import ctypes.wintypes
import sys
import winreg
import threading
import time
import atexit
import traceback
from tkinter import Tk, Label, Entry, Button, Frame

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
        self.unlock_password = "123456"

        self._kb_hook_proc = None
        self._mouse_hook_proc = None
        self._msg_thread = None

        self.caps_lock_press_times = []
        self.unlock_mode = False
        self._unlock_mode_changed = False

        self._original_screensaver_active = None
        self._original_screensaver_timeout = None

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
            if self.unlock_mode:
                return user32.CallNextHookEx(
                    self.mouse_hook_handle, nCode, wParam,
                    ctypes.cast(lParam, ctypes.POINTER(ctypes.c_void_p))
                )
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
    def __init__(self, locker):
        self.locker = locker
        self.root = Tk()
        self.root.title("系统锁定工具")
        self.root.geometry("500x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        self._last_unlock_mode = False

        self._build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Alt-F4>", lambda e: "break")

        self._poll_state()

    def _build_ui(self):
        main_frame = Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill="both", expand=True, padx=30, pady=20)

        title = Label(main_frame, text="系统锁定工具", font=("Arial", 22, "bold"),
                       bg="#1a1a2e", fg="#e94560")
        title.pack(pady=(0, 10))

        self.status_label = Label(main_frame, text="当前状态: 未锁定",
                                   font=("Arial", 14), bg="#1a1a2e", fg="#16c79a")
        self.status_label.pack(pady=(0, 15))

        self.lock_button = Button(main_frame, text="开始锁定", command=self.lock,
                                   width=20, height=2, bg="#e94560", fg="white",
                                   font=("Arial", 13, "bold"), borderwidth=0,
                                   activebackground="#c81e45", activeforeground="white")
        self.lock_button.pack(pady=8)

        self.msg_label = Label(main_frame, text="", font=("Arial", 11),
                                bg="#1a1a2e", fg="#16c79a", wraplength=420)
        self.msg_label.pack(pady=5)

        self.unlock_frame = Frame(main_frame, bg="#1a1a2e")

        self.unlock_hint = Label(self.unlock_frame, text="请输入密码后按 Enter 解锁",
                                  font=("Arial", 11), bg="#1a1a2e", fg="#16c79a")
        self.unlock_hint.pack(pady=(0, 8))

        self.password_entry = Entry(self.unlock_frame, show="*", width=30,
                                     font=("Arial", 16), justify="center",
                                     bg="#16213e", fg="white", insertbackground="white")
        self.password_entry.pack(pady=(0, 8))

        self.unlock_button = Button(self.unlock_frame, text="解锁 (Enter)",
                                     command=self.unlock,
                                     width=20, height=2, bg="#16c79a", fg="white",
                                     font=("Arial", 13, "bold"), borderwidth=0,
                                     activebackground="#0f9b7a", activeforeground="white")
        self.unlock_button.pack(pady=5)

        self.password_entry.bind("<Return>", lambda e: self.unlock())

        hint_frame = Frame(main_frame, bg="#1a1a2e")
        hint_frame.pack(side="bottom", fill="x", pady=(10, 0))

        hints = [
            "锁定后: 键盘/鼠标禁用，USB存储禁用，屏幕常亮",
            "解锁: 连按3次 CapsLock(大写锁定) → 输入密码 → Enter",
            "解锁模式下鼠标可用，密码错误自动关闭解锁模式",
            f"默认密码: {self.locker.unlock_password}"
        ]
        for h in hints:
            Label(hint_frame, text=h, font=("Arial", 9), bg="#1a1a2e", fg="#555").pack(anchor="w")

    def _poll_state(self):
        try:
            if self.locker._unlock_mode_changed:
                self.locker._unlock_mode_changed = False
                new_mode = self.locker.unlock_mode
                if new_mode != self._last_unlock_mode:
                    self._last_unlock_mode = new_mode
                    self._update_unlock_ui(new_mode)
        except:
            pass
        self.root.after(100, self._poll_state)

    def _update_unlock_ui(self, unlock_mode):
        if unlock_mode:
            self.unlock_frame.pack(pady=8)
            self.password_entry.delete(0, 'end')
            self.password_entry.focus_set()
            self.msg_label.config(text="解锁模式已开启 - 请输入密码", fg="#16c79a")
        else:
            self.unlock_frame.pack_forget()
            if self.locker.lock_active:
                self.msg_label.config(text="已锁定! 连按3次 CapsLock 解锁", fg="#16c79a")

    def lock(self):
        success = self.locker.start_lock()
        if success:
            self.status_label.config(text="当前状态: 已锁定", fg="#e94560")
            self.lock_button.config(state="disabled")
            self.root.attributes('-topmost', True)
            self.root.lift()
            self.root.focus_force()
            self.msg_label.config(
                text="已锁定! 连按3次 CapsLock(大写锁定) 解锁",
                fg="#16c79a"
            )
        else:
            self.msg_label.config(text="锁定失败!", fg="#e94560")

    def unlock(self):
        password = self.password_entry.get()
        if password == self.locker.unlock_password:
            if self.locker.stop_lock():
                self.status_label.config(text="当前状态: 未锁定", fg="#16c79a")
                self.lock_button.config(state="normal")
                self.root.attributes('-topmost', False)
                self.unlock_frame.pack_forget()
                self._last_unlock_mode = False
                self.msg_label.config(text="已成功解锁", fg="#16c79a")
            else:
                self.msg_label.config(text="解锁失败，请重试", fg="#e94560")
        else:
            self.locker.cancel_unlock_mode()
            self.unlock_frame.pack_forget()
            self._last_unlock_mode = False
            self.password_entry.delete(0, 'end')
            self.msg_label.config(text="密码错误! 连按3次 CapsLock 重新解锁", fg="#e94560")

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
            from tkinter import messagebox
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
