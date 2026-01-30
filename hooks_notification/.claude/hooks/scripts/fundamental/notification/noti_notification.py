#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
noti_notification.py
windows-toastsベースの通知hookスクリプト（ユーザー入力待ち時に発火）
通知クリックでWeztermウィンドウを前面にフォーカスする機能付き
"""
import sys
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

        # クリック時用にproject_dirフルパスを一時ファイルに書き込む
        project_dir_cache = get_path_from_config("notification_project_dir_cache")
        try:
            project_dir_cache.parent.mkdir(parents=True, exist_ok=True)
            project_dir_cache.write_text(str(project_dir_path), encoding="utf-8")
            debug_log(f"noti_notification: saved project_dir to cache: {project_dir_path}")
        except Exception as e:
            debug_log(f"noti_notification: failed to save project_dir: {e}")

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
