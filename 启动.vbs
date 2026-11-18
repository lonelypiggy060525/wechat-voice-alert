' 启动 微信语音提醒（无控制台窗口）
Set fso = CreateObject("Scripting.FileSystemObject")
project = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = project
sh.Run """" & project & "\.venv\Scripts\pythonw.exe"" """ & project & "\app.py""", 0, False
