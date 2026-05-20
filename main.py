import ctypes
import ctypes.wintypes
import sys
import winreg
import threading
import time
from tkinter import Tk, Label, Entry, Button, messagebox, Frame
from tkinter import ttk

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_ESCAPE = 0x1B
VK_TAB = 0x09
VK_CONTROL = 0x11
VK_ALT = 0x12
VK_DELETE = 0x2E
VK_F4 = 0x73
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_PAUSE = 0x13
VK_CAPSLOCK = 0x14
VK_NUMLOCK = 0x90
VK_SCROLL = 0x91
VK_PRINTSCREEN = 0x2C
VK_INSERT = 0x2D
VK_HOME = 0x24
VK_END = 0x23
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_R = 0x52
VK_D = 0x44
VK_E = 0x45
VK_L = 0x4C
VK_U = 0x55

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105

ES_CONTINUOUS = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_int),
        ("scanCode", ctypes.c_int),
        ("flags", ctypes.c_int),
        ("time", ctypes.c_int),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_void_p))
    ]

HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(KBDLLHOOKSTRUCT))

class ScreenLocker:
    def __init__(self):
        self.hook_handle = None
        self.lock_active = False
        self.unlock_password = "123456"
        self.original_display_timeout = 0
        self.original_screensaver_timeout = 0
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.win_pressed = False
        self._hook_proc = None

    def disable_display_sleep(self):
        try:
            self.original_display_timeout = self.get_display_timeout()
            self.original_screensaver_timeout = self.get_screensaver_timeout()
            
            self.set_display_timeout(0)
            self.set_screensaver_timeout(0)
            
            kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)
            return True
        except Exception as e:
            print(f"Error disabling display sleep: {e}")
            return False

    def restore_display_settings(self):
        try:
            self.set_display_timeout(self.original_display_timeout)
            self.set_screensaver_timeout(self.original_screensaver_timeout)
            kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            return True
        except Exception as e:
            print(f"Error restoring display settings: {e}")
            return False

    def get_display_timeout(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\PowerCfg\GlobalPowerPolicy")
            value, _ = winreg.QueryValueEx(key, "PowerPolicy")
            winreg.CloseKey(key)
            return value[12] if len(value) > 12 else 600
        except:
            return 600

    def set_display_timeout(self, timeout):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\PowerCfg\GlobalPowerPolicy", 0, winreg.KEY_SET_VALUE)
            value = bytearray([0]*16)
            value[12] = timeout & 0xFF
            value[13] = (timeout >> 8) & 0xFF
            winreg.SetValueEx(key, "PowerPolicy", 0, winreg.REG_BINARY, bytes(value))
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Error setting display timeout: {e}")

    def get_screensaver_timeout(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
            value, _ = winreg.QueryValueEx(key, "ScreenSaveTimeOut")
            winreg.CloseKey(key)
            return int(value)
        except:
            return 600

    def set_screensaver_timeout(self, timeout):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "ScreenSaveTimeOut", 0, winreg.REG_SZ, str(timeout))
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Error setting screensaver timeout: {e}")

    def disable_usb_storage(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\USBSTOR", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, 4)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Error disabling USB storage: {e}")
            return False

    def enable_usb_storage(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\USBSTOR", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, 3)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Error enabling USB storage: {e}")
            return False

    def keyboard_hook_callback(self, nCode, wParam, lParam):
        if nCode >= 0 and self.lock_active:
            try:
                vk_code = lParam.contents.vkCode
                
                # Track modifier keys
                if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                    if vk_code == VK_CONTROL:
                        self.ctrl_pressed = True
                    elif vk_code == VK_ALT:
                        self.alt_pressed = True
                    elif vk_code == VK_LWIN or vk_code == VK_RWIN:
                        self.win_pressed = True
                
                elif wParam == WM_KEYUP or wParam == WM_SYSKEYUP:
                    if vk_code == VK_CONTROL:
                        self.ctrl_pressed = False
                    elif vk_code == VK_ALT:
                        self.alt_pressed = False
                    elif vk_code == VK_LWIN or vk_code == VK_RWIN:
                        self.win_pressed = False
                
                # Block all keyboard input when locked
                return 1

            except Exception as e:
                print(f"Error in hook callback: {e}")

        return user32.CallNextHookEx(self.hook_handle, nCode, wParam, ctypes.cast(lParam, ctypes.POINTER(ctypes.c_void_p)))

    def set_keyboard_hook(self):
        try:
            self._hook_proc = HOOKPROC(self.keyboard_hook_callback)
            # For WH_KEYBOARD_LL, hInstance can be 0
            self.hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, 0, 0)
            if not self.hook_handle:
                raise ctypes.WinError(ctypes.get_last_error())
            print("Keyboard hook installed successfully")
            return True
        except Exception as e:
            print(f"Error setting keyboard hook: {e}")
            return False

    def remove_keyboard_hook(self):
        if self.hook_handle:
            try:
                result = user32.UnhookWindowsHookEx(self.hook_handle)
                print(f"Unhook result: {result}")
                self.hook_handle = None
                return True
            except Exception as e:
                print(f"Error removing keyboard hook: {e}")
                return False
        return True

    def message_loop(self):
        print("Message loop started")
        msg = ctypes.wintypes.MSG()
        while self.lock_active:
            # Check for messages with a timeout so we can check lock_active
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == 0x0012:  # WM_QUIT
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)
        print("Message loop stopped")

    def start_lock(self):
        try:
            self.lock_active = True
            
            sleep_ok = self.disable_display_sleep()
            usb_ok = self.disable_usb_storage()
            hook_ok = self.set_keyboard_hook()
            
            if hook_ok:
                self.msg_thread = threading.Thread(target=self.message_loop, daemon=True)
                self.msg_thread.start()
            
            return True, f"屏幕常亮: {'成功' if sleep_ok else '失败'}, USB禁用: {'成功' if usb_ok else '失败'}, 键盘钩子: {'成功' if hook_ok else '失败'}"
        except Exception as e:
            print(f"Error starting lock: {e}")
            return False, str(e)

    def stop_lock(self):
        try:
            self.lock_active = False
            time.sleep(0.2)
            
            self.remove_keyboard_hook()
            self.enable_usb_storage()
            self.restore_display_settings()
            
            return True
        except Exception as e:
            print(f"Error stopping lock: {e}")
            return False

