import sys
import os

# Ensure UTF-8 output encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.orchestrator import AvatarOrchestrator

mission_prompt = (
    "Analiza el estado actual de Avatar como sistema de ingeniería autónoma. "
    "Investiga su arquitectura, su flujo de ejecución y sus pruebas actuales. "
    "Determina si existe alguna debilidad real que pueda limitar su capacidad para desarrollar software de forma autónoma. "
    "Si encuentras una debilidad real y suficientemente demostrada, decide por ti mismo qué debería hacerse para resolverla y, si está justificado, implementa la solución. "
    "Si no encuentras una debilidad suficientemente demostrada, no modifiques código simplemente para producir actividad. "
    "En ambos casos debes justificar tu conclusión mediante evidencia reproducible. "
    "Ejecuta las pruebas necesarias y realiza regresión. "
    "Explica qué investigaste, qué encontraste, qué decidiste y por qué."
)

print("=" * 80)
print("AUDITORÍA INDEPENDIENTE DE GATES F Y G — EJECUCIÓN DE MISIÓN ABIERTA")
print("=" * 80)
print(f"PROMPT EXACTO DE LA MISIÓN:\n{mission_prompt}\n")

orchestrator = AvatarOrchestrator()
response = orchestrator.process_user_input(mission_prompt, max_steps=15)

print("\n" + "=" * 80)
print("RESPUESTA FINAL DEVUELTA POR AVATAR AI:")
print("=" * 80)
print(response)
print("=" * 80)
