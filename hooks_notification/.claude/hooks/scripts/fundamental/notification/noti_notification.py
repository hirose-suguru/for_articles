#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
noti_notification.py
windows-toastsベースの通知hookスクリプト（ユーザー入力待ち時に発火）
通知クリックでWeztermウィンドウを前面にフォーカスする機能付き
"""
import sys
import json
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from hook_utils import log_hook_execution, debug_log, notify_user, get_hook_toggle, log_hook_error, get_project_root, get_path_from_config

except ImportError as e:
    error_msg = f"Failed to import hook_utils: {e}"
    print(f"[HOOK ERROR] {error_msg}")
    print(f"[HOOK ERROR] Script: {__file__}")
    print(f"[HOOK ERROR] sys.path: {sys.path}")
    sys.stderr.write(f"[HOOK ERROR] {error_msg}\n")
    sys.stderr.write(f"[HOOK ERROR] Script: {__file__}\n")
    sys.exit(1)


# focus_wezterm.vbsのパス（.vbsはwscript.exeで実行され、コンソールウィンドウが表示されない）
FOCUS_SCRIPT = Path(__file__).parent / "focus_wezterm.vbs"


def main():
    """入力待ち時の通知を送信"""
    try:
        log_hook_execution()
        debug_log("started.")

        # トグル設定をチェック（デフォルトは有効）
        if not get_hook_toggle("notification"):
            debug_log("noti_notification: Notification disabled by toggle")
            debug_log("finished.")
            return

        # プロジェクトディレクトリを取得（hook_utilsのget_project_root()を使用）
        project_dir_path = get_project_root()
        project_dir_name = project_dir_path.name

        # クリック時用にproject_dirとhwndを一時ファイルに書き込む
        project_dir_cache = get_path_from_config("notification_wezterm_cache")
        try:
            project_dir_cache.parent.mkdir(parents=True, exist_ok=True)

            # Claude Codeが動作しているWeztermウィンドウのhwndを取得
            hwnd = None
            window_id = None  # wezterm cli list用
            pane_id = None    # タブ切り替え用
            if sys.platform == 'win32':
                try:
                    import subprocess
                    import win32gui

                    WEZTERM_CLASS = "org.wezfurlong.wezterm"

                    # 1. WEZTERM_PANE環境変数からpane_idを取得し、window_idを特定
                    # (CWDマッチングより確実)
                    import os as os_module
                    import json as json_module
                    tabs = []
                    try:
                        result = subprocess.run(
                            ["wezterm", "cli", "list", "--format", "json"],
                            capture_output=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            tabs = json_module.loads(result.stdout.decode('utf-8'))
                            # debug_log(f"noti_notification: wezterm cli found {len(tabs)} tabs")

                            # WEZTERM_PANE環境変数からpane_idを取得
                            pane_id_str = os_module.environ.get("WEZTERM_PANE")
                            if pane_id_str:
                                pane_id = int(pane_id_str)  # 外側のスコープの変数を更新
                                for tab in tabs:
                                    if tab.get("pane_id") == pane_id:
                                        window_id = tab.get("window_id")
                                        # debug_log(f"noti_notification: WEZTERM_PANE={pane_id} -> window_id={window_id}")
                                        break
                            # else:
                            #     debug_log("noti_notification: WEZTERM_PANE not set, skipping")
                        else:
                            debug_log(f"noti_notification: wezterm cli failed: {result.stderr.decode()[:100]}")
                    except Exception as e:
                        debug_log(f"noti_notification: wezterm cli error: {e}")

                    # 2. window_idが取得できたら、そのwindow_idに対応するhwndを探す
                    # タブ数マッチング方式: wezterm cli listの各window_idのタブ数と
                    # Win32ウィンドウタイトルの[N/M]からタブ数を比較してマッチング

                    # 2a. 各window_idのタブ数を集計（nvim系タブは除外）
                    # ty.exe, ruff.exe などはnvimなので除外
                    NVIM_TITLES = {'ty.exe', 'ruff.exe', 'nvim', 'vim'}
                    tab_counts = {}  # window_id -> tab_count
                    for tab in tabs if 'tabs' in dir() else []:
                        wid = tab.get("window_id")
                        title = tab.get("title", "").lower()
                        # nvim系タブのみのウィンドウは除外対象
                        if any(nvim_title in title for nvim_title in NVIM_TITLES):
                            continue
                        tab_counts[wid] = tab_counts.get(wid, 0) + 1

                    # debug_log(f"noti_notification: tab_counts (excluding nvim): {tab_counts}")

                    # 2b. Win32でWeztermウィンドウを列挙し、タイトルからタブ数を抽出
                    import re
                    wezterm_windows = []
                    def enum_handler(h, results):
                        if win32gui.IsWindowVisible(h):
                            classname = win32gui.GetClassName(h)
                            if classname == WEZTERM_CLASS:
                                title = win32gui.GetWindowText(h)
                                # [N/M] 形式からタブ総数Mを抽出
                                match = re.search(r'\[(\d+)/(\d+)\]', title)
                                total_tabs = int(match.group(2)) if match else None
                                results.append((h, title, total_tabs))
                    win32gui.EnumWindows(enum_handler, wezterm_windows)
                    # debug_log(f"noti_notification: found {len(wezterm_windows)} wezterm windows")

                    # 各ウィンドウの詳細をログ出力
                    # for i, (h, title, total_tabs) in enumerate(wezterm_windows):
                    #     debug_log(f"noti_notification: window[{i}]: hwnd={h}, tabs={total_tabs}, title={repr(title[:50])}")

                    # 2c. タブ数でマッチング
                    if window_id is not None and window_id in tab_counts:
                        target_tab_count = tab_counts[window_id]
                        # debug_log(f"noti_notification: target window_id={window_id}, tab_count={target_tab_count}")

                        # タブ数が一致するhwndを探す
                        matched_hwnds = [(h, title) for h, title, total_tabs in wezterm_windows
                                        if total_tabs == target_tab_count]

                        if len(matched_hwnds) == 1:
                            hwnd = matched_hwnds[0][0]
                            # debug_log(f"noti_notification: matched by tab count: hwnd={hwnd}")
                        elif len(matched_hwnds) > 1:
                            # 複数マッチした場合は最初のものを使用
                            hwnd = matched_hwnds[0][0]
                            debug_log(f"noti_notification: multiple matches ({len(matched_hwnds)}), using first hwnd={hwnd}")
                        else:
                            debug_log(f"noti_notification: no match by tab count")

                    # フォールバック: マッチしなかった場合
                    if hwnd is None and len(wezterm_windows) == 1:
                        hwnd = wezterm_windows[0][0]
                        # debug_log(f"noti_notification: fallback to single window: hwnd={hwnd}")
                    elif hwnd is None and len(wezterm_windows) > 0:
                        # nvim系タイトルを除外して最初のものを使用
                        for h, title, _ in wezterm_windows:
                            if not any(nvim_title in title.lower() for nvim_title in NVIM_TITLES):
                                hwnd = h
                                debug_log(f"noti_notification: fallback (excluding nvim): hwnd={hwnd}")
                                break
                        if hwnd is None:
                            hwnd = wezterm_windows[0][0]
                            debug_log(f"noti_notification: fallback to first window: hwnd={hwnd}")
                except ImportError:
                    debug_log("noti_notification: pywin32 not available, skipping hwnd capture")
                except Exception as e:
                    debug_log(f"noti_notification: failed to get hwnd: {e}")

            # JSON形式で保存（project_dir + hwnd + window_id + pane_id + socket）
            cache_data = {
                "project_dir": str(project_dir_path),
                "hwnd": hwnd,
                "window_id": window_id,
                "pane_id": pane_id,
                "wezterm_socket": os_module.environ.get("WEZTERM_UNIX_SOCKET")
            }
            project_dir_cache.write_text(json.dumps(cache_data, ensure_ascii=False), encoding="utf-8")
            # debug_log(f"noti_notification: saved cache: {cache_data}")
        except Exception as e:
            debug_log(f"noti_notification: failed to save cache: {e}")

        # クリック時実行スクリプトのパス
        on_click_script = str(FOCUS_SCRIPT) if FOCUS_SCRIPT.exists() else None

        # 通知を送信
        result = notify_user(
            title=f"Claude Code - {project_dir_name}",
            message="入力をお待ちしています",
            speak=True,
            speak_text="入力をお待ちしています",
            on_click_script=on_click_script
        )

        debug_log(f"noti_notification: toast={result['toast']}, tts={result['tts']}")
        debug_log("finished.")

    except Exception as e:
        error_msg = f"Unexpected error in main(): {e}"
        log_hook_error(error_msg)
        debug_log(error_msg)
        raise


if __name__ == "__main__":
    main()
