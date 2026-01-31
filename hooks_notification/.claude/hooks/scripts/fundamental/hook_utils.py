#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hook_utils.py
hookスクリプト用の共通ユーティリティ関数
"""
import sys
import json
import io
import inspect
import re
from datetime import datetime
from pathlib import Path

# hook_path_config.json5を読み込み（モジュールレベルで1回だけ）
# __file__の絶対パスから.claude/hooks/jsons/を見つける
_hooks_dir = Path(__file__).resolve()
while _hooks_dir.name != "hooks" and _hooks_dir.parent != _hooks_dir:
    _hooks_dir = _hooks_dir.parent
if _hooks_dir.name != "hooks":
    raise RuntimeError("Could not find 'hooks' directory in path")
_config_path = _hooks_dir / "jsons" / "hook_path_config.json5"

# JSON5パース用の簡易関数（parse_json5が定義される前に使用）
def _parse_json5_early(json5_text: str) -> str:
    """モジュールレベルで使用するJSON5パース（簡易版）"""
    result = re.sub(r'/\*[\s\S]*?\*/', '', json5_text)
    lines = result.split('\n')
    cleaned_lines = []
    for line in lines:
        quote_count = 0
        comment_pos = -1
        for i, char in enumerate(line):
            if char == '"':
                quote_count += 1
            elif char == '/' and i + 1 < len(line):
                if line[i + 1] == '/' and quote_count % 2 == 0:
                    comment_pos = i
                    break
        cleaned_lines.append(line[:comment_pos] if comment_pos >= 0 else line)
    result = '\n'.join(cleaned_lines)
    result = re.sub(r',\s*}', '}', result)
    result = re.sub(r',\s*]', ']', result)
    return result

with open(_config_path, 'r', encoding='utf-8') as f:
    json5_text = f.read()
_config = json.loads(_parse_json5_early(json5_text))

# プロジェクトルートを取得（後で定義される get_project_root() を使用）
def _get_project_root_early() -> Path:
    """早期にプロジェクトルートを取得（モジュールレベルで使用）"""
    hooks_dir = Path(__file__).resolve()
    while hooks_dir.name != "hooks" and hooks_dir.parent != hooks_dir:
        hooks_dir = hooks_dir.parent
    if hooks_dir.name != "hooks":
        raise RuntimeError("Could not find 'hooks' directory in path")
    return hooks_dir.parent.parent

_project_root = _get_project_root_early()
_log_file = _project_root / _config["log_file"]
_debug_file = _project_root / _config["debug_file"]

# Windows環境でのみUTF-8入出力を自動設定
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')

# hook_toggle_config.json5のパス
_toggle_config_path = _hooks_dir / "jsons" / "hook_toggle_config.json5"

def get_hook_path_config_path() -> Path:
    """
    hook_path_config.json5のパスを取得する

    Returns:
        hook_path_config.json5の絶対パス（Pathオブジェクト）

    Example:
        >>> config_path = get_hook_path_config_path()
        >>> print(config_path)
        C:/Users/username/Documents/ProjectName/.claude/hooks/jsons/hook_path_config.json5
    """
    return _config_path

def get_path_from_config(key: str) -> Path:
    """
    hook_path_config.json5から指定されたキーのパスを取得する

    Args:
        key: 設定キー（"log_file", "debug_file", "timestamps_file"等）

    Returns:
        プロジェクトルートからの絶対パス（Pathオブジェクト）

    Raises:
        KeyError: 指定されたキーが設定ファイルに存在しない場合
    """
    if key not in _config:
        raise KeyError(f"'{key}' は設定ファイルに存在しません")

    # 相対パスを取得
    relative_path = Path(_config[key])

    # プロジェクトルートと結合して絶対パスを返す
    project_root = get_project_root()
    return project_root / relative_path

def get_project_root() -> Path:
    """
    プロジェクトルートディレクトリを取得する

    hooks/ディレクトリから3階層上（.claude/hooks/ → .claude/ → プロジェクトルート）

    Returns:
        プロジェクトルートのPathオブジェクト

    Example:
        hooks/ が C:/Users/username/Documents/ProjectName/.claude/hooks/ の場合
        → C:/Users/username/Documents/ProjectName/ を返す
    """
    # hooks/ → .claude/ → ProjectRoot/
    return _hooks_dir.parent.parent

def get_relative_path(path: Path) -> Path:
    """
    プロジェクトルートからの相対パスを取得

    Args:
        path: 絶対パス（PathオブジェクトまたはPath文字列）

    Returns:
        プロジェクトルートからの相対パス

    Example:
        >>> abs_path = Path("C:/Users/username/Documents/ProjectName/.claude/hooks/logs/debug.log")
        >>> get_relative_path(abs_path)
        Path(".claude/hooks/logs/debug.log")
    """
    project_root = get_project_root()
    abs_path = Path(path).resolve()
    return abs_path.relative_to(project_root)

def get_obsidian_config() -> dict:
    """
    hook_path_config.json5からObsidian設定を取得

    Returns:
        Obsidian設定の辞書
    """
    return _config.get("obsidian", {})

def get_obsidian_path(path_key: str) -> Path:
    """
    Obsidian vault内のパスを取得

    Args:
        path_key: パスのキー ("progress", "index", "features"等)

    Returns:
        プロジェクトルートからの絶対パス

    Raises:
        KeyError: 指定されたキーがObsidian設定に存在しない場合
    """
    obs_config = get_obsidian_config()

    if not obs_config:
        raise KeyError("Obsidian設定が存在しません")

    base_dir = get_project_root()  # プロジェクトルートディレクトリ
    vault_path = base_dir / obs_config["vault_path"]

    if path_key in obs_config["paths"]:
        return vault_path / obs_config["paths"][path_key]
    else:
        raise KeyError(f"'{path_key}' はObsidian設定に存在しません")

def log_hook_execution():
    """
    hookスクリプトの実行を記録する
    呼び出し元のファイル名を自動取得
    """
    # 呼び出し元のファイル名を自動取得
    current_frame = inspect.currentframe()
    frame = current_frame.f_back if current_frame else None
    script_name = Path(frame.f_code.co_filename).name if frame else "unknown"

    # ログディレクトリが存在しない場合は作成
    _log_file.parent.mkdir(parents=True, exist_ok=True)

    # 現在の日時を取得（秒まで）
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ログメッセージを生成
    log_message = f"{script_name} hook was executed at {timestamp}\n"

    # ログファイルに追記
    with open(_log_file, 'a', encoding='utf-8') as f:
        f.write(log_message)

def log_hook_error(error_message: str, script_name: str | None = None):
    """
    hookスクリプトのエラーを記録する

    Args:
        error_message: エラーメッセージ
       script_name: スクリプト名（省略時は呼び出し元から自動取得）

    Note:
        stdoutにもprintで出力するため、Claude Codeに確実に見える
    """
    # スクリプト名が指定されていない場合は自動取得
    if script_name is None:
        current_frame = inspect.currentframe()
        frame = current_frame.f_back if current_frame else None
        script_name = Path(frame.f_code.co_filename).name if frame else "unknown"

    # エラーログファイルのパスを取得
    error_log_file = get_path_from_config("error_file")

    # ログディレクトリが存在しない場合は作成
    error_log_file.parent.mkdir(parents=True, exist_ok=True)

    # 現在の日時を取得（秒まで）
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ログメッセージを生成
    log_message = f"[{timestamp}] {script_name}: {error_message}\n"

    # stdoutに出力（Claude Codeに見えるようにする）
    print(f"[HOOK ERROR] {script_name}: {error_message}")

    # エラーログファイルに追記
    with open(error_log_file, 'a', encoding='utf-8') as f:
        f.write(log_message)

def debug_log(message: str, include_caller: bool = True):
    """
    デバッグログをhook_debug.logに記録する
    呼び出し元のファイル名を自動取得

    Args:
        message: デバッグメッセージ
        include_caller: Falseの場合、呼び出し元のファイル名を省略
    """
    # ログディレクトリが存在しない場合は作成
    _debug_file.parent.mkdir(parents=True, exist_ok=True)

    # 現在の日時を取得（秒まで）
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ログメッセージを生成
    if include_caller:
        # 呼び出し元のファイル名を自動取得
        current_frame = inspect.currentframe()
        frame = current_frame.f_back if current_frame else None
        script_name = Path(frame.f_code.co_filename).name if frame else "unknown"
        log_message = f"[{timestamp}] {script_name}: {message}\n"
    else:
        log_message = f"[{timestamp}] {message}\n"

    # ログファイルに追記
    with open(_debug_file, 'a', encoding='utf-8') as f:
        f.write(log_message)

def log_python_env():
    """
    現在のPython実行環境情報をデバッグログに記録する

    記録される情報:
    - Python実行パス (sys.executable)
    - Pythonバージョン (sys.version)
    - 仮想環境名 (VIRTUAL_ENV環境変数から取得)
    """
    import os

    python_path = sys.executable
    python_version = sys.version.split()[0]  # バージョン番号のみ取得

    # 仮想環境名を取得
    venv_path = os.environ.get('VIRTUAL_ENV', '')
    if venv_path:
        venv_name = Path(venv_path).name
    else:
        venv_name = 'None (system Python)'

    debug_log(f"Python env: {python_path}", include_caller=False)
    debug_log(f"Python version: {python_version}", include_caller=False)
    debug_log(f"Virtual env: {venv_name}", include_caller=False)

def parse_json5(json5_text: str) -> str:
    """
    JSON5形式のテキストを標準JSONに変換
    - 行コメント（//）を除去
    - ブロックコメント（/* */）を除去
    - 末尾カンマを除去

    Args:
        json5_text: JSON5形式のテキスト

    Returns:
        標準JSON形式のテキスト
    """
    # ブロックコメント（/* */）を除去
    result = re.sub(r'/\*[\s\S]*?\*/', '', json5_text)

    # 行コメント（//）を除去（文字列内は保護）
    lines = result.split('\n')
    cleaned_lines = []

    for line in lines:
        # 文字列リテラル内の // を保護するため、" の外側の // のみ削除
        quote_count = 0
        comment_pos = -1

        for i, char in enumerate(line):
            if char == '"':
                quote_count += 1
            elif char == '/' and i + 1 < len(line):
                # 次の文字も / なら、引用符の外側かチェック
                if line[i + 1] == '/' and quote_count % 2 == 0:
                    comment_pos = i
                    break

        # コメント位置が見つかったら、その前までを保持
        if comment_pos >= 0:
            cleaned_lines.append(line[:comment_pos])
        else:
            cleaned_lines.append(line)

    result = '\n'.join(cleaned_lines)

    # 末尾カンマを除去（JSON5 → JSON変換）
    # オブジェクトの末尾カンマ: ,} → }
    result = re.sub(r',\s*}', '}', result)
    # 配列の末尾カンマ: ,] → ]
    result = re.sub(r',\s*]', ']', result)

    return result

def load_json5(filepath: Path) -> dict:
    """
    JSON5ファイルを読み込んでdictを返す

    Args:
        filepath: JSON5ファイルのパス

    Returns:
        パースされたdict（ファイルが存在しない場合は空dict）
    """
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                json5_text = f.read()
            json_text = parse_json5(json5_text)
            return json.loads(json_text)
        else:
            return {}
    except (json.JSONDecodeError, IOError):
        return {}

def save_json5(filepath: Path, data: dict, indent: int = 2, ensure_ascii: bool = False):
    """
    dictをJSONファイルに保存

    Args:
        filepath: 保存先のファイルパス
        data: 保存するdict
        indent: インデント幅（デフォルト: 2）
        ensure_ascii: ASCII文字のみで出力するか（デフォルト: False）
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

