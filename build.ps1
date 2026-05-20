Write-Host "=== 系统锁定工具 - 打包脚本 ===" -ForegroundColor Cyan
Write-Host ""

$pythonPath = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $found = Get-Command $cmd -ErrorAction Stop
        $pythonPath = $cmd
        Write-Host "[OK] Python: $($found.Source)" -ForegroundColor Green
        break
    } catch {}
}

if (-not $pythonPath) {
    Write-Host "[FAIL] Python not found! Please install Python 3.7+" -ForegroundColor Red
    Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
& $pythonPath -m pip install pyinstaller --user

Write-Host ""
Write-Host "Building..." -ForegroundColor Yellow

& $pythonPath -m PyInstaller --onefile --windowed --uac-admin --name="SystemLocker" main.pyw

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Build successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Output: $(Get-Location)\dist\SystemLocker.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  Right-click SystemLocker.exe -> Run as administrator" -ForegroundColor White
    Write-Host "  Default password: 123456" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "[FAIL] Build failed!" -ForegroundColor Red
}

Write-Host ""
Read-Host "Press Enter to exit"
