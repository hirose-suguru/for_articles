@echo off
REM 実際の処理を行う内部バッチファイル（VBSから非表示で呼び出される）

cd /d "%~dp0"
set "LOGFILE=..\..\..\logs\focus_wezterm.log"
set "DEBUGLOG=..\..\..\logs\hook_debug.log"
set "LOCKFILE=..\..\..\cache\focus_wezterm.lock"
set "LOCK_TIMEOUT_SEC=30"
set "MY_PID="
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq cmd.exe" /fo list 2^>nul ^| findstr /i "PID:"') do (
    if not defined MY_PID set "MY_PID=%%a"
)

REM === ロックファイルによる排他制御（新しいプロセス優先） ===
REM ロックファイルが存在するか確認
if exist "%LOCKFILE%" (
    REM ロックファイルから古いPIDを読み取る
    set "OLD_PID="
    for /f "tokens=1" %%p in ('type "%LOCKFILE%" 2^>nul') do set "OLD_PID=%%p"

    REM ロックファイルの経過時間をチェック（PowerShellで秒数を取得）
    set "LOCK_AGE="
    for /f %%a in ('powershell -NoProfile -Command "(New-TimeSpan -Start (Get-Item '%LOCKFILE%').LastWriteTime -End (Get-Date)).TotalSeconds" 2^>nul') do set "LOCK_AGE=%%a"

    REM 小数点を除去して整数比較（30.5 -> 30）
    set "LOCK_AGE_INT=0"
    if defined LOCK_AGE (
        for /f "tokens=1 delims=." %%i in ("%LOCK_AGE%") do set "LOCK_AGE_INT=%%i"
    )

    REM 競合ログを記録
    >> "%DEBUGLOG%" 2>nul echo [%date% %time%] focus_wezterm_inner.bat: Lock conflict detected - old_pid=%OLD_PID%, my_pid=%MY_PID%, lock_age=%LOCK_AGE_INT%s

    REM 古いプロセスをkill（タイムアウト関係なく新しいプロセス優先）
    if defined OLD_PID (
        >> "%DEBUGLOG%" 2>nul echo [%date% %time%] focus_wezterm_inner.bat: Killing old process PID=%OLD_PID%
        taskkill /F /PID %OLD_PID% >nul 2>&1
    )

    REM 古いロックを削除
    del "%LOCKFILE%" 2>nul
)

REM ロックファイルを作成（PIDを記録）
echo %MY_PID% > "%LOCKFILE%"

REM ログ書き込みテスト（ロックされているか確認）
>> "%LOGFILE%" 2>nul echo [%date% %time%] focus_wezterm_inner.bat executed
if errorlevel 1 (
    REM ログファイルがロックされている場合、ロック元を調べてdebug_logに記録
    >> "%DEBUGLOG%" 2>nul echo [%date% %time%] focus_wezterm_inner.bat: focus_wezterm.log is locked, checking...
    uv run python check_file_lock.py "%LOGFILE%" >> "%DEBUGLOG%" 2>&1
)

REM wezterm cli用のソケットパスを設定（gui-sock-*を探す）
for %%f in ("%USERPROFILE%\.local\share\wezterm\gui-sock-*") do (
    set "WEZTERM_UNIX_SOCKET=%%f"
)
>> "%LOGFILE%" 2>nul echo WEZTERM_UNIX_SOCKET=%WEZTERM_UNIX_SOCKET%

>> "%LOGFILE%" 2>nul echo [%date% %time%] Running: uv run python focus_wezterm.py

REM Pythonスクリプト実行（ログがロックされていても実行する）
uv run python focus_wezterm.py >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    REM ログ書き込み失敗時はログなしで再実行
    uv run python focus_wezterm.py 2>nul
)

>> "%LOGFILE%" 2>nul echo [%date% %time%] Exit code: %ERRORLEVEL%

REM === ロックファイルを削除 ===
del "%LOCKFILE%" 2>nul
