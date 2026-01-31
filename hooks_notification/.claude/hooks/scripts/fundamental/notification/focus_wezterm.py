#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
focus_wezterm.py
通知クリック時にWeztermウィンドウを前面にフォーカスする

機能:
1. 一時ファイルからproject_dirを読み込む
2. wezterm cli listでCWDが一致するタブを探す
3. wezterm cli activate-tabで正しいタブをアクティブにする
4. ウィンドウを前面にフォーカスする

Usage:
    python focus_wezterm.py
"""
import sys
import subprocess
import json
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import NamedTuple

# hook_utilsからdebug_logとget_path_from_configをインポート
sys.path.insert(0, str(Path(__file__).parent.parent))
from hook_utils import debug_log, get_path_from_config

# 通知クリック時に参照するproject_dirの一時ファイル
PROJECT_DIR_CACHE = get_path_from_config("notification_wezterm_cache")


def normalize_wezterm_cwd(cwd: str) -> str:
    """
    wezterm cli listのCWD（file:///C:/path/形式）を通常のパス形式に変換する

    Args:
        cwd: file:///C:/path/ 形式のCWD

    Returns:
        C:/path 形式の正規化されたパス
    """
    if cwd.startswith("file:///"):
        # file:///C:/path/ -> C:/path
        parsed = urlparse(cwd)
        path = unquote(parsed.path)
        # Windows: /C:/path -> C:/path
        if len(path) > 2 and path[0] == '/' and path[2] == ':':
            path = path[1:]
        # 末尾のスラッシュを除去
        return path.rstrip('/')
    return cwd.rstrip('/')


def get_target_project_dir() -> str | None:
    """
    一時ファイルからキャッシュデータを読み込む

    Returns:
        CacheData: project_dir, hwnd, pane_id, wezterm_socketを含むNamedTuple
    """
    if not PROJECT_DIR_CACHE.exists():
        return CacheData(None, None, None, None)
    try:
        content = PROJECT_DIR_CACHE.read_text(encoding="utf-8").strip()
        # JSON形式を試す（新形式）
        try:
            data = json.loads(content)
            return CacheData(
                project_dir=data.get("project_dir"),
                hwnd=data.get("hwnd"),
                pane_id=data.get("pane_id"),
                wezterm_socket=data.get("wezterm_socket")
            )
        except json.JSONDecodeError:
            # 旧形式（プレーンテキスト）との互換性
            return CacheData(project_dir=content, hwnd=None, pane_id=None, wezterm_socket=None)
    except Exception:
        return CacheData(None, None, None, None)


def get_target_project_dir() -> str | None:
    """
    一時ファイルからターゲットのproject_dirを読み込む（後方互換用）

    Returns:
        project_dirのパス、またはNone
    """
    return get_cache_data().project_dir


def find_and_activate_tab(target_dir: str) -> tuple[bool, int | None]:
    """
    wezterm cli listで対象ディレクトリのタブを探してアクティブにする

    Claude Codeのタブを優先して選択する（タイトルに ⠂ や ✳ が含まれるタブ）

    Args:
        target_dir: 対象のプロジェクトディレクトリパス

    Returns:
        tuple[bool, int | None]: (成功フラグ, window_id)
    """
    # Claude Code のタイトルに含まれる特徴的な文字
    CLAUDE_TITLE_MARKERS = ['⠂', '✳', '⠈', '⠐', '⠠', '⠄', '⠁']

    try:
        import os
        import glob as glob_module
        debug_log("find_and_activate_tab: Step 2a - checking environment")
        debug_log(f"find_and_activate_tab: PATH = {os.environ.get('PATH', 'NOT SET')[:200]}...")
        wezterm_socket = os.environ.get('WEZTERM_UNIX_SOCKET', 'NOT SET')
        debug_log(f"find_and_activate_tab: WEZTERM_UNIX_SOCKET = {wezterm_socket}")
        # ソケットファイルの存在確認
        if wezterm_socket != 'NOT SET':
            socket_exists = os.path.exists(wezterm_socket)
            debug_log(f"find_and_activate_tab: Step 2a - socket exists: {socket_exists}")
        # 実際に存在するソケットファイルを列挙
        wezterm_socket_dir = os.path.expanduser("~/.local/share/wezterm")
        if os.path.exists(wezterm_socket_dir):
            existing_sockets = glob_module.glob(os.path.join(wezterm_socket_dir, "gui-sock-*"))
            debug_log(f"find_and_activate_tab: Step 2a - existing sockets: {existing_sockets}")

        # wezterm のフルパスを確認
        import shutil
        wezterm_path = shutil.which("wezterm")
        debug_log(f"find_and_activate_tab: shutil.which('wezterm') = {wezterm_path}")

        # まず単純なコマンドでsubprocess.runが動くか確認
        debug_log("find_and_activate_tab: Step 2b - testing subprocess with echo")
        test_result = subprocess.run(
            ["cmd", "/c", "echo", "test"],
            capture_output=True,
            timeout=5
        )
        debug_log(f"find_and_activate_tab: Step 2b1 - echo returned: {test_result.stdout.decode().strip()}")

        debug_log("find_and_activate_tab: Step 2b2 - calling wezterm cli list with Popen")
        # wezterm cli list --format json でタブ一覧を取得（Popenで手動タイムアウト）
        import time

        # Windows用のcreationflagsを設定（新しいプロセスグループを作成）
        creationflags = 0
        if sys.platform == 'win32':
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            debug_log(f"find_and_activate_tab: Step 2b2a - using creationflags={creationflags}")

        # 一時ファイルに出力してパイプのブロックを回避
        import tempfile
        debug_log("find_and_activate_tab: Step 2b2b - creating temp files")
        stdout_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt')
        stderr_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt')
        debug_log(f"find_and_activate_tab: stdout={stdout_file.name}, stderr={stderr_file.name}")

        debug_log("find_and_activate_tab: Step 2b2c - calling Popen with file output")
        proc = subprocess.Popen(
            ["wezterm", "cli", "list", "--format", "json"],
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=creationflags
        )
        debug_log(f"find_and_activate_tab: Step 2b3 - Popen started, pid={proc.pid}")
        print(f"[POPEN] pid={proc.pid}", flush=True)

        # 手動で5秒タイムアウト（0.5秒ごとにチェック）
        # debug_logではなくprintを使用してファイルI/O問題を切り分け
        timeout_sec = 5
        start_time = time.time()
        loop_count = 0
        while proc.poll() is None:
            loop_count += 1
            elapsed = time.time() - start_time
            # ログは1秒ごとに出力
            if loop_count % 2 == 0:
                print(f"[WAIT] elapsed={elapsed:.1f}s, poll={proc.poll()}", flush=True)
            if elapsed > timeout_sec:
                print(f"[TIMEOUT] after {elapsed:.1f}s, killing pid={proc.pid}", flush=True)
                debug_log(f"find_and_activate_tab: TIMEOUT after {elapsed:.1f}s, killing pid={proc.pid}")
                try:
                    proc.kill()
                    print("[KILL] kill() called", flush=True)
                    proc.wait(timeout=2)
                    print("[KILL] wait() completed", flush=True)
                except Exception as e:
                    print(f"[KILL] error: {e}", flush=True)
                raise subprocess.TimeoutExpired(cmd="wezterm cli list", timeout=timeout_sec)
            time.sleep(0.5)

        # プロセス終了を待つ
        proc.wait()

        # 一時ファイルを閉じてから読み込む
        stdout_file.close()
        stderr_file.close()

        try:
            with open(stdout_file.name, 'r', encoding='utf-8') as f:
                stdout_content = f.read()
            with open(stderr_file.name, 'r', encoding='utf-8') as f:
                stderr_content = f.read()
        finally:
            # 一時ファイルを削除
            import os
            try:
                os.unlink(stdout_file.name)
                os.unlink(stderr_file.name)
            except Exception:
                pass

        debug_log(f"find_and_activate_tab: Step 2c - wezterm cli returned, returncode={proc.returncode}")
        debug_log(f"find_and_activate_tab: Step 2c - stdout_len={len(stdout_content)}, stderr_len={len(stderr_content)}")
        if stderr_content:
            debug_log(f"find_and_activate_tab: Step 2c - stderr: {stderr_content[:500]}")
        if proc.returncode != 0:
            debug_log(f"find_and_activate_tab: Step 2c - FAILED, stdout: {stdout_content[:200]}")
            print(f"ERROR: wezterm cli list failed: {stderr_content}")
            return False, None

        # JSON をパース
        debug_log("find_and_activate_tab: Step 2d - parsing JSON")
        tabs = json.loads(stdout_content)
        debug_log(f"find_and_activate_tab: Step 2e - found {len(tabs)} tabs")
        target_normalized = Path(target_dir).resolve().as_posix().lower()

        # CWDがマッチするタブを収集
        matching_tabs = []
        for tab in tabs:
            cwd = tab.get("cwd", "")
            tab_cwd_normalized = normalize_wezterm_cwd(cwd).lower()

            if tab_cwd_normalized == target_normalized:
                matching_tabs.append(tab)

        debug_log(f"find_and_activate_tab: Step 2f - {len(matching_tabs)} matching tabs")
        if not matching_tabs:
            print(f"ERROR: No tab found with CWD matching: {target_dir}")
            return False, None

        # Claude Code のタブを優先（タイトルにマーカーが含まれるもの）
        selected_tab = None
        for tab in matching_tabs:
            title = tab.get("title", "")
            if any(marker in title for marker in CLAUDE_TITLE_MARKERS):
                selected_tab = tab
                break

        # Claude タブが見つからなければ最初のマッチを使用
        if selected_tab is None:
            selected_tab = matching_tabs[0]

        tab_id = selected_tab.get("tab_id")
        window_id = selected_tab.get("window_id")
        debug_log(f"find_and_activate_tab: Step 2g - selected tab_id={tab_id}, window_id={window_id}")

        if tab_id is not None:
            # タブをアクティブにする
            debug_log("find_and_activate_tab: Step 2h - calling wezterm cli activate-tab")
            activate_result = subprocess.run(
                ["wezterm", "cli", "activate-tab", "--tab-id", str(tab_id)],
                capture_output=True,
                timeout=5
            )
            debug_log(f"find_and_activate_tab: Step 2i - activate returned, returncode={activate_result.returncode}")
            if activate_result.returncode == 0:
                # print(f"Activated tab {tab_id} (window {window_id}) for {target_dir}")
                return True, window_id
            else:
                print(f"ERROR: Failed to activate tab {tab_id}")

        return False, None

    except subprocess.TimeoutExpired:
        debug_log("find_and_activate_tab: TIMEOUT - wezterm cli timed out")
        print("ERROR: wezterm cli timed out")
        return False, None
    except json.JSONDecodeError as e:
        debug_log(f"find_and_activate_tab: JSON ERROR - {e}")
        print(f"ERROR: Failed to parse wezterm cli output: {e}")
        return False, None
    except FileNotFoundError:
        debug_log("find_and_activate_tab: FILE NOT FOUND - wezterm command not found")
        print("ERROR: wezterm command not found")
        return False, None
    except Exception as e:
        debug_log(f"find_and_activate_tab: EXCEPTION - {e}")
        print(f"ERROR: Error finding tab: {e}")
        return False, None


def get_window_title_for_window_id(window_id: int) -> str | None:
    """
    指定されたwindow_idのウィンドウタイトルを取得する

    Args:
        window_id: weztermのwindow_id

    Returns:
        ウィンドウタイトル、またはNone
    """
    try:
        result = subprocess.run(
            ["wezterm", "cli", "list", "--format", "json"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        tabs = json.loads(result.stdout.decode('utf-8'))
        for tab in tabs:
            if tab.get("window_id") == window_id:
                return tab.get("window_title")
        return None
    except Exception:
        return None


def is_hwnd_valid(hwnd: int) -> bool:
    """
    hwndが有効なWeztermウィンドウかどうか確認する

    Args:
        hwnd: ウィンドウハンドル

    Returns:
        bool: 有効なWeztermウィンドウならTrue
    """
    try:
        import win32gui
        if not win32gui.IsWindow(hwnd):
            return False
        if not win32gui.IsWindowVisible(hwnd):
            return False
        classname = win32gui.GetClassName(hwnd)
        return classname == "org.wezfurlong.wezterm"
    except Exception:
        return False


def focus_hwnd(hwnd: int) -> bool:
    """
    指定されたhwndのウィンドウを前面にフォーカスする

    Args:
        hwnd: フォーカスするウィンドウのハンドル

    Returns:
        bool: 成功時True、失敗時False
    """
    # debug_log(f"focus_hwnd: focusing hwnd={hwnd}")
    try:
        import win32gui
        import win32con
        import win32process
        import ctypes
        import time

        # debug_log("focus_hwnd: Step 1 - GetForegroundWindow()")
        before_hwnd = win32gui.GetForegroundWindow()
        # debug_log(f"focus_hwnd: before_hwnd={before_hwnd}")

        # debug_log("focus_hwnd: Step 2 - checking IsIconic")
        if win32gui.IsIconic(hwnd):
            # debug_log("focus_hwnd: ShowWindow (restore)")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # debug_log("focus_hwnd: Step 3 - AttachThreadInput")
        foreground_hwnd = win32gui.GetForegroundWindow()
        foreground_thread_id, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
        target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
        # debug_log(f"focus_hwnd: foreground_thread_id={foreground_thread_id}, target_thread_id={target_thread_id}")

        attach_result = ctypes.windll.user32.AttachThreadInput(foreground_thread_id, target_thread_id, True)
        # debug_log(f"focus_hwnd: AttachThreadInput result={attach_result}")

        try:
            # debug_log("focus_hwnd: Step 4 - BringWindowToTop + SetForegroundWindow")
            try:
                win32gui.BringWindowToTop(hwnd)
            except Exception as e:
                debug_log(f"focus_hwnd: BringWindowToTop failed: {e}")

            ctypes.windll.kernel32.SetLastError(0)
            sfw_result = ctypes.windll.user32.SetForegroundWindow(hwnd)
            # debug_log(f"focus_hwnd: SetForegroundWindow result={sfw_result}")
        finally:
            ctypes.windll.user32.AttachThreadInput(foreground_thread_id, target_thread_id, False)

        # debug_log("focus_hwnd: Step 5 - verifying focus")
        after_hwnd = win32gui.GetForegroundWindow()
        success = after_hwnd == hwnd
        # debug_log(f"focus_hwnd: after_hwnd={after_hwnd}, success={success}")

        # debug_log("focus_hwnd: finished")
        return True
    except Exception as e:
        debug_log(f"focus_hwnd: ERROR - {e}")
        return False


def focus_wezterm() -> bool:
    """
    Weztermウィンドウを前面にフォーカスする

    処理順序:
    1. キャッシュからproject_dirとhwndを読み込む
    2. hwndが有効ならそのウィンドウをフォーカス（最優先・高速）
    3. 失敗した場合、wezterm cli で対象タブをアクティブにする
    4. 対象のwindow_idに対応するウィンドウを前面にフォーカスする

    Returns:
        bool: 成功時True、失敗時False
    """
    debug_log("focus_wezterm: started")

    if sys.platform != 'win32':
        print("ERROR: Not supported on non-Windows platforms")
        return False

    # 1. キャッシュからデータを読み込む
    # debug_log("focus_wezterm: Step 1 - get_cache_data()")
    cache_data = get_cache_data()
    target_dir = cache_data.project_dir
    cached_hwnd = cache_data.hwnd
    cached_pane_id = cache_data.pane_id
    cached_socket = cache_data.wezterm_socket
    # debug_log(f"focus_wezterm: target_dir={target_dir}, cached_hwnd={cached_hwnd}, cached_pane_id={cached_pane_id}, cached_socket={cached_socket}")

    # 2. キャッシュされたhwndが有効なら、それを直接使用（最優先）
    if cached_hwnd is not None:
        # debug_log(f"focus_wezterm: Step 1a - checking cached hwnd validity")
        if is_hwnd_valid(cached_hwnd):
            # debug_log(f"focus_wezterm: cached hwnd={cached_hwnd} is valid")

            # 2a. pane_idとソケットがあれば、まずタブをアクティブにする
            if cached_pane_id is not None and cached_socket is not None:
                # debug_log(f"focus_wezterm: Step 1b - activating pane_id={cached_pane_id} with socket={cached_socket}")
                try:
                    import subprocess
                    import tempfile
                    import os

                    # キャッシュされたソケットを環境変数にセット
                    env = os.environ.copy()
                    env["WEZTERM_UNIX_SOCKET"] = cached_socket
                    # debug_log(f"focus_wezterm: set WEZTERM_UNIX_SOCKET={cached_socket}")

                    # 一時ファイルを作成（PIPEの代わり）
                    stdout_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stdout.txt')
                    stderr_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_stderr.txt')
                    stdout_path = stdout_file.name
                    stderr_path = stderr_file.name
                    stdout_file.close()
                    stderr_file.close()

                    with open(stdout_path, 'w') as out_f, open(stderr_path, 'w') as err_f:
                        proc = subprocess.Popen(
                            ["wezterm", "cli", "activate-pane", "--pane-id", str(cached_pane_id)],
                            stdout=out_f,
                            stderr=err_f,
                            env=env,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        # 最大3秒待つ
                        try:
                            proc.wait(timeout=3)
                            # debug_log(f"focus_wezterm: pane activation returncode={proc.returncode}")
                        except subprocess.TimeoutExpired:
                            debug_log(f"focus_wezterm: pane activation timed out, killing")
                            proc.kill()

                    # 一時ファイルを削除
                    try:
                        os.unlink(stdout_path)
                        os.unlink(stderr_path)
                    except Exception:
                        pass
                except Exception as e:
                    debug_log(f"focus_wezterm: pane activation error: {e}")

            # 2b. ウィンドウをフォーカス
            return focus_hwnd(cached_hwnd)
        else:
            debug_log(f"focus_wezterm: cached hwnd={cached_hwnd} is invalid, falling back")

    # 3. キャッシュされたhwndが無効な場合、従来のロジックにフォールバック
    target_window_id = None
    target_window_title = None
    if target_dir:
        debug_log("focus_wezterm: Step 2 - find_and_activate_tab()")
        tab_activated, target_window_id = find_and_activate_tab(target_dir)
        debug_log(f"focus_wezterm: tab_activated={tab_activated}, window_id={target_window_id}")
        if tab_activated and target_window_id is not None:
            # アクティブにした後、そのwindow_idのタイトルを取得
            debug_log("focus_wezterm: Step 3 - get_window_title_for_window_id()")
            target_window_title = get_window_title_for_window_id(target_window_id)
            debug_log(f"focus_wezterm: target_window_title obtained")
        elif not tab_activated:
            print("ERROR: Tab switch failed, continuing with window focus")
    else:
        print("ERROR: project_dir cache not found")

    # 2. ウィンドウをフォーカスする
    debug_log("focus_wezterm: Step 4 - importing win32gui")
    try:
        import win32gui
        import win32com.client
        debug_log("focus_wezterm: win32gui imported")
    except ImportError:
        print("ERROR: pywin32 not installed: pip install pywin32")
        return False

    # Weztermのウィンドウクラス名
    WEZTERM_CLASS = "org.wezfurlong.wezterm"

    def enum_handler(hwnd, results):
        """ウィンドウを列挙するコールバック"""
        if win32gui.IsWindowVisible(hwnd):
            classname = win32gui.GetClassName(hwnd)
            if classname == WEZTERM_CLASS:
                title = win32gui.GetWindowText(hwnd)
                results.append((hwnd, title))

    debug_log("focus_wezterm: Step 5 - EnumWindows()")
    windows = []
    win32gui.EnumWindows(enum_handler, windows)
    debug_log(f"focus_wezterm: found {len(windows)} wezterm windows")
    # 全ウィンドウの詳細をログ出力（マーカー検出も確認）
    CLAUDE_TITLE_MARKERS = ['⠂', '✳', '⠈', '⠐', '⠠', '⠄', '⠁']
    # マーカーのコードポイントをログ出力（デバッグ用）
    marker_codepoints = [f"{m}=U+{ord(m):04X}" for m in CLAUDE_TITLE_MARKERS]
    debug_log(f"focus_wezterm: Step 5 - markers: {marker_codepoints}")
    for i, (w_hwnd, w_title) in enumerate(windows):
        safe_title = w_title.encode('ascii', 'replace').decode('ascii')
        has_marker = any(marker in w_title for marker in CLAUDE_TITLE_MARKERS)
        # タイトルのバイト表現も出力（マーカー文字の確認用）
        title_repr = repr(w_title[:30])
        # タイトル先頭10文字のコードポイントを出力（マーカー検出問題の調査用）
        title_codepoints = [f"U+{ord(c):04X}" for c in w_title[:10]]
        debug_log(f"focus_wezterm: Step 5 - window[{i}]: hwnd={w_hwnd}, has_marker={has_marker}, title={title_repr}")
        debug_log(f"focus_wezterm: Step 5 - window[{i}]: codepoints={title_codepoints}")

    if not windows:
        print("ERROR: Wezterm window not found")
        return False

    # 対象のウィンドウを選択
    # target_window_titleが取得できていれば、それにマッチするウィンドウを優先
    # Win32のタイトルは "[1/4] タイトル" のようにタブ番号が付くため、部分一致で検索
    hwnd = None
    if target_window_title:
        for w_hwnd, w_title in windows:
            # 部分一致: wezterm cli listのタイトルがWin32タイトルに含まれているか
            if target_window_title in w_title:
                hwnd = w_hwnd
                # 正常動作時のログはコメントアウト
                # cp932でエンコードできない文字があるため、ASCII安全な出力にする
                # safe_w_title = w_title.encode('ascii', 'replace').decode('ascii')
                # print(f"Found matching window by title: hwnd={hwnd}, title='{safe_w_title}'")
                break

    # wezterm cli listが失敗した場合のフォールバック:
    # Claude Codeのマーカー（⠂ ✳ など）がタイトルに含まれるウィンドウを優先
    if hwnd is None:
        CLAUDE_TITLE_MARKERS = ['⠂', '✳', '⠈', '⠐', '⠠', '⠄', '⠁']
        for w_hwnd, w_title in windows:
            if any(marker in w_title for marker in CLAUDE_TITLE_MARKERS):
                hwnd = w_hwnd
                # 正常動作時のログはコメントアウト
                # cp932でエンコードできない文字があるため、ASCII安全な出力にする
                # safe_title = w_title.encode('ascii', 'replace').decode('ascii')
                # print(f"Found Claude Code window by marker: hwnd={hwnd}, title='{safe_title}'")
                break

    # それでも見つからなければ最初のウィンドウを使用（フォールバック情報として出力）
    if hwnd is None:
        hwnd = windows[0][0]
        print(f"WARNING: No match found, using first window: hwnd={hwnd}")

    debug_log(f"focus_wezterm: Step 6 - focusing hwnd={hwnd}")
    try:
        import win32con
        import win32process
        import ctypes
        import time

        debug_log("focus_wezterm: Step 6a - GetForegroundWindow()")
        # フォーカス前の状態をログ
        before_hwnd = win32gui.GetForegroundWindow()
        before_title = win32gui.GetWindowText(before_hwnd)
        before_class = win32gui.GetClassName(before_hwnd)
        # プロセス情報も取得
        _, before_pid = win32process.GetWindowThreadProcessId(before_hwnd)
        debug_log(f"focus_wezterm: Step 6a - before_hwnd={before_hwnd}, before_class='{before_class}', before_pid={before_pid}")
        debug_log(f"focus_wezterm: Step 6a - before_title={repr(before_title[:50])}")

        debug_log("focus_wezterm: Step 6b - checking IsIconic")
        # ウィンドウが最小化されている場合は復元
        if win32gui.IsIconic(hwnd):
            debug_log("focus_wezterm: Step 6b - ShowWindow (restore)")
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        debug_log("focus_wezterm: Step 6c - AttachThreadInput")
        # AttachThreadInput 方式（keybd_event なし）
        foreground_hwnd = win32gui.GetForegroundWindow()
        foreground_thread_id, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
        target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
        debug_log(f"focus_wezterm: Step 6c - foreground_hwnd={foreground_hwnd}, foreground_thread_id={foreground_thread_id}, target_thread_id={target_thread_id}")

        attach_result = ctypes.windll.user32.AttachThreadInput(foreground_thread_id, target_thread_id, True)
        debug_log(f"focus_wezterm: Step 6c - AttachThreadInput result={attach_result}, GetLastError={ctypes.get_last_error()}")

        try:
            debug_log("focus_wezterm: Step 6d - BringWindowToTop")
            try:
                win32gui.BringWindowToTop(hwnd)
                debug_log("focus_wezterm: Step 6d - BringWindowToTop succeeded")
            except Exception as e:
                debug_log(f"focus_wezterm: Step 6d - BringWindowToTop failed: {e}")

            debug_log("focus_wezterm: Step 6d - SetForegroundWindow")
            try:
                ctypes.windll.kernel32.SetLastError(0)
                sfw_result = ctypes.windll.user32.SetForegroundWindow(hwnd)
                sfw_error = ctypes.get_last_error()
                debug_log(f"focus_wezterm: Step 6d - SetForegroundWindow result={sfw_result}, GetLastError={sfw_error}")
                if sfw_result == 0:
                    debug_log(f"focus_wezterm: Step 6d - SetForegroundWindow FAILED (result=0)")
            except Exception as e:
                debug_log(f"focus_wezterm: Step 6d - SetForegroundWindow exception: {e}")
                raise
        finally:
            detach_result = ctypes.windll.user32.AttachThreadInput(foreground_thread_id, target_thread_id, False)
            debug_log(f"focus_wezterm: Step 6c - DetachThreadInput result={detach_result}")

        debug_log("focus_wezterm: Step 6e - verifying focus")
        # フォーカス直後の状態をログ
        after_hwnd = win32gui.GetForegroundWindow()
        after_title = win32gui.GetWindowText(after_hwnd)
        after_class = win32gui.GetClassName(after_hwnd)
        debug_log(f"focus_wezterm: Step 6e - after_hwnd={after_hwnd}, after_class='{after_class}', target_hwnd={hwnd}, success={after_hwnd == hwnd}")
        debug_log(f"focus_wezterm: Step 6e - after_title={repr(after_title[:50])}")

        debug_log("focus_wezterm: Step 6f - sleeping 0.5s")
        # 少し待って再確認（何がフォーカスを奪うか調査）
        time.sleep(0.5)
        later_hwnd = win32gui.GetForegroundWindow()
        later_title = win32gui.GetWindowText(later_hwnd)
        later_class = win32gui.GetClassName(later_hwnd)
        debug_log(f"focus_wezterm: Step 6f - later_hwnd={later_hwnd}, later_class='{later_class}', success={later_hwnd == hwnd}")
        debug_log(f"focus_wezterm: Step 6f - later_title={repr(later_title[:50])}")

        debug_log("focus_wezterm: finished successfully")
        return True
    except Exception as e:
        debug_log(f"focus_wezterm: ERROR - {e}")
        print(f"ERROR: Failed to set focus: {e}")
        return False


if __name__ == "__main__":
    debug_log("=== focus_wezterm.py started ===")
    debug_log(f"Python: {sys.executable}")
    debug_log(f"CWD: {Path.cwd()}")
    try:
        success = focus_wezterm()
        debug_log(f"=== focus_wezterm.py finished (success={success}) ===")
        sys.exit(0 if success else 1)
    except Exception as e:
        debug_log(f"=== FATAL ERROR: {e} ===")
        import traceback
        traceback.print_exc()
        sys.exit(1)
