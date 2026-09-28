import os
import sys
import subprocess
from PIL import Image, ImageDraw

def generate_futuristic_avatar_icon(icon_path: str):
    os.makedirs(os.path.dirname(icon_path), exist_ok=True)
    
    # Crear imagen 256x256 RGBA de alta resolución
    size = (256, 256)
    img = Image.new("RGBA", size, (11, 15, 25, 255)) # Dark navy background
    draw = ImageDraw.Draw(img)

    # 1. Anillos cibernéticos de fondo (Cyan brillante y violeta)
    draw.ellipse([20, 20, 236, 236], outline=(0, 229, 255, 200), width=6)
    draw.ellipse([40, 40, 216, 216], outline=(138, 43, 226, 150), width=4)
    draw.ellipse([65, 65, 191, 191], outline=(0, 229, 255, 255), width=5)

    # 2. Núcleo IA Central (Triángulo/Diamante Futurista)
    core_polygon = [(128, 75), (175, 128), (128, 181), (81, 128)]
    draw.polygon(core_polygon, fill=(0, 229, 255, 220), outline=(255, 255, 255, 255))
    
    # 3. Punto de poder central
    draw.ellipse([110, 110, 146, 146], fill=(255, 255, 255, 255))

    # Guardar como .ico con múltiples tamaños (256x256, 128x128, 64x64, 48x48, 32x32, 16x16)
    img.save(
        icon_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    )
    print(f"[OK] Icono futurista generado en: {icon_path}")

def update_desktop_shortcut_with_icon():
    avatar_dir = r"b:\PROYECTOS ANTIGRAVITY\Avatar"
    assets_dir = os.path.join(avatar_dir, "assets")
    icon_path = os.path.join(assets_dir, "avatar.ico")
    
    # 1. Generar icono
    generate_futuristic_avatar_icon(icon_path)

    # 2. Actualizar archivo .bat temático para la aplicación GUI de Escritorio
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    bat_path = os.path.join(desktop, "Iniciar_Avatar.bat")
    main_gui = os.path.join(avatar_dir, "main_gui.py")

    bat_content = f"""@echo off
title ⚡ AVATAR AI - Sovereign Agent Workspace GUI
cd /d "{avatar_dir}"
python "{main_gui}"
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # 3. Actualizar el acceso directo en el Escritorio con el icono futurista creado
    lnk_path = os.path.join(desktop, "Avatar AI.lnk")
    ps_script = f"""
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Avatar AI.lnk'
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = 'cmd.exe'
$Shortcut.Arguments = '/c "{bat_path}"'
$Shortcut.WorkingDirectory = '{avatar_dir}'
$Shortcut.IconLocation = '{icon_path}'
$Shortcut.Save()
"""
    ps_file = os.path.join(avatar_dir, "update_icon_shortcut.ps1")
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_script)

    try:
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], check=True)
        print(f"[OK] Acceso directo actualizado con el icono temático futurista en: {lnk_path}")
    except Exception as e:
        print(f"[Aviso]: {e}")

if __name__ == "__main__":
    update_desktop_shortcut_with_icon()
