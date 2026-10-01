# ADR — AST de PowerShell (U3) — cerrado

Fecha: 2026-10-01. Mauro pidió cerrar el analizador. No hay un parser nuevo.

## Decisión

Queda la alternativa 1. El clasificador de `core/command_risk.py` es el analizador: `Invoke-Expression`, `iex`, bajar la política de ejecución, `format`, `diskpart`, `bcdedit`, borrar registro y apagar el firewall salen `PROHIBITED`. `-EncodedCommand`, aquí-strings y composición salen al menos C. Un envoltorio no baja el nivel. Si el texto no se entiende, el nivel es C.

La alternativa 2 no se escribe. Un árbol a medias que clasifique de menos sería peor que este fallo cerrado. La alternativa 3, pedirle el árbol a PowerShell en el PC, sigue `UNVERIFIED` hasta que ese PC la ejecute.

## Problema

El clasificador actual usa expresiones y `shlex`. Un envoltorio puede subir el nivel, no bajarlo. No entiende el lenguaje de PowerShell: alias, splat, here-strings, ni el árbol real de un script.

## Alternativas

1. **Dejar el clasificador actual.** Ya niega lo que no entiende (nivel C) y bloquea lo prohibido. No cubre un script ofuscado que el regex no vea.
2. **AST de PowerShell, solo para clasificar.** Un parser genera el árbol. El efecto de cada nodo se traduce a A, B, C, D o PROHIBITED. Sin AST aprobado, no se ejecuta nada nuevo.
3. **Pedirle a PowerShell el árbol** (`[System.Management.Automation.Language.Parser]::ParseInput`) en el PC de Mauro. Eso es código y una dependencia de Windows. No entra en este documento.

## Qué se parsearía, si Mauro aprueba el código

- Comando y argumentos, no solo la primera palabra.
- Alias conocidos (`ls` → `Get-ChildItem`, `iex` → `Invoke-Expression`) como el comando real.
- Tuberías y encadenamiento como composición, nunca como nivel A.
- `-EncodedCommand` y cadenas reconstruidas como ofuscación.

## Allowlist

Sigue siendo la línea completa, no un prefijo. `git diff` permitido no autoriza `git diff --output=...`. La lista vive en `config/avatar/command_allowlist.yaml`.

## Clasificación por efecto

- Leer estado local: A.
- Escribir dentro del alcance de la misión: B.
- Red, instalación global, push: C.
- Borrar, reiniciar, descartar trabajo, force push: D.
- Formatear, `diskpart`, `bcdedit`, borrar registro, `Invoke-Expression`, bajar la política de ejecución, apagar el firewall: PROHIBITED. No se aprueban.

## Registro

Cada autorización de misión sigue en el grant (`core/grants.py`): niveles, caducidad, y `allow_level_c` explícito. D y PROHIBITED no los concede el grant. `exec_requires_approval` no se apaga.

## Riesgos

Un AST incompleto que clasifique de menos sería peor que el fallo cerrado de hoy. Por eso no se añade un parser. Si el clasificador duda, el nivel es C o PROHIBITED, nunca A.

## Decisión que falta

Ninguna. La alternativa 2 queda rechazada por el riesgo que este mismo ADR nombra.
