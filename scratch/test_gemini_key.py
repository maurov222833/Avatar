import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_provider import LLMProvider

def test_gemini():
    llm = LLMProvider()
    res = llm.generate_response_with_tools(
        system_prompt="Test system",
        contents=[{"role": "user", "parts": [{"text": "Hola, lista el directorio actual '.' con LIST_DIR"}]}],
        tools=[{
            "functionDeclarations": [{
                "name": "LIST_DIR",
                "description": "Lista el contenido de un directorio local.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "dir_path": {"type": "STRING", "description": "Ruta del directorio."}
                    },
                    "required": ["dir_path"]
                }
            }]
        }]
    )
    print("Gemini Result:", res)

if __name__ == "__main__":
    test_gemini()