def get_counter(counter_name: str, max_value: int = 2) -> int:
    """
    カウンターの現在値を取得する

    Args:
        counter_name: カウンター名（例: "read_claude_reminder"）
        max_value: カウンターの最大値（デフォルト: 2、つまり 0, 1, 2 の3段階）

    Returns:
        現在のカウンター値
    """
    counters_file = get_path_from_config("hook_counters_file")
    counters = load_json5(counters_file)
    return counters.get(counter_name, 0)

def increment_counter(counter_name: str, max_value: int = 2):
    """
    カウンターをインクリメントする（max_valueを超えたら0に戻る）

    Args:
        counter_name: カウンター名（例: "read_claude_reminder"）
        max_value: カウンターの最大値（デフォルト: 2、つまり 0, 1, 2 の3段階）
    """
    counters_file = get_path_from_config("hook_counters_file")
    counters = load_json5(counters_file)

    current = counters.get(counter_name, 0)
    counters[counter_name] = (current + 1) % (max_value + 1)

    save_json5(counters_file, counters)

def reset_counter(counter_name: str):
    """
    カウンターを0にリセットする

    Args:
        counter_name: カウンター名（例: "read_claude_reminder"）
    """
    counters_file = get_path_from_config("hook_counters_file")
    counters = load_json5(counters_file)

    counters[counter_name] = 0

    save_json5(counters_file, counters)

