# 系统锁定工具 - 打包脚本

Write-Host "=== 系统锁定工具打包脚本 ===" -ForegroundColor Cyan
Write-Host ""

# 检查Python是否安装
try {
    $pythonCmd = Get-Command python -ErrorAction Stop
    Write-Host "✓ Python已找到: $($pythonCmd.Source)" -ForegroundColor Green
} catch {
    try {
        $pythonCmd = Get-Command python3 -ErrorAction Stop
        Write-Host "✓ Python3已找到: $($pythonCmd.Source)" -ForegroundColor Green
        $pythonPath = "python3"
    } catch {
        try {
            $pythonCmd = Get-Command py -ErrorAction Stop
            Write-Host "✓ Python Launcher已找到" -ForegroundColor Green
            $pythonPath = "py"
        } catch {
            Write-Host "✗ 未找到Python! 请先安装Python 3.7或更高版本" -ForegroundColor Red
            Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
            Read-Host "按回车键退出"
            exit 1
        }
    }
}

Write-Host ""
Write-Host "正在安装PyInstaller..." -ForegroundColor Yellow
& $pythonPath -m pip install pyinstaller --user

Write-Host ""
Write-Host "正在打包程序..." -ForegroundColor Yellow

# PyInstaller参数说明:
# --onefile: 打包成单个exe文件
# --windowed: 不显示控制台窗口
# --uac-admin: 请求管理员权限
# --name: 输出文件名
& $pythonPath -m PyInstaller --onefile --windowed --uac-admin --name="系统锁定工具" main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ 打包成功!" -ForegroundColor Green
    Write-Host ""
    Write-Host "可执行文件位置: $(Get-Location)\dist\系统锁定工具.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "使用说明:" -ForegroundColor Yellow
    Write-Host "1. 右键点击 '系统锁定工具.exe'" -ForegroundColor White
    Write-Host "2. 选择 '以管理员身份运行'" -ForegroundColor White
    Write-Host "3. 默认解锁密码: 123456" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "✗ 打包失败!" -ForegroundColor Red
}

Write-Host ""
Read-Host "按回车键退出"
