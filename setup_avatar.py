import os
import sys
import subprocess
import requests

# Forzar UTF-8 en consola de Windows si está disponible
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def verify_and_setup_avatar():
    print("=" * 65)
    print(" [AVATAR] DIAGNÓSTICO Y CONFIGURACIÓN INICIAL - PROYECTO AVATAR ")
    print("=" * 65)

    # 1. Verificar Python
    print(f"[*] Python Version: {sys.version.split()[0]}")

    # 2. Verificar dependencias
    print("[*] Verificando dependencias en requirements.txt...")
    req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], check=True)
        print("[OK] Dependencias verificadas correctamente.")
    except Exception as e:
        print(f"[!] Aviso al instalar dependencias: {e}")

    # 3. Verificar Ollama Local
    print("\n[*] Verificando conexión con motor local (Ollama)...")
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=5)
        if res.status_code == 200:
            models = [m.get("name") for m in res.json().get("models", [])]
            print(f"[OK] Ollama detectado en ejecución.")
            print(f"     Modelos instalados: {models if models else 'Ninguno detectado aún.'}")
        else:
            print("[!] Ollama respondió con código de estado inusual.")
    except Exception:
        print("[!] Ollama no está ejecutándose en http://localhost:11434.")
        print("[+] Nota: Puedes iniciar Ollama localmente en cualquier momento o configurar tu API Key en config.json.")

    print("\n" + "=" * 65)
    print(" [OK] PROYECTO AVATAR LISTO PARA SER USADO EN TU COMPUTADORA ")
    print("=" * 65)

if __name__ == "__main__":
    verify_and_setup_avatar()
