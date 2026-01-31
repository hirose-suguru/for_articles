#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_file_lock.py
ファイルをロックしているプロセスを調べる
"""
import sys
import subprocess
from pathlib import Path


def check_file_lock(file_path: str) -> str:
    """
    指定ファイルをロックしているプロセスを調べる

    Args:
        file_path: チェックするファイルのパス

    Returns:
        ロック情報の文字列
    """
    # まずファイルが開けるか試す
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write("")
        return f"File is NOT locked: {file_path}"
    except PermissionError:
        pass
    except Exception as e:
        return f"Unexpected error: {e}"

    # ロックされている場合、PowerShellでハンドルを調べる
    # Windows専用
    if sys.platform != 'win32':
        return "File is locked but cannot check on non-Windows"

    try:
        # openfiles コマンドを試す（管理者権限が必要）
        result = subprocess.run(
            ['openfiles', '/query', '/fo', 'csv'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            output = result.stdout.decode('cp932', errors='replace')
            file_name = Path(file_path).name
            lines = [line for line in output.split('\n') if file_name in line]
            if lines:
                return f"Locked by (openfiles): {lines}"
    except Exception:
        pass

    # PowerShellでハンドル情報を取得（handle.exeなしで）
    try:
        ps_script = f'''
        $file = "{file_path.replace(chr(92), chr(92)+chr(92))}"
        Get-Process | ForEach-Object {{
            $proc = $_
            try {{
                $proc.Modules | ForEach-Object {{
                    if ($_.FileName -like "*$file*") {{
                        Write-Output "$($proc.ProcessName) (PID: $($proc.Id))"
                    }}
                }}
            }} catch {{}}
        }}
        '''
        result = subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True,
            timeout=10
        )
        output = result.stdout.decode('utf-8', errors='replace').strip()
        if output:
            return f"Possibly locked by: {output}"
    except Exception as e:
        pass

    return f"File IS locked but could not determine which process: {file_path}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: check_file_lock.py <file_path>")
        sys.exit(1)

    result = check_file_lock(sys.argv[1])
    print(result)