def get_user_message_from_stdin() -> str:
    """
    stdinからユーザーメッセージを取得（キャッシュ機能付き）

    動作:
    1. stdin読み取り成功 → キャッシュ保存
    2. stdin空 & キャッシュあり → キャッシュから読む（5秒以内のみ）
    3. stdin空 & キャッシュなし/古い → 空文字列

    Returns:
        ユーザーメッセージ（取得失敗時は空文字列）
    """
    cache_file = get_path_from_config("stdin_cache_file")

    try:
        input_data = sys.stdin.read()

        if input_data.strip():
            # stdin読み取り成功 → キャッシュに保存（上書き）
            cache = {
                "timestamp": datetime.now().timestamp(),
                "data": input_data
            }
            save_json5(cache_file, cache)
            # debug_log("stdin read successful, cache saved")

        elif cache_file.exists():
            # stdin空 → キャッシュから読む（タイムスタンプチェック）
            try:
                cache = load_json5(cache_file)

                age = datetime.now().timestamp() - cache["timestamp"]
                if age < 5:  # 5秒以内のみ有効
                    input_data = cache["data"]
                    # debug_log(f"stdin cache hit (age: {age:.2f}s)")
                else:
                    debug_log(f"stdin cache expired (age: {age:.2f}s), removed")
                    cache_file.unlink()
                    return ""
            except Exception as e:
                debug_log(f"stdin cache read error: {e}")
                if cache_file.exists():
                    cache_file.unlink()
                return ""
        else:
            debug_log("stdin empty (no cache)")
            return ""

        # JSON parse処理（Claude Codeからのstdinは標準JSON）
        hook_data = json.loads(input_data)
        user_message = hook_data.get("prompt", "")

        if not user_message:
            debug_log("prompt field is empty")

        return user_message

    except json.JSONDecodeError as e:
        debug_log(f"JSON parse error: {str(e)}")
        return ""
    except Exception as e:
        debug_log(f"unexpected error: {str(e)}")
        return ""

