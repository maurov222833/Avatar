import sys
import os
import json
import requests

sys.path.insert(0, os.path.abspath("b:/PROYECTOS ANTIGRAVITY/Avatar"))

from core.orchestrator import AvatarOrchestrator, AVATAR_TOOLS_SCHEMA

def test_gemini_role_user():
    orc = AvatarOrchestrator()
    api_key = orc.llm._get_api_key("gemini")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"

    # Probando payload con role: "user" para functionResponse
    contents = [
        {
            "role": "user",
            "parts": [{"text": "Analiza la arquitectura del proyecto Avatar AI."}]
        },
        {
            "role": "model",
            "parts": [{"functionCall": {"name": "LIST_DIR", "args": {"dir_path": "."}}}]
        },
        {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "name": "LIST_DIR",
                        "response": {"output": "core/ tools/ tests/ main.py requirements.txt"}
                    }
                },
                {
                    "text": "[MOTOR COGNITIVO - EVIDENCE GAP]: Únicamente se posee la lista de archivos. Falta inspección del código fuente. PRÓXIMO OBJETIVO DE INFORMACIÓN: Obtener evidencia sobre la implementación interna de los componentes principales. Selecciona e invoca libremente la herramienta nativa adecuada (COMMAND, READ_FILE, WRITE_FILE, LIST_DIR, etc.)."
                }
            ]
        }
    ]

    payload = {
        "contents": contents,
        "tools": AVATAR_TOOLS_SCHEMA
    }

    res = requests.post(url, json=payload, timeout=30)
    print(f"HTTP Status: {res.status_code}")
    print("RAW Response:\n", json.dumps(res.json(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_gemini_role_user()
