# SystemLocker - Windows 系统锁定工具

适用于笔记本电脑的展示/防误触锁定工具。锁定后键盘、鼠标、USB 全部禁用，屏幕保持常亮，仅通过特定组合键+密码解锁。

## 功能

| 功能 | 说明 |
|------|------|
| 键盘锁定 | 禁用所有按键，仅放行 ScrollLock（触发解锁）和字母/数字键（输入密码） |
| 鼠标锁定 | 完全禁用鼠标输入 |
| USB 禁用 | 禁用所有 USB 设备（笔记本自带键盘不受影响） |
| 屏幕常亮 | 禁用屏保和自动息屏 |
| 防杀后台 | 通过 `SetThreadExecutionState` 阻止系统休眠 |
| 崩溃恢复 | 注册 `atexit` 回调，程序异常退出时自动恢复系统设置 |

## 解锁流程

```
连按3次 ScrollLock → 弹出密码输入框 → 输入密码 → 按 Enter 解锁
```

- 3次 ScrollLock 需在 2 秒内完成
- 密码输入仅支持字母、数字、退格和回车
- 默认密码: `123456`

## 使用方法

### 直接运行

```bash
# 需要管理员权限
python main.py
```

### 打包成 EXE

```powershell
# PowerShell
.\build.ps1

# 或 CMD
.\build.bat
```

打包后右键 `dist\SystemLocker.exe` → 以管理员身份运行。

## 修改密码

编辑 `main.py` 第 83 行：

```python
self.unlock_password = "你的密码"
```

## 注意事项

- **必须以管理员身份运行**
- 本程序专为笔记本电脑设计（自带键盘非 USB，可禁用所有 USB）
- Ctrl+Alt+Del 是 Windows 安全序列，低级键盘钩子无法拦截
- USB 禁用通过修改注册表实现，需要重启或重新插拔设备生效
- 程序崩溃时会通过 `atexit` 尝试恢复设置，但极端情况可能需要手动恢复

## 手动恢复（紧急情况）

如果程序崩溃且设置未恢复，可手动执行：

```reg
; 恢复 USB 存储
Windows Registry Editor Version 5.00
[HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\USBSTOR]
"Start"=dword:00000003

; 恢复屏保
[HKEY_CURRENT_USER\Control Panel\Desktop]
"ScreenSaveActive"="1"
"ScreenSaveTimeOut"="600"
```
