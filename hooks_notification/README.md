# hooks_notification

Claude hooks の通知周りを記事用に抜き出したディレクトリです。

プライバシーの観点から、パス情報を含むキャッシュは削除しています。

## Structure

- .claude/
  - hooks/
    - jsons/
      - hook_path_config.json5
    - scripts/
      - fundamental/
        - hook_utils.py
        - notification_package.py
        - notification/
          - __init__.py
          - noti_notification.py
          - focus_wezterm.vbs
          - focus_wezterm_inner.bat
          - focus_wezterm.py