class LockApp:
    def __init__(self, locker):
        self.locker = locker
        self.root = Tk()
        self.root.title("系统锁定工具")
        self.root.geometry("450x350")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f0f0")
        
        # Bring window to front and keep it on top
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', True)
        
        self.style = ttk.Style()
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0", font=("Arial", 12))
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        title_label = ttk.Label(main_frame, text="系统锁定工具", font=("Arial", 20, "bold"))
        title_label.pack(pady=(0, 20))
        
        self.status_label = ttk.Label(main_frame, text="当前状态: 未锁定", font=("Arial", 14), foreground="green")
        self.status_label.pack(pady=(0, 25))
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        self.lock_button = Button(button_frame, text="开始锁定", command=self.lock, 
                                  width=18, height=2, bg="#dc3545", fg="white",
                                  font=("Arial", 12, "bold"), borderwidth=0)
        self.lock_button.grid(row=0, column=0, padx=5)
        
        self.unlock_button = Button(button_frame, text="解锁", command=self.unlock, 
                                    width=18, height=2, bg="#28a745", fg="white",
                                    font=("Arial", 12, "bold"), borderwidth=0)
        self.unlock_button.grid(row=0, column=1, padx=5)
        
        password_frame = ttk.Frame(main_frame)
        password_frame.pack(pady=20)
        
        password_label = ttk.Label(password_frame, text="解锁密码:", font=("Arial", 12))
        password_label.pack(pady=(0, 10))
        
        self.password_entry = Entry(password_frame, show="*", width=35, 
                                    font=("Arial", 14), justify="center")
        self.password_entry.pack(pady=(0, 15))
        
        features_frame = ttk.Frame(main_frame)
        features_frame.pack(pady=10)
        
        features_title = ttk.Label(features_frame, text="锁定功能:", font=("Arial", 10, "bold"))
        features_title.pack(pady=(0, 10))
        
        features = [
            "• 禁用所有键盘输入",
            "• 禁用USB存储设备",
            "• 保持屏幕常亮",
            "• 防止系统睡眠"
        ]
        
        for feature in features:
            feature_label = ttk.Label(features_frame, text=feature, font=("Arial", 10), foreground="#666")
            feature_label.pack(anchor="w", pady=2)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Handle Alt+F4
        self.root.bind("<Alt-F4>", lambda e: "break")

    def lock(self):
        success, msg = self.locker.start_lock()
        if success:
            self.status_label.config(text="当前状态: 已锁定", foreground="red")
            self.lock_button.config(state="disabled")
            # Focus on password entry
            self.password_entry.focus_set()
            messagebox.showinfo("提示", f"已成功锁定!\n\n{msg}\n\n解锁密码: 123456")
        else:
            messagebox.showerror("错误", f"锁定失败!\n\n{msg}")

    def unlock(self):
        password = self.password_entry.get()
        if password == self.locker.unlock_password:
            if self.locker.stop_lock():
                self.status_label.config(text="当前状态: 未锁定", foreground="green")
                self.lock_button.config(state="normal")
                self.password_entry.delete(0, 'end')
                messagebox.showinfo("提示", "已成功解锁")
            else:
                messagebox.showerror("错误", "解锁失败，请重试")
        else:
            messagebox.showerror("错误", "密码错误，请重试")

    def on_close(self):
        if self.locker.lock_active:
            if messagebox.askyesno("确认", "系统当前已锁定，确定要退出程序吗？"):
                self.locker.stop_lock()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        if result <= 32:
            messagebox.showerror("错误", "需要管理员权限才能运行此程序!\n\n请右键点击程序，选择'以管理员身份运行'")
        sys.exit(0)
    
    locker = ScreenLocker()
    app = LockApp(locker)
    app.run()