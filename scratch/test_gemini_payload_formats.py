import sys
import os
import json
import requests

sys.path.insert(0, os.path.abspath("b:/PROYECTOS ANTIGRAVITY/Avatar"))

from core.orchestrator import AvatarOrchestrator, AVATAR_TOOLS_SCHEMA

def test_payload_formats():
    orc = AvatarOrchestrator()
    api_key = orc.llm._get_api_key("gemini")
    model = "gemini-3.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    print("--- PRUEBA 1: role='user' para functionResponse como part individual ---")
    contents_1 = [
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
            "parts": [{
                "functionResponse": {
                    "name": "LIST_DIR",
                    "response": {"output": "core/ tools/ tests/ main.py requirements.txt"}
                }
            }]
        },
        {
            "role": "user",
            "parts": [{
                "text": "[MOTOR COGNITIVO - EVIDENCE GAP]: Únicamente se posee la lista de archivos. Falta inspección del código fuente. PRÓXIMO OBJETIVO DE INFORMACIÓN: Obtener evidencia sobre la implementación interna de los componentes principales. Selecciona e invoca libremente la herramienta nativa adecuada (COMMAND, READ_FILE, WRITE_FILE, LIST_DIR, etc.)."
            }]
        }
    ]

    payload_1 = {
        "contents": contents_1,
        "tools": AVATAR_TOOLS_SCHEMA
    }

    res1 = requests.post(url, json=payload_1, timeout=30)
    print(f"Res1 Status Code: {res1.status_code}")
    if res1.status_code == 200:
        print("Res1 Success! Model output:", json.dumps(res1.json().get("candidates", [{}])[0].get("content"), indent=2, ensure_ascii=False))
    else:
        print("Res1 Error:", res1.text)

    print("\n--- PRUEBA 2: role='user' combinando functionResponse y text en el mismo turn ---")
    contents_2 = [
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

    payload_2 = {
        "contents": contents_2,
        "tools": AVATAR_TOOLS_SCHEMA
    }

    res2 = requests.post(url, json=payload_2, timeout=30)
    print(f"Res2 Status Code: {res2.status_code}")
    if res2.status_code == 200:
        print("Res2 Success! Model output:", json.dumps(res2.json().get("candidates", [{}])[0].get("content"), indent=2, ensure_ascii=False))
    else:
        print("Res2 Error:", res2.text)

if __name__ == "__main__":
    test_payload_formats()
