#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notification_package.py
Notification hookで実行される全スクリプトを統合実行
（ユーザー入力待ち時に発火）
"""
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from hook_utils import log_hook_execution, debug_log, log_hook_error

except ImportError as e:
    error_msg = f"Failed to import hook_utils: {e}"
    print(f"[HOOK ERROR] {error_msg}")
    print(f"[HOOK ERROR] Script: {__file__}")
    print(f"[HOOK ERROR] sys.path: {sys.path}")
    sys.stderr.write(f"[HOOK ERROR] {error_msg}\n")
    sys.stderr.write(f"[HOOK ERROR] Script: {__file__}\n")
    sys.exit(1)

def main():
    """Notificationの全処理を順次実行"""
    import json
    try:
        log_hook_execution()
        debug_log("started.")

        # stdinからデータを取得
        hook_data = {}
        try:
            input_bytes = sys.stdin.buffer.read()
            try:
                input_data = input_bytes.decode('cp932')
            except UnicodeDecodeError:
                input_data = input_bytes.decode('utf-8', errors='replace')

            if input_data.strip():
                hook_data = json.loads(input_data)
                debug_log(f"notification_type: {hook_data.get('notification_type', 'unknown')}")
        except Exception as e:
            debug_log(f"notification stdin error: {e}")

        # idle_promptはStopフックで処理済みなのでスキップ
        notification_type = hook_data.get("notification_type", "")
        if notification_type == "idle_prompt":
            debug_log("idle_prompt: skipped (handled by Stop hook)")
            debug_log("finished.")
            return

        # noti_notificationを実行（launch_action + .bat方式）
        sys.path.insert(0, str(Path(__file__).parent))
        from notification import noti_notification
        noti_notification.main()

        debug_log("finished.")

    except Exception as e:
        error_msg = f"Unexpected error in main(): {e}"
        log_hook_error(error_msg)
        debug_log(error_msg)
        raise

if __name__ == "__main__":
    main()
