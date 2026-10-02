# ADR — AST de PowerShell (U3)

Fecha inicial: 2026-10-01. Corregido el 2026-10-02 con la revisión condicional. No hay un parser nuevo.

Estado: aprobado condicionalmente, no cerrado. La alternativa 2 no se escribe.

## Decisión

Queda la alternativa 1. El clasificador de `core/command_risk.py` es el analizador.

- `Invoke-Expression`, `iex`, bajar la política de ejecución, `format`, `diskpart`, `bcdedit`, borrar registro y apagar el firewall salen `PROHIBITED`.
- Lo ofuscado también sale `PROHIBITED`: `-EncodedCommand`, concatenación de cadenas y un `iex` partido con comilla invertida. No lo cubre un grant ni una aprobación.
- Una tubería, un `;`, un comando desconocido o `UNCLASSIFIED_DEFAULT_C` salen `UNUNDERSTOOD`. No lo cubre ningún grant, ni con `allow_level_c`. La aprobación muestra el comando completo.
- C entendido (`git push` sin force, `curl`, un `pip install` sin archivo de hashes) sí puede entrar en un grant que tenga `allow_level_c`.
- Un envoltorio no baja el nivel.
- `pip install` y `npm install` son C, salvo un install desde archivo con versiones y hashes en la propia línea (`--require-hashes -r`, `npm ci`, `--frozen-lockfile`), que es B.
- Un comando de lectura cuyo argumento nombra credenciales, un perfil de navegador o una clave deja de ser A y pasa a D.

La alternativa 2 no se escribe. Un árbol a medias que clasifique de menos sería peor que este fallo cerrado. La alternativa 3, pedirle el árbol a PowerShell en el PC (`Parser.ParseInput`), sigue `UNVERIFIED`. No se codifica aquí.

## Desviación aceptada

Analizar la línea con expresiones y `shlex`, en vez del árbol de PowerShell, es una desviación aceptada. La condición es revisarla antes de usar `allow_level_c` por primera vez y antes del modo noche. Esas dos cosas no se encienden con este documento.

## Problema

El clasificador no entiende el lenguaje de PowerShell: alias, splat, here-strings, ni el árbol real de un script. Por eso lo que no reconoce no queda en C aprobable por grant: queda en `UNUNDERSTOOD` o, si parece ofuscación, en `PROHIBITED`.

## Alternativas

1. **Dejar el clasificador actual**, con la separación de esta revisión. No cubre un script ofuscado que el patrón no vea: ese hueco es el motivo de la revisión futura.
2. **AST de PowerShell, solo para clasificar.** Rechazada. No se escribe.
3. **Pedirle a PowerShell el árbol** en el PC de Mauro. Sigue fuera de este documento y `UNVERIFIED`.

## Qué quedaría para un AST, si algún día se aprueba código

- Comando y argumentos, no solo la primera palabra.
- Alias conocidos (`iex` → `Invoke-Expression`) como el comando real.
- Tuberías como composición, nunca como nivel A.
- `-EncodedCommand` y cadenas reconstruidas como ofuscación, que ya es `PROHIBITED`.

Esa lista no es una autorización para escribirlo.

## Allowlist

Sigue siendo la línea completa, no un prefijo. `git diff` permitido no autoriza `git diff --output=...`. La lista vive en `config/avatar/command_allowlist.yaml`.

## Registro

Cada autorización de misión sigue en el grant (`core/grants.py`): niveles, caducidad y `allow_level_c` explícito. D, `UNUNDERSTOOD` y `PROHIBITED` no los concede el grant. `exec_requires_approval` no se apaga.

## Riesgos

Un AST incompleto que clasifique de menos sería peor que el fallo cerrado de hoy. El patrón actual también puede no ver una ofuscación nueva, y no ve la redirección `>`. `echo` es C entendido. Por eso la desviación se revisa antes de `allow_level_c` y antes del modo noche. Apagar `exec_requires_approval` no deja correr un comando no entendido.

## Decisión que falta

La revisión de esta desviación, antes del primer `allow_level_c` y antes del modo noche. La alternativa 2 sigue rechazada.