def detect_keywords(user_message: str, keywords: list) -> tuple:
    """
    キーワードを検出する

    Args:
        user_message: ユーザーのプロンプト
        keywords: 検出するキーワードのリスト

    Returns:
        (bool, list): (キーワードが検出されたか, 検出されたキーワードのリスト)
    """
    message_lower = user_message.lower()
    detected_keywords = []

    for keyword in keywords:
        if keyword.lower() in message_lower:
            detected_keywords.append(keyword)

    # デバッグログ
    if detected_keywords:
        debug_log(f"keyword was detected: {', '.join(detected_keywords)}")
        return (True, detected_keywords)
    else:
        debug_log("キーワード未検出")
        return (False, [])

def detect_trigger(message: str, trigger: str) -> bool:
    """
    トリガー文字列が独立した形で存在するかチェック

    パス内の\を誤検出しないよう、前後が空白、行頭、行末のいずれかであることを確認

    Args:
        message: 検索対象のメッセージ
        trigger: トリガー文字列（例: "\\obsidian", "\\serena_stop"）

    Returns:
        bool: トリガーが独立した形で存在する場合True

    Example:
        detect_trigger("\\obsidian を有効にして", "\\obsidian")  # True
        detect_trigger("C:\\obsidian\\file.txt", "\\obsidian")   # False
    """
    # \を正規表現用にエスケープ
    escaped = re.escape(trigger)
    # 前後が空白、行頭、行末のいずれかであることを確認
    pattern = rf'(?:^|\s){escaped}(?:\s|$)'
    found = bool(re.search(pattern, message))

    if found:
        # 呼び出し元のファイル名を取得して、メッセージに含める
        current_frame = inspect.currentframe()
        frame = current_frame.f_back if current_frame else None
        caller_name = Path(frame.f_code.co_filename).name if frame else "unknown"
        # include_caller=False で呼び出し元情報をメッセージ内に含める
        debug_log(f"{caller_name}: Trigger detected: '{trigger}'", include_caller=False)

    return found

