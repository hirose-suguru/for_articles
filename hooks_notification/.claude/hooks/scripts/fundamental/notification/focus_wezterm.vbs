' focus_wezterm.vbs
' 通知クリック時にWeztermをフォーカスする（ウィンドウ非表示で実行）
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' スクリプトのディレクトリを取得
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' batファイルを非表示で実行（0 = 非表示, False = 完了を待たない）
WshShell.Run """" & scriptDir & "\focus_wezterm_inner.bat""", 0, True
