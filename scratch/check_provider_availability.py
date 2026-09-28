import sys
import os
import json

sys.path.insert(0, os.path.abspath("."))
from core.llm_provider import LLMProvider

def test_provider(provider_name):
    print(f"\n==========================================")
    print(f"TESTING PROVIDER: {provider_name}")
    print(f"==========================================")
    provider = LLMProvider("config.json")
    provider.config["default_provider"] = provider_name
    
    # 1. Simple text test
    print("[1] Simple Text Request...")
    try:
        text_resp = provider.generate_response(
            system_prompt="You are a helpful assistant.",
            prompt="Respond with 'READY' if you are active."
        )
        print("  -> Response:", text_resp[:150])
    except Exception as e:
        print("  -> Exception:", str(e))
        text_resp = f"ERROR: {str(e)}"
        
    # 2. Tools test
    print("[2] Function Calling Request...")
    sample_contents = [
        {"role": "user", "parts": [{"text": "List the files in the directory using LIST_DIR"}]}
    ]
    sample_tools = [
        {
            "functionDeclarations": [
                {
                    "name": "LIST_DIR",
                    "description": "List contents of a directory",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "dir_path": {"type": "STRING", "description": "Target directory"}
                        },
                        "required": ["dir_path"]
                    }
                }
            ]
        }
    ]
    try:
        tool_resp = provider.generate_response_with_tools(
            system_prompt="You are an autonomous engineering agent.",
            contents=sample_contents,
            tools=sample_tools
        )
        print("  -> Response:", json.dumps(tool_resp, indent=2))
    except Exception as e:
        print("  -> Exception:", str(e))
        tool_resp = {"type": "exception", "error": str(e)}
        
    return {"text": text_resp, "tool": tool_resp}

if __name__ == "__main__":
    providers = ["openai", "groq", "github", "lmstudio", "ollama", "gemini"]
    summary = {}
    for p in providers:
        summary[p] = test_provider(p)
    print("\n==========================================")
    print("FINAL SUMMARY MATRIX")
    print("==========================================")
    print(json.dumps(summary, indent=2))
