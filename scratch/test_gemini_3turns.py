import sys
import os
import json
import requests

sys.path.insert(0, os.path.abspath("b:/PROYECTOS ANTIGRAVITY/Avatar"))

from core.orchestrator import AvatarOrchestrator, AVATAR_TOOLS_SCHEMA

def test_3_turns():
    orc = AvatarOrchestrator()
    api_key = orc.llm._get_api_key("gemini")
    model = "gemini-3.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    print("=== TURN 1 ===")
    contents = [
        {
            "role": "user",
            "parts": [{"text": "Analiza la arquitectura del proyecto Avatar AI, inspecciona el orquestador principal y determina cómo funciona."}]
        }
    ]
    payload1 = {"contents": contents, "tools": AVATAR_TOOLS_SCHEMA}
    res1 = requests.post(url, json=payload1, timeout=30)
    print("Turn 1 Status:", res1.status_code)
    data1 = res1.json()
    part1 = data1["candidates"][0]["content"]["parts"][0]
    func1 = part1["functionCall"]
    print("Turn 1 Call:", func1)

    out1 = orc._dispatch_native_tool(func1["name"], func1.get("args", {}))

    print("\n=== TURN 2 ===")
    contents.append({"role": "model", "parts": [part1]})
    contents.append({
        "role": "user",
        "parts": [{
            "functionResponse": {
                "name": func1["name"],
                "response": {"output": out1}
            }
        }]
    })
    contents.append({
        "role": "user",
        "parts": [{
            "text": "[MOTOR COGNITIVO - EVIDENCE GAP]: Se posee la lista de archivos. Falta inspeccionar el código fuente del orquestador. NEXT_INFORMATION_TARGET: Inspeccionar core/orchestrator.py."
        }]
    })

    payload2 = {"contents": contents, "tools": AVATAR_TOOLS_SCHEMA}
    res2 = requests.post(url, json=payload2, timeout=30)
    print("Turn 2 Status:", res2.status_code)
    data2 = res2.json()
    parts2 = data2["candidates"][0]["content"]["parts"]
    part2 = parts2[0]
    print("Turn 2 Response parts:", parts2)

    if "functionCall" in part2:
        func2 = part2["functionCall"]
        out2 = orc._dispatch_native_tool(func2["name"], func2.get("args", {}))
        
        print("\n=== TURN 3 ===")
        contents.append({"role": "model", "parts": [part2]})
        contents.append({
            "role": "user",
            "parts": [{
                "functionResponse": {
                    "name": func2["name"],
                    "response": {"output": out2[:1000]}
                }
            }]
        })
        payload3 = {"contents": contents, "tools": AVATAR_TOOLS_SCHEMA}
        res3 = requests.post(url, json=payload3, timeout=30)
        print("Turn 3 Status:", res3.status_code)
        data3 = res3.json()
        print("Turn 3 Response:", json.dumps(data3["candidates"][0]["content"], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_3_turns()
