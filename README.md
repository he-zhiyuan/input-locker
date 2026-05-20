# SystemLocker - Windows 系统锁定工具

适用于笔记本电脑的展示/防误触锁定工具。锁定后键盘、鼠标禁用，USB存储禁用，屏幕保持常亮，仅通过 ScrollLock+密码解锁。

## 功能

| 功能 | 说明 |
|------|------|
| 键盘锁定 | 禁用所有按键，仅放行 ScrollLock（触发解锁）和字母/数字键（输入密码） |
| 鼠标锁定 | 锁定时禁用，解锁模式下恢复可用 |
| USB存储禁用 | 禁用U盘等USB存储设备（不影响笔记本自带键盘/触控板） |
| 屏幕常亮 | 禁用屏保和自动息屏 |
| 防杀后台 | 通过 `SetThreadExecutionState` 阻止系统休眠 |
| 崩溃恢复 | 注册 `atexit` 回调，程序异常退出时自动恢复系统设置 |

## 解锁流程

```
连按3次 ScrollLock → 弹出密码输入框（鼠标恢复可用）→ 输入密码 → Enter 解锁
```

- 3次 ScrollLock 需在 2 秒内完成
- 密码输入仅支持字母、数字、退格和回车
- 解锁模式下鼠标可用，方便操作
- 默认密码: `123456`

## 使用方法

### 直接运行

```bash
python main.py
```

### 打包成 EXE

```powershell
.\build.ps1
```

打包后右键 `dist\SystemLocker.exe` → 以管理员身份运行。

## 修改密码

编辑 `main.py` 第 70 行：

```python
self.unlock_password = "你的密码"
```

## 注意事项

- **必须以管理员身份运行**
- 本程序专为笔记本电脑设计（自带键盘非 USB）
- Ctrl+Alt+Del 是 Windows 安全序列，低级键盘钩子无法拦截
- USB存储禁用仅影响 USBSTOR（U盘等），不影响笔记本自带键盘/触控板
- 锁定时关闭窗口被禁止，必须先解锁
- 程序崩溃时会通过 `atexit` 尝试恢复设置

## 手动恢复（紧急情况）

如果程序崩溃且设置未恢复，在命令行执行：

```cmd
reg add "HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR" /v Start /t REG_DWORD /d 3 /f
reg add "HKCU\Control Panel\Desktop" /v ScreenSaveActive /d 1 /f
reg add "HKCU\Control Panel\Desktop" /v ScreenSaveTimeOut /d 600 /f
```
