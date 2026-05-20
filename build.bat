@echo off
echo 正在安装PyInstaller...
pip install pyinstaller

echo.
echo 正在打包成可执行文件...
pyinstaller --onefile --windowed --icon=NONE --name="系统锁定工具" main.py

echo.
echo 打包完成！
echo 可执行文件位于 dist 文件夹中
pause