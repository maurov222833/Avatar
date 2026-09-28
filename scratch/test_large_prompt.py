import sys
import os

avatar_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if avatar_root not in sys.path:
    sys.path.insert(0, avatar_root)

from core.llm_provider import LLMProvider

def main():
    llm = LLMProvider()
    print("Testing large prompt handling...")
    large_prompt = "AUTHORITY CONSOLIDATION 005 EVIDENCE TRUST MODEL & AUTHORITY DESIGN\n" + ("Test line for payload limit check. " * 300)
    
    contents = [{"role": "user", "parts": [{"text": large_prompt}]}]
    
    res = llm.generate_response_with_tools("System Prompt Test", contents)
    print("Response Type:", res.get("type"))
    print("Response Provider:", res.get("provider"))
    if res.get("type") == "provider_error":
        print("Error:", res.get("error"))
    elif res.get("type") == "text":
        print("Text Snippet:", res.get("text")[:200])
    elif res.get("type") == "function_call":
        print("Function Call:", res.get("name"), res.get("args"))

if __name__ == "__main__":
    main()
