# system-locker

Windows 系统锁定工具。适用于笔记本电脑的展示/防误触场景，锁定后键盘、鼠标禁用，USB存储禁用，屏幕保持常亮，通过 CapsLock+密码解锁。

## 功能

| 功能 | 说明 |
|------|------|
| 键盘锁定 | 禁用所有按键，仅放行 CapsLock（触发解锁）和字母/数字键（输入密码） |
| 鼠标锁定 | 锁定时禁用，解锁模式下恢复可用 |
| USB存储禁用 | 禁用U盘等USB存储设备（不影响笔记本自带键盘/触控板） |
| 屏幕常亮 | 禁用屏保和自动息屏 |
| 防杀后台 | 通过 `SetThreadExecutionState` 阻止系统休眠 |
| 密码保护 | 支持修改密码，持久化保存到 config.json |
| 崩溃恢复 | 注册 `atexit` 回调，程序异常退出时自动恢复系统设置 |

## 解锁流程

```
连按3次 CapsLock（大写锁定）→ 弹出密码输入框（鼠标恢复可用）→ 输入密码 → Enter 解锁
```

- 3次 CapsLock 需在 2 秒内完成
- 密码输入仅支持字母、数字、退格和回车
- 解锁模式下鼠标可用，方便点击解锁按钮
- 密码错误自动关闭解锁模式，需重新触发

## 使用方法

### 直接运行

```bash
# 需要管理员权限
python main.py
```

### 打包成 EXE

```powershell
.\build.ps1
```

打包后右键 `dist\SystemLocker.exe` → 以管理员身份运行。

## 修改密码

1. 点击主界面"修改密码"按钮
2. 输入当前密码 → 输入新密码 → 确认新密码
3. 密码保存到 `config.json`，下次启动自动加载

## 项目结构

```
system-locker/
├── main.py           # 主程序
├── build.ps1         # PowerShell 打包脚本
├── requirements.txt  # Python 依赖
├── .gitignore        # Git 忽略规则
├── README.md         # 说明文档
└── config.json       # 密码配置（运行后自动生成，不提交到git）
```

## 注意事项

- **必须以管理员身份运行**
- 本程序专为笔记本电脑设计（自带键盘非 USB，可安全禁用 USB 存储）
- Ctrl+Alt+Del 是 Windows 安全序列，低级键盘钩子无法拦截，始终可用作紧急手段
- USB存储禁用仅影响 USBSTOR（U盘等），不影响笔记本自带键盘/触控板
- 锁定时无法关闭窗口，必须先解锁
- 程序崩溃时会通过 `atexit` 尝试恢复设置

## 紧急恢复

如果程序崩溃且设置未恢复，在命令行（管理员）执行：

```cmd
reg add "HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR" /v Start /t REG_DWORD /d 3 /f
reg add "HKCU\Control Panel\Desktop" /v ScreenSaveActive /d 1 /f
reg add "HKCU\Control Panel\Desktop" /v ScreenSaveTimeOut /d 600 /f
```
