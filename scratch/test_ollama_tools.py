import requests
import json

def test_ollama_tool_call():
    url = "http://localhost:11434/api/chat"
    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "COMMAND",
                "description": "Ejecuta un comando en la terminal PowerShell de Windows.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Comando PowerShell a ejecutar en Windows."}
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "LIST_DIR",
                "description": "Lista el contenido de un directorio local.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dir_path": {"type": "string", "description": "Ruta del directorio."}
                    },
                    "required": ["dir_path"]
                }
            }
        }
    ]

    payload = {
        "model": "qwen2.5-coder:latest",
        "messages": [
            {"role": "system", "content": "Eres Avatar AI. Responde invocando herramientas nativas."},
            {"role": "user", "content": "Lista los archivos en el directorio actual '.'"}
        ],
        "tools": tools_schema,
        "stream": False
    }

    try:
        r = requests.post(url, json=payload, timeout=60)
        print("Status Code:", r.status_code)
        if r.status_code == 200:
            res = r.json()
            print("Response Message:", json.dumps(res.get("message", {}), indent=2))
            return True
        else:
            print("Error Response:", r.text)
            return False
    except Exception as e:
        print("Exception:", e)
        return False

if __name__ == "__main__":
    test_ollama_tool_call()
