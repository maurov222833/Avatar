import time
import sys
from core.rag_memory import RAGMemory
from tools.shell_tool import ShellTool

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class AutoLoopEngine:
    """
    MÓDULO 1: Bucle Autónomo de Autocorrección ReAct para Proyecto Avatar.
    Permite a Avatar ejecutar tareas multi-paso, detectar fallas y corregir errores automáticamente.
    """
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.memory = RAGMemory()

    def run_autonomous_step(self, user_prompt: str, max_retries: int = 3) -> str:
        self.memory.save_active_task(user_prompt, 10, "Ejecutando bucle autónomo...")
        
        attempt = 0
        current_input = user_prompt

        while attempt < max_retries:
            attempt += 1
            print(f"🤖 [AutoLoop Step {attempt}/{max_retries}]: Ejecutando acción autónoma...")
            
            response = self.orchestrator.process_user_input(current_input)

            if "Error" in response or "ERROR:" in response:
                print(f"⚠️ [AutoLoop Alert]: Error detectado en el paso {attempt}. Iniciando autocorrección...")
                current_input = f"El paso anterior generó un error: {response}. Corrígelo autónomamente y reintenta."
                time.sleep(1)
            else:
                self.memory.save_active_task(user_prompt, 100, "Completado exitosamente")
                return response

        return response
