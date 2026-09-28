import os
import sys
import subprocess

def build_avatar_executable():
    print("=" * 65)
    print(" 🛠️ EMPAQUETADOR AUTOMÁTICO DE PROYECTO AVATAR A .EXE ")
    print("=" * 65)

    avatar_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(avatar_dir, "main.py")
    dist_dir = os.path.join(avatar_dir, "dist")
    build_dir = os.path.join(avatar_dir, "build")

    # Verificar PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("📦 Instalando PyInstaller para empaquetado autónomo...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    print("\n🔨 Compilando Proyecto Avatar en un ejecutable portátil autónomo...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name=Avatar_AI",
        f"--add-data={os.path.join(avatar_dir, 'config.json')};.",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        main_py
    ]

    try:
        subprocess.run(cmd, check=True)
        print("\n" + "=" * 65)
        print(f" 🎉 ¡ÉXITO! Tu ejecutable de Avatar ha sido generado en:")
        print(f" 📂 {os.path.join(dist_dir, 'Avatar_AI')}")
        print(" Puedes copiar esa carpeta a cualquier PC y ejecutar 'Avatar_AI.exe'.")
        print("=" * 65)
    except Exception as e:
        print(f"\n❌ [Error durante la compilación]: {str(e)}")

if __name__ == "__main__":
    build_avatar_executable()