def get_hook_toggle(hook_name: str) -> bool:
    """
    hook_toggle_config.json5から指定されたhookのトグル状態を取得

    Args:
        hook_name: hookの名前（例: "obsidian", "project"）

    Returns:
        bool: hookが有効化されている場合True、それ以外False
    """
    try:
        if not _toggle_config_path.exists():
            debug_log(f"Hook toggle config not found: {_toggle_config_path}")
            return False

        toggle_config = load_json5(_toggle_config_path)
        is_enabled = toggle_config.get(hook_name, False)
        return is_enabled

    except (json.JSONDecodeError, IOError) as e:
        debug_log(f"Hook toggle config read error: {e}")
        return False

def set_hook_toggle(hook_name: str, enabled: bool):
    """
    hook_toggle_config.json5の指定されたhookのトグル状態を設定

    Args:
        hook_name: hookの名前（例: "obsidian", "project"）
        enabled: 有効化する場合True、無効化する場合False
    """
    try:
        # 既存の設定を読み込み
        if _toggle_config_path.exists():
            toggle_config = load_json5(_toggle_config_path)
        else:
            toggle_config = {}

        # トグル状態を更新
        toggle_config[hook_name] = enabled

        # 保存
        save_json5(_toggle_config_path, toggle_config)

        debug_log(f"Hook toggle set: {hook_name} = {enabled}")

    except Exception as e:
        debug_log(f"Hook toggle config write error: {e}")

def clear_file(file_path: Path):
    """
    指定したファイルを空にする

    Args:
        file_path: 空にするファイルのパス（Pathオブジェクト）
    """
    try:
        # ファイルが存在する場合のみ空にする
        if file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as _:
                pass  # 空の状態で書き込み
    except PermissionError as e:
        # ファイルがロックされている場合はエラーログに記録
        log_hook_error(f"clear_file: PermissionError - {file_path.name} is locked: {e}")
    except Exception as e:
        # その他のエラーもログに記録（処理は続行）
        log_hook_error(f"clear_file: Failed to clear {file_path.name}: {e}")

def get_tool_data_from_stdin() -> dict:
    """
    PostToolUse hookでstdinからツール実行データを取得

    Returns:
        ツール実行データの辞書（取得失敗時は空の辞書）
    """
    try:
        # stdinをバイナリモードで読み込み
        input_bytes = sys.stdin.buffer.read()

        # まずCP932としてデコードを試みる
        try:
            input_data = input_bytes.decode('cp932')
        except UnicodeDecodeError:
            # CP932で失敗した場合はUTF-8としてデコード
            input_data = input_bytes.decode('utf-8', errors='replace')

        hook_data = json.loads(input_data)

        return hook_data

    except json.JSONDecodeError as e:
        debug_log(f"JSON解析エラー: {str(e)}")
        return {}
    except Exception as e:
        debug_log(f"予期しないエラー: {str(e)}")
        return {}

