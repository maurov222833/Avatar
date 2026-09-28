import os
import sys
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_provider import LLMProvider

def check_providers():
    print("=" * 80)
    print("EVALUACIÓN DE DISPONIBILIDAD DE PROVEEDORES DE IA EN AVATAR")
    print("=" * 80)

    llm = LLMProvider()
    config = llm.config
    print(f"Configuración por defecto: {config}")

    # 1. Check Gemini
    gemini_key = llm._get_api_key("gemini")
    print(f"Gemini API Key configurada: {'SÍ' if gemini_key else 'NO'}")
    
    # 2. Check OpenAI
    openai_key = llm._get_api_key("openai")
    print(f"OpenAI API Key configurada: {'SÍ' if openai_key else 'NO'}")

    # 3. Check Ollama
    ollama_url = config.get("ollama", {}).get("url", "http://localhost:11434")
    ollama_running = False
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=3)
        if r.status_code == 200:
            ollama_running = True
            print(f"Ollama local en {ollama_url}: ACTIVO. Modelos: {r.json()}")
        else:
            print(f"Ollama local en {ollama_url}: HTTP {r.status_code}")
    except Exception as e:
        print(f"Ollama local en {ollama_url}: INACTIVO ({e})")

    # Check function calling capability in LLMProvider
    # generate_response_with_tools currently routes through _query_gemini REST API
    print("-" * 80)
    print("Evaluando capacidad de Function Calling NATIVO en LLMProvider...")
    test_result = llm.generate_response_with_tools(
        system_prompt="Test system",
        contents=[{"role": "user", "parts": [{"text": "Hola"}]}]
    )
    print(f"Resultado de generate_response_with_tools: {test_result}")
    print("-" * 80)

if __name__ == "__main__":
    check_providers()
