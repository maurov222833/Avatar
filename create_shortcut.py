import os
import sys
import subprocess

def create_desktop_shortcuts():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    avatar_dir = r"b:\PROYECTOS ANTIGRAVITY\Avatar"
    main_py = os.path.join(avatar_dir, "main.py")
    
    # 1. Crear ejecutable .bat en el Escritorio
    bat_content = f"""@echo off
title Avatar AI Terminal
cd /d "{avatar_dir}"
python "{main_py}"
pause
"""
    bat_path = os.path.join(desktop, "Iniciar_Avatar.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    
    print(f"[OK] Acceso directo ejecutable creado en: {bat_path}")

    # 2. Crear acceso directo .lnk de Windows mediante VBScript/PowerShell
    ps_script = f"""
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Avatar AI.lnk'
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = 'cmd.exe'
$Shortcut.Arguments = '/c "{bat_path}"'
$Shortcut.WorkingDirectory = '{avatar_dir}'
$Shortcut.IconLocation = 'shell32.dll,220'
$Shortcut.Save()
"""
    ps_file = os.path.join(avatar_dir, "make_lnk.ps1")
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_script)
    
    try:
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], check=True)
        print(f"[OK] Acceso directo icono Windows creado en: {os.path.join(desktop, 'Avatar AI.lnk')}")
    except Exception as e:
        print(f"[Aviso]: {e}")

if __name__ == "__main__":
    create_desktop_shortcuts()