def parse_timestamp(line: str, format: str = '%Y-%m-%d %H:%M:%S') -> datetime | None:
    """
    タイムスタンプ文字列をdatetimeに変換

    Args:
        line: タイムスタンプ文字列
        format: タイムスタンプのフォーマット（デフォルト: '%Y-%m-%d %H:%M:%S'）

    Returns:
        datetimeオブジェクト（パース失敗時はNone）
    """
    try:
        return datetime.strptime(line.strip(), format)
    except ValueError:
        print(f"WARNING: タイムスタンプのパースに失敗: {line}")
        return None

def get_last_n_timestamps(log_path: Path, n: int = 2) -> list:
    """
    ログファイルから最後のN個のタイムスタンプを取得

    Args:
        log_path: ログファイルのパス
        n: 取得するタイムスタンプの数（デフォルト: 2）

    Returns:
        datetimeオブジェクトのリスト（取得失敗時はNoneのリスト）
    """
    if not log_path.exists():
        return [None] * n

    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if len(lines) < n:
        return [None] * n

    return [parse_timestamp(line) for line in lines[-n:]]

def check_new_files(directory: Path, start_time: datetime, end_time: datetime, pattern: str = '*.md') -> list:
    """
    指定期間に作成されたファイルをチェック

    Args:
        directory: 検索対象のディレクトリ
        start_time: 開始時刻
        end_time: 終了時刻
        pattern: ファイルパターン（デフォルト: '*.md'）

    Returns:
        新規ファイルの相対パスのリスト
    """
    if not directory.exists():
        return []

    new_files = []
    for file in directory.rglob(pattern):
        created = datetime.fromtimestamp(file.stat().st_ctime)
        if start_time <= created <= end_time:
            # directory.parent.parent は obsidian/02_context/sessions → obsidian/
            try:
                new_files.append(str(file.relative_to(directory.parent.parent)))
            except ValueError:
                # relative_to が失敗した場合は絶対パスを使用
                new_files.append(str(file))
    return new_files

def rotate_debug_log():
    """
    debug_logをマーカーベースでローテーション（2プロンプト分を保持）

    マーカーの仕組み:
    - PROMPT_MARKER_1: 前回のプロンプトの開始位置
    - PROMPT_MARKER_0: 今回のプロンプトの開始位置

    処理:
    1. MARKER_1より前を削除
    2. MARKER_0 → MARKER_1に置き換え
    3. 新しいMARKER_0を挿入
    """
    marker_0 = "=== PROMPT_MARKER_0 ==="
    marker_1 = "=== PROMPT_MARKER_1 ==="

    try:
        if not _debug_file.exists():
            # ファイルがない場合は新規作成してマーカー挿入
            with open(_debug_file, 'w', encoding='utf-8') as f:
                f.write(f"{marker_1}\n")
            debug_log("rotate_debug_log: Created new debug log file with MARKER_0")
            return

        with open(_debug_file, 'r', encoding='utf-8') as f:
            content = f.read()

        original_marker_1_count = content.count(marker_1)

        # 現在のMARKER_0をMARKER_1に置き換え（新しい → 古い）
        content = content.replace(marker_0, marker_1, 1)

        # MARKER_1が2つ以上ある場合、2つ目以降（古いログ）を削除
        marker_1_count = content.count(marker_1)
        deleted = False
        if marker_1_count >= 2:
            # 2つ目のMARKER_1の位置を探す
            first_marker = content.find(marker_1)
            second_marker = content.find(marker_1, first_marker + len(marker_1))
            if second_marker != -1:
                # 2つ目のMARKER_1より前を削除
                content = content[second_marker:]
                deleted = True

        # 新しいMARKER_0を最後に追加（前に改行）
        content = f"{content}\n{marker_0}\n"

        # 書き戻し
        with open(_debug_file, 'w', encoding='utf-8') as f:
            f.write(content)

        if deleted:
            debug_log("rotate_debug_log: Rotated (deleted old logs, kept 2 prompts)")
        else:
            debug_log(f"rotate_debug_log: Rotated (no deletion, MARKER_1 count: {original_marker_1_count})")

    except Exception as e:
        debug_log(f"rotate_debug_log: ERROR - {e}")

