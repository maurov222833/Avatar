import sys
import os

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.orchestrator import AvatarOrchestrator

mission_1_prompt = (
    "Analiza el estado actual de Avatar como sistema de ingeniería autónoma. "
    "Investiga su arquitectura y sus pruebas. "
    "Determina si existe una debilidad REAL que afecte su capacidad de desarrollo autónomo. "
    "Si encuentras una debilidad real y suficientemente justificada, diseña e implementa una solución. "
    "Si no encuentras una debilidad suficientemente demostrada, NO modifiques código simplemente para producir actividad. "
    "En ambos casos, debes justificar tu conclusión mediante evidencia reproducible. "
    "Ejecuta las pruebas necesarias y realiza regresión completa. "
    "Informa exactamente qué investigaste, qué decidiste y por qué."
)

print("=" * 80)
print("INICIANDO PRUEBA DE AUTONOMÍA ABIERTA — MISIÓN #1 DE AVATAR AI")
print("=" * 80)
print(f"PROMPT ENVIADO:\n{mission_1_prompt}\n")

orchestrator = AvatarOrchestrator()
response = orchestrator.process_user_input(mission_1_prompt, max_steps=10)

print("\n" + "=" * 80)
print("RESPUESTA FINAL DEVUELTA POR AVATAR AI (MISIÓN #1):")
print("=" * 80)
print(response)
print("=" * 80)
