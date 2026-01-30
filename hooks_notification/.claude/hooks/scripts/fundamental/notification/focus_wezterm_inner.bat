@echo off
REM 実際の処理を行う内部バッチファイル（VBSから非表示で呼び出される）

cd /d "%~dp0"
echo [%date% %time%] focus_wezterm_inner.bat executed >> ..\..\..\logs\focus_wezterm.log

REM wezterm cli用のソケットパスを設定（gui-sock-*を探す）
for %%f in ("%USERPROFILE%\.local\share\wezterm\gui-sock-*") do (
    set "WEZTERM_UNIX_SOCKET=%%f"
)
echo WEZTERM_UNIX_SOCKET=%WEZTERM_UNIX_SOCKET% >> ..\..\..\logs\focus_wezterm.log

echo [%date% %time%] Running: uv run python focus_wezterm.py >> ..\..\..\logs\focus_wezterm.log
uv run python focus_wezterm.py >> ..\..\..\logs\focus_wezterm.log 2>&1
echo [%date% %time%] Exit code: %ERRORLEVEL% >> ..\..\..\logs\focus_wezterm.log
