$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Avatar AI.lnk'
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = 'C:\Users\Mauro\AppData\Local\Programs\Python\Python312\pythonw.exe'
$Shortcut.Arguments = '"b:\PROYECTOS ANTIGRAVITY\Avatar\main_gui.py"'
$Shortcut.WorkingDirectory = 'b:\PROYECTOS ANTIGRAVITY\Avatar'
$Shortcut.IconLocation = 'b:\PROYECTOS ANTIGRAVITY\Avatar\assets\avatar.ico'
$Shortcut.WindowStyle = 1
$Shortcut.Save()
