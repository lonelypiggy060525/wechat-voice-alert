' 启动 微信语音提醒（无控制台窗口）
Set sh = CreateObject("WScript.Shell")
project = "D:\project\message notification"
sh.CurrentDirectory = project
sh.Run """" & project & "\.venv\Scripts\pythonw.exe"" """ & project & "\app.py""", 0, False