def sync_hook_utils_to_subdirs():
    """
    hook_utils.py を各サブディレクトリに同期

    scripts/hook_utils.py を以下にコピー:
    - fundamental/hook_utils.py
    - obsidian/hook_utils.py

    成功/失敗時にデバッグログを出力
    """
    import shutil

    # このファイル自身のパス（scripts/hook_utils.py）
    source = Path(__file__).resolve()

    # コピー先ディレクトリのリスト
    target_dirs = [
        source.parent / "fundamental",
        source.parent / "obsidian"
    ]

    for target_dir in target_dirs:
        try:
            dest = target_dir / "hook_utils.py"
            shutil.copy2(source, dest)
            # プロジェクトルートからの相対パスを取得
            source_rel = get_relative_path(source.parent)
            dest_rel = get_relative_path(target_dir)
            debug_log(f"hook_utils.py synced successfully: {source_rel} -> {dest_rel}")
        except Exception as e:
            debug_log(f"Failed to sync hook_utils.py to {target_dir.name}: {e}")

def print_tree(directory: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0, exclude_dirs: list | None = None):
    """
    ディレクトリツリーを表示（簡易版）

    Args:
        directory: 表示するディレクトリ
        prefix: 表示時のプレフィックス
        max_depth: 最大探索深度
        current_depth: 現在の深度
        exclude_dirs: 除外するディレクトリ名のリスト

    Example:
        print_tree(Path("/path/to/dir"), max_depth=3, exclude_dirs=[".git", "__pycache__"])
    """
    if current_depth >= max_depth:
        return

    if exclude_dirs is None:
        exclude_dirs = ["__pycache__", ".git", ".obsidian"]

    try:
        items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    except PermissionError:
        debug_log(f"Permission denied: {directory}")
        return

    for i, item in enumerate(items):
        # 除外するディレクトリをスキップ
        if item.is_dir() and item.name in exclude_dirs:
            continue

        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "

        # ディレクトリには末尾に/を付ける
        display_name = f"{item.name}/" if item.is_dir() else item.name
        print(f"{prefix}{connector}{display_name}")

        if item.is_dir() and item.name not in exclude_dirs:
            extension = "    " if is_last else "│   "
            print_tree(item, prefix + extension, max_depth, current_depth + 1, exclude_dirs)

def wait_for_lock_release(lock_file_path: Path, timeout: float = 5.0):
    """
    指定されたロックファイルが削除されるまで待機

    Args:
        lock_file_path: ロックファイルのパス（Pathオブジェクト）
        timeout: 最大待機時間（秒）。デフォルト5秒
    """
    import time

    try:
        waited = 0
        wait_interval = 0.05  # 50ms

        while lock_file_path.exists() and waited < timeout:
            time.sleep(wait_interval)
            waited += wait_interval

        if waited >= timeout:
            debug_log(f"wait_for_lock_release({lock_file_path.name}): timeout after {timeout}s")
        elif waited > 0:
             # debug_log(f"wait_for_lock_release({lock_file_path.name}): waited {waited:.2f}s")
             return

    except Exception as e:
        debug_log(f"wait_for_lock_release: error: {e}")

def speak_windows_tts(text: str, rate: int = 0) -> bool:
    """
    Windows SAPI TTSで音声読み上げ

    Args:
        text: 読み上げるテキスト
        rate: 読み上げ速度（-10〜10、デフォルト: 0）

    Returns:
        bool: 成功時True、失敗時False
    """
    if sys.platform != 'win32':
        debug_log("speak_windows_tts: Not Windows platform, skipping")
        return False

    import subprocess

    # 特殊文字をエスケープ
    text_escaped = text.replace('"', '`"').replace("'", "''")

    ps_script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = {rate}
