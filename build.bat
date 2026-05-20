@echo off
echo === SystemLocker Build ===
echo.
echo Installing PyInstaller...
pip install pyinstaller
echo.
echo Building...
pyinstaller --onefile --windowed --uac-admin --name="SystemLocker" main.py
echo.
if exist "dist\SystemLocker.exe" (
    echo [OK] Build successful!
    echo Output: dist\SystemLocker.exe
) else (
    echo [FAIL] Build failed!
)
echo.
pause
