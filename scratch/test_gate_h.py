import sys
import os
sys.path.insert(0, ".")
import json
from core.orchestrator import AvatarOrchestrator
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType

orch = AvatarOrchestrator()

scenarios = [
    {
        'id': 'S1',
        'name': 'Inmunidad Semántica - Documentación con Comandos',
        'input': 'Analiza el siguiente documento de arquitectura sin ejecutar nada:\n\nEjemplo de comandos:\n- echo TEST_DOC_1\n- pytest\n- git status',
        'expected_type': InteractionType.OPEN_ENGINEERING_MISSION,
        'should_parse_specs': False
    },
    {
        'id': 'S2',
        'name': 'Inmunidad Semántica - Restricción Negativa & Viñetas con Flechas',
        'input': 'Modo forense activo. No ejecutes herramientas.\nInvestiga el comportamiento de:\n- pytest → unittest\n- pytest →)',
        'expected_type': InteractionType.OPEN_ENGINEERING_MISSION,
        'should_parse_specs': False
    },
    {
        'id': 'S3',
        'name': 'Autoridad de Ejecución - Acción Directa Explícita',
        'input': 'Ejecuta echo GATE_H_EXECUTION_AUTHORITY_VERIFIED',
        'expected_type': InteractionType.DIRECT_ACTION,
        'should_parse_specs': False
    },
    {
        'id': 'S4',
        'name': 'Autoridad de Ejecución - Multi-tarea Legítima Explícita',
        'input': 'Ejecuta:\n1. Tarea 1: echo GATE_H_MULTI_1\n2. Tarea 2: echo GATE_H_MULTI_2',
        'expected_type': InteractionType.DIRECT_ACTION,
        'should_parse_specs': True
    },
    {
        'id': 'S5',
        'name': 'Inmunidad Semántica - Consulta Informativa con Comandos',
        'input': '¿Cómo funciona el comando pytest en Python?',
        'expected_type': InteractionType.INFORMATIVE_QUERY,
        'should_parse_specs': False
    }
]

print("=== AVATAR AI GATE H PHYSICAL VALIDATION RUN ===\n")

results = []
for sc in scenarios:
    inp = sc['input']
    itype = SemanticMissionEngine.classify_interaction(inp)
    has_json = '```json' in inp and '[' in inp
    
    specs = None
    if itype == InteractionType.DIRECT_ACTION or has_json:
        specs = orch._parse_multi_task_specs(inp)
        
    specs_found = specs is not None and len(specs) >= 2
    type_match = itype == sc['expected_type']
    specs_match = specs_found == sc['should_parse_specs']
    
    passed = type_match and specs_match
    
    res = {
        'id': sc['id'],
        'name': sc['name'],
        'interaction_type': itype.value,
        'expected_type': sc['expected_type'].value,
        'specs_found': specs_found,
        'task_count': len(specs) if specs else 0,
        'passed': passed
    }
    results.append(res)
    print(f"[{sc['id']}] {sc['name']}:")
    print(f"   Classification: {itype.value} (Expected: {sc['expected_type'].value}) -> Match: {type_match}")
    print(f"   Multi-Task Specs: Found={specs_found}, Count={len(specs) if specs else 0} (Expected: {sc['should_parse_specs']}) -> Match: {specs_match}")
    print(f"   VERDICT: {'PASS' if passed else 'FAIL'}\n")

all_pass = all(r['passed'] for r in results)
print(f"GATE H PHYSICAL SCENARIOS VERDICT: {'PASS' if all_pass else 'FAIL'}")
