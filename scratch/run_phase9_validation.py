import sys
import os

# Ensure UTF-8 output encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.orchestrator import AvatarOrchestrator

prompt = (
    "Investiga el estado actual del sistema de pruebas de Avatar.\n"
    "Determina si existe algún problema real que pueda afectar la confiabilidad del proceso de desarrollo.\n"
    "Investiga lo necesario, determina la causa de cualquier problema que encuentres y decide si existe alguna acción de ingeniería justificada.\n"
    "No modifiques código durante esta prueba.\n"
    "Debes justificar tu conclusión mediante evidencia reproducible."
)

print("=" * 80)
print("VALIDACIÓN POST-FASE 9 — PRUEBA DE INVESTIGACIÓN ADAPTATIVA REAL")
print("=" * 80)
print(f"PROMPT EXACTO:\n{prompt}\n")

orchestrator = AvatarOrchestrator()
response = orchestrator.process_user_input(prompt, max_steps=15)

print("\n" + "=" * 80)
print("RESPUESTA FINAL DEVUELTA POR AVATAR AI:")
print("=" * 80)
print(response)
print("=" * 80)