$synth.Speak("{text_escaped}")
'''

    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            debug_log(f"speak_windows_tts: Success - '{text[:30]}...'")
            return True
        else:
            debug_log(f"speak_windows_tts: Failed - {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        debug_log("speak_windows_tts: Timeout")
        return False
    except Exception as e:
        debug_log(f"speak_windows_tts: Error - {e}")
        return False

def stop_tool_use(message: str):
    """
    PreToolUse hookでツール実行をブロックする

    Args:
        message: Claudeに表示するブロック理由

    Note:
        この関数は sys.exit(2) を呼び出すため、呼び出し後は処理が終了します。
        exit(2) は stderr を Claude にフィードバックしてブロックします。
    """
    print(message, file=sys.stderr)
    sys.exit(2)


def show_windows_toast(
    title: str,
    message: str,
    app_id: str = "Claude Code",
    on_click_script: str | None = None
) -> bool:
    """
    windows-toastsライブラリを使用してWindowsトースト通知を表示

    Args:
        title: 通知のタイトル
        message: 通知のメッセージ
        app_id: アプリケーションID（デフォルト: "Claude Code"）
        on_click_script: 通知クリック時に実行するスクリプトパス（.bat推奨）

    Returns:
        bool: 成功時True、失敗時False
    """
    if sys.platform != 'win32':
        debug_log("show_windows_toast: Not Windows platform, skipping")
        return False

    try:
        from windows_toasts import Toast, WindowsToaster
    except ImportError:
        debug_log("show_windows_toast: windows-toasts not installed")
        return False

    try:
        from pathlib import Path

        toaster = WindowsToaster(app_id)
        toast = Toast()
        toast.text_fields = [title, message]

        # 通知クリック時のアクションを設定（launch_action方式）
        if on_click_script:
            script_path = Path(on_click_script)
            if script_path.exists():
                # launch_actionに絶対パスを設定
                # Windowsがクリック時に直接このパスを起動する
                toast.launch_action = str(script_path.resolve())
                debug_log(f"show_windows_toast: launch_action set to '{script_path.resolve()}'")

        toaster.show_toast(toast)
        debug_log(f"show_windows_toast: Success - '{title}'")
        return True

    except Exception as e:
        debug_log(f"show_windows_toast: Error - {e}")
        return False


def notify_user(
    title: str,
    message: str,
    speak: bool = True,
    speak_text: str | None = None,
    on_click_script: str | None = None
) -> dict:
    """
    windows-toastsベースのトースト通知 + オプションでTTS読み上げ

    Args:
        title: 通知のタイトル
        message: 通知のメッセージ
        speak: TTSで読み上げるか（デフォルト: True）
        speak_text: 読み上げテキスト（省略時はmessageを使用）
        on_click_script: 通知クリック時に実行するPythonスクリプトパス（オプション）

    Returns:
        dict: {"toast": bool, "tts": bool} 各機能の成否
    """
    result = {"toast": False, "tts": False}

    # トースト通知
    result["toast"] = show_windows_toast(title, message, on_click_script=on_click_script)

    # TTS読み上げ
    if speak:
        tts_text = speak_text if speak_text else message
        result["tts"] = speak_windows_tts(tts_text)

    return result


def estimate_tokens(text: str) -> int:
    """
    テキストのトークン数を推定する（簡易的な推定）

    Args:
        text: トークン数を推定するテキスト

    Returns:
        推定トークン数

    Note:
        実際のトークナイザーは使用せず、文字数から推定します。
        英語: 約4文字 = 1トークン
        日本語: 約1.5文字 = 1トークン
        混在テキストは平均的な比率で推定
    """
    if not text:
        return 0

    # ASCII文字と非ASCII文字をカウント
    ascii_count = sum(1 for c in text if ord(c) < 128)
    non_ascii_count = len(text) - ascii_count

    # 英語は約4文字で1トークン、日本語は約1.5文字で1トークン
    ascii_tokens = ascii_count / 4
    non_ascii_tokens = non_ascii_count / 1.5

    return int(ascii_tokens + non_ascii_tokens)


if __name__ == '__main__':
    # テスト用
    log_hook_execution()
    debug_log("テストメッセージ")
    print("ログ記録のテストが完了しました。")
