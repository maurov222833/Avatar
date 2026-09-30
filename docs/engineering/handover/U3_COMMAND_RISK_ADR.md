# ADR — Clasificación de riesgo de comandos (U3)

Fecha: 2026-09-30. Mauro autorizó seguir con todas las unidades, así que este ADR y el código van juntos. `exec_requires_approval` sigue en verdadero.

## Decisión

- Niveles A, B, C, D y PROHIBITED, en `core/command_risk.py`.
- Sin un grant de misión, un comando sigue pidiendo aprobación, igual que antes.
- Con grant, solo A y B dentro de ese grant se ejecutan sin preguntar otra vez. C y D siguen en la puerta de aprobación. PROHIBITED no se puede aprobar.
- Si el texto no se analiza (comillas rotas, ofuscación, tuberías, `Invoke-Expression`), no es nivel A.
- No hay parser AST de PowerShell en este entorno. Ante duda, el nivel es C.

## Marcha atrás

Quitar `mission_grant` del policy. Sin grant, el camino nuevo no deja pasar comandos. El flag `exec_requires_approval` no se apaga.
