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

# 通知クリック時に参照するproject_dirの一時ファイル
# __file__ = .claude/hooks/scripts/fundamental/notification/focus_wezterm.py
# .parent = notification/
# .parent.parent = fundamental/
# .parent.parent.parent = scripts/
# .parent.parent.parent.parent = hooks/
PROJECT_DIR_CACHE = Path(__file__).parent.parent.parent.parent / "cache" / "notification_project_dir.txt"


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
    一時ファイルからターゲットのproject_dirを読み込む

    Returns:
        project_dirのパス、またはNone
    """
    if not PROJECT_DIR_CACHE.exists():
        return None
    try:
        return PROJECT_DIR_CACHE.read_text(encoding="utf-8").strip()
    except Exception:
        return None


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
        # wezterm cli list --format json でタブ一覧を取得
        result = subprocess.run(
            ["wezterm", "cli", "list", "--format", "json"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            print(f"ERROR: wezterm cli list failed: {result.stderr.decode('utf-8', errors='replace')}")
            return False, None

        # UTF-8でデコード（日本語タイトルがあるため）
        tabs = json.loads(result.stdout.decode('utf-8'))
        target_normalized = Path(target_dir).resolve().as_posix().lower()

        # CWDがマッチするタブを収集
        matching_tabs = []
        for tab in tabs:
            cwd = tab.get("cwd", "")
            tab_cwd_normalized = normalize_wezterm_cwd(cwd).lower()

            if tab_cwd_normalized == target_normalized:
                matching_tabs.append(tab)

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

        if tab_id is not None:
            # タブをアクティブにする
            activate_result = subprocess.run(
                ["wezterm", "cli", "activate-tab", "--tab-id", str(tab_id)],
                capture_output=True,
                timeout=5
            )
            if activate_result.returncode == 0:
                # print(f"Activated tab {tab_id} (window {window_id}) for {target_dir}")
                return True, window_id
            else:
                print(f"ERROR: Failed to activate tab {tab_id}")

        return False, None

    except subprocess.TimeoutExpired:
        print("ERROR: wezterm cli timed out")
        return False, None
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse wezterm cli output: {e}")
        return False, None
    except FileNotFoundError:
        print("ERROR: wezterm command not found")
        return False, None
    except Exception as e:
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


def focus_wezterm() -> bool:
    """
    Weztermウィンドウを前面にフォーカスする

    処理順序:
    1. 一時ファイルからproject_dirを読み込む
    2. wezterm cli で対象タブをアクティブにする
    3. 対象のwindow_idに対応するウィンドウを前面にフォーカスする

    Returns:
        bool: 成功時True、失敗時False
    """
    if sys.platform != 'win32':
        print("ERROR: Not supported on non-Windows platforms")
        return False

    # 1. 対象タブをアクティブにする（タブ切り替え）
    target_dir = get_target_project_dir()
    target_window_id = None
    target_window_title = None
    if target_dir:
        tab_activated, target_window_id = find_and_activate_tab(target_dir)
        if tab_activated and target_window_id is not None:
            # アクティブにした後、そのwindow_idのタイトルを取得
            target_window_title = get_window_title_for_window_id(target_window_id)
            # 正常動作時のログはコメントアウト
            # safe_title = target_window_title.encode('ascii', 'replace').decode('ascii') if target_window_title else ''
            # print(f"Target window_id={target_window_id}, title='{safe_title}'")
        elif not tab_activated:
            print("ERROR: Tab switch failed, continuing with window focus")
    else:
        print("ERROR: project_dir cache not found")

    # 2. ウィンドウをフォーカスする
    try:
        import win32gui
        import win32com.client
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

    windows = []
    win32gui.EnumWindows(enum_handler, windows)

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

    try:
        import win32con
        import win32process
        import ctypes
        import time

        # フォーカス前の状態をログ
        before_hwnd = win32gui.GetForegroundWindow()
        before_title = win32gui.GetWindowText(before_hwnd)
        before_class = win32gui.GetClassName(before_hwnd)
        print(f"DEBUG: Before focus - hwnd={before_hwnd}, class='{before_class}', title='{before_title[:50]}'")

        # ウィンドウが最小化されている場合は復元
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # AttachThreadInput 方式（keybd_event なし）
        foreground_hwnd = win32gui.GetForegroundWindow()
        foreground_thread_id, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
        target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)

        ctypes.windll.user32.AttachThreadInput(foreground_thread_id, target_thread_id, True)

        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            ctypes.windll.user32.AttachThreadInput(foreground_thread_id, target_thread_id, False)

        # フォーカス直後の状態をログ
        after_hwnd = win32gui.GetForegroundWindow()
        after_title = win32gui.GetWindowText(after_hwnd)
        after_class = win32gui.GetClassName(after_hwnd)
        print(f"DEBUG: After focus - hwnd={after_hwnd}, class='{after_class}', title='{after_title[:50]}'")
        print(f"DEBUG: Target was hwnd={hwnd}, success={after_hwnd == hwnd}")

        # 少し待って再確認（何がフォーカスを奪うか調査）
        time.sleep(0.5)
        later_hwnd = win32gui.GetForegroundWindow()
        later_title = win32gui.GetWindowText(later_hwnd)
        later_class = win32gui.GetClassName(later_hwnd)
        print(f"DEBUG: After 0.5s - hwnd={later_hwnd}, class='{later_class}', title='{later_title[:50]}'")

        return True
    except Exception as e:
        print(f"ERROR: Failed to set focus: {e}")
        return False


if __name__ == "__main__":
    success = focus_wezterm()
    sys.exit(0 if success else 1)
