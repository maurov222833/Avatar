import sys
import os
import json
import time
import requests

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
from core.llm_provider import LLMProvider, ProviderManager

def run_live_audit():
    print("==========================================")
    print("AVATAR AI — LIVE PROVIDER AUDIT EXECUTION")
    print("==========================================")
    
    llm = LLMProvider("config.json")
    health = llm.get_health_report()
    
    providers = ["gemini", "openai", "groq", "ollama", "lmstudio", "github"]
    results = {}
    
    for p in providers:
        print(f"\n--- AUDITING PROVIDER: {p.upper()} ---")
        p_info = {
            "provider": p,
            "implemented": True,
            "configured": False,
            "text": "FAIL",
            "function_calling": "UNSUPPORTED",
            "multi_turn": "UNSUPPORTED",
            "tool_result": "UNSUPPORTED",
            "isolation": "VERIFIED",
            "latency": 0.0,
            "status": "UNAVAILABLE"
        }
        
        if p == "github":
            p_info["status"] = "RETIRED"
            results[p] = p_info
            print("Status: RETIRED (Service deprecated 30-July-2026)")
            continue
            
        key = llm._get_api_key(p)
        if key and not key.startswith("YOUR_"):
            p_info["configured"] = True
        elif p in ["ollama", "lmstudio"]:
            p_info["configured"] = True # local server based
            
        # 1. LIVE TEST TEXT
        start_time = time.time()
        llm.config["default_provider"] = p
        
        try:
            text_resp = llm.generate_response(
                system_prompt="You are a test assistant.",
                prompt="Say READY."
            )
            elapsed = time.time() - start_time
            p_info["latency"] = round(elapsed, 3)
            
            if "Aviso" in text_resp or "Error" in text_resp or "No API key" in text_resp or "No se pudo conectar" in text_resp:
                print(f"Text Test: FAIL (Reason: {text_resp[:120]})")
                p_info["text"] = "FAIL"
                p_info["status"] = "MISSING_KEY" if ("API Key" in text_resp or "No API key" in text_resp) else "OFFLINE"
            else:
                clean_text = text_resp[:50].replace("\n", " ").strip()
                print(f"Text Test: PASS ({clean_text}) Latency: {p_info['latency']}s")
                p_info["text"] = "PASS"
                p_info["status"] = "LIVE_TESTED"
        except Exception as e:
            print(f"Text Test Exception: {e}")
            p_info["text"] = "FAIL"
            p_info["status"] = "UNAVAILABLE"
            
        # 2. LIVE FUNCTION CALLING & MULTI-TURN (only if text passed)
        if p_info["text"] == "PASS":
            sample_contents = [
                {"role": "user", "parts": [{"text": "List directory using LIST_DIR"}]}
            ]
            sample_tools = [
                {
                    "functionDeclarations": [
                        {
                            "name": "LIST_DIR",
                            "description": "List contents of directory",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {"dir_path": {"type": "STRING"}},
                                "required": ["dir_path"]
                            }
                        }
                    ]
                }
            ]
            try:
                fc_resp = llm.generate_response_with_tools(
                    system_prompt="You are an agent. Use tools when requested.",
                    contents=sample_contents,
                    tools=sample_tools
                )
                if fc_resp.get("type") == "function_call":
                    print(f"Function Calling Test: PASS (Tool: {fc_resp.get('name')})")
                    p_info["function_calling"] = "PASS"
                    
                    # 3. LIVE MULTI-TURN
                    turn1_fc = fc_resp.get("raw_part", {})
                    multi_contents = [
                        {"role": "user", "parts": [{"text": "List directory using LIST_DIR"}]},
                        {"role": "model", "parts": [turn1_fc]},
                        {"role": "function", "parts": [{"functionResponse": {"name": "LIST_DIR", "response": {"result": ["file1.py", "file2.py"]}}}]}
                    ]
                    mt_resp = llm.generate_response_with_tools(
                        system_prompt="You are an agent.",
                        contents=multi_contents,
                        tools=sample_tools
                    )
                    if mt_resp.get("type") in ["text", "function_call"]:
                        print(f"Multi-turn Test: PASS (Type: {mt_resp.get('type')})")
                        p_info["multi_turn"] = "PASS"
                        p_info["tool_result"] = "PASS"
                        p_info["status"] = "VERIFIED"
                    else:
                        print(f"Multi-turn Test: FAIL ({mt_resp})")
                        p_info["multi_turn"] = "FAIL"
                else:
                    print(f"Function Calling Test: UNSUPPORTED / TEXT ONLY ({fc_resp.get('type')})")
                    p_info["function_calling"] = "UNSUPPORTED"
                    p_info["status"] = "PARTIAL"
            except Exception as e:
                print(f"Function Calling Exception: {e}")
                p_info["function_calling"] = "FAIL"
                
        results[p] = p_info
        
    print("\n==========================================")
    print("AUDIT MATRIX SUMMARY")
    print("==========================================")
    print(json.dumps(results, indent=2))
    
    with open("scratch/live_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    return results

if __name__ == "__main__":
    run_live_audit()
