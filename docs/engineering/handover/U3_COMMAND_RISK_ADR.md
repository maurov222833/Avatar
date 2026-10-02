# ADR — Clasificación de riesgo de comandos (U3, fase 1)

Fecha de este texto: 2026-10-02. Incorpora la revisión condicional de Mauro. El otro ADR es `U3_POWERSHELL_AST_ADR.md`.

Estado: aprobado condicionalmente. No se da por cerrado. `exec_requires_approval` sigue en verdadero. No hay código de AST.

## Problema

La aprobación obligatoria cubre el riesgo EXEC: `COMMAND`, `DESKTOP_CLICK` y `DESKTOP_TYPE`. Leer y varios actos locales no pasan por esa puerta. Hace falta un modelo por efecto, sin apagar la aprobación general, y sin tratar igual un `git push` que un comando que el clasificador no entiende.

## Decisión

Queda el clasificador de `core/command_risk.py` (expresiones y `shlex`). No se añade un parser de PowerShell.

- Niveles A, B, C entendido, `UNUNDERSTOOD`, D y `PROHIBITED`.
- Sin grant, un comando sigue pidiendo aprobación.
- Con grant, solo A y B de ese grant pasan sin preguntar otra vez. C entendido exige `allow_level_c`. D, `PROHIBITED` y lo no entendido no los concede el grant.
- Lo no entendido (`UNUNDERSTOOD`: comando desconocido, tubería o `;`/`&`, texto que no se puede partir, `UNCLASSIFIED_DEFAULT_C`, git sin subcomando o con subcomando desconocido) pide siempre aprobación interactiva y el aviso lleva el comando completo.
- Lo ofuscado es `PROHIBITED`: `-EncodedCommand`, concatenación de cadenas (`"a" + "b"`), sustitución `$(` / `${`, y un `iex` camuflado con comilla invertida. No se puede aprobar.
- Un envoltorio (`powershell -Command`, `cmd /c`, `bash -c`, `sudo`) no baja el nivel.
- La allowlist sigue siendo la línea completa. Vive en `config/avatar/command_allowlist.yaml`.

## C entendido y lo no entendido

| Clase | Ejemplos | Grant con `allow_level_c` |
|---|---|---|
| C entendido | `git push` sin force, `curl`/`wget`/`irm`, `git diff --output`, `Get-ChildItem Env:`, `sc start`, `git reset` sin `--hard`, `git clean` parcial, `npm install`, `pip install`, `pip install -r` sin `--require-hashes`, `echo` | Puede dejarlo pasar |
| No entendido | Comando desconocido, `git` a secas, `git frobnicate`, `git status; rm x`, `Get-Content a \| findstr x`, comillas rotas | No. Siempre pregunta y muestra la línea entera |
| Ofuscado | `-EncodedCommand`, `"who" + "ami"`, `` i`ex `` | `PROHIBITED`. Ni el grant ni una aprobación lo ejecutan |

## Niveles de la directriz, en comandos concretos

| Nivel | Efecto (directriz 5.3) | Lo que clasifica el código |
|---|---|---|
| A | Lectura y pruebas no destructivas, sin ruta protegida | `git status`/`diff`/`log`/`show`, `pytest`, `python -m pytest`, `npm test`, `ls`, `dir`, `pwd`, `whoami`, `cat`, `type`, `Get-ChildItem`, `Get-Content`, `Get-Location` |
| B | Escritura reversible, o un install fijado | `git add`, `git commit`, `git checkout`/`switch` sin descartar. Install desde archivo con versiones y hashes: `pip install --require-hashes -r <archivo>`, `npm ci`, `pnpm`/`yarn install --frozen-lockfile` |
| C entendido | Efecto conocido fuera de lo rutinario | Ver la tabla de arriba |
| UNUNDERSTOOD | El texto no se entendió | Ver la tabla de arriba. Motivos: `UNCLASSIFIED_DEFAULT_C`, `COMPOSITION`, `UNPARSEABLE`, `EMPTY_COMMAND`, `GIT_BARE`, `GIT_OTHER` |
| D | Destructivo, o una lectura que nombra una ruta protegida | `git push --force`, `git reset --hard`, `git clean -fd`, `git checkout --`/`restore`, `git branch -d`, `rm`/`del`/`Remove-Item`, `shutdown`. También `Get-Content ~/.ssh/id_rsa`, `cat .aws/credentials`, una ruta con `AppData`, `.gnupg`, perfil de navegador (`user data`, `.mozilla`, `google-chrome`) o un nombre de clave (`id_rsa`, `id_ed25519`) |
| PROHIBITED | Sin aprobación posible | `format`, `diskpart`, `bcdedit`, `reg delete`, `Set-ExecutionPolicy`, `Invoke-Expression`, `iex`, `irm \| iex`, `runas`, firewall, y la ofuscación de la tabla anterior |

La lista de rutas protegidas de una lectura es la de credenciales, perfiles de navegador y claves que está en `core/command_risk.py` (`_PROTECTED_PATH_PARTS`). Se mira cada argumento ya partido, no un trozo suelto del texto. `Get-Content readme.txt` sigue en A.

`DESKTOP_CLICK` y `DESKTOP_TYPE` no tienen línea de comando. Siguen pidiendo aprobación.

El clasificador no abre el archivo de requisitos. Acepta como install fijado solo la forma canónica del comando (`--require-hashes` junto con `-r`, o `npm ci`, o `--frozen-lockfile`). Si el archivo no trae hashes, pip lo rechaza al correr.

## Desviación aceptada

El análisis es estructural, no el árbol de PowerShell. Mauro acepta esa desviación con una condición: hay que revisarla antes de usar `allow_level_c` por primera vez y antes de encender el modo noche. Hasta esa revisión, este ADR no se da por cerrado y no se enciende ninguna de esas dos cosas.

Hueco de esa revisión: la redirección `>` no se trata como composición. `echo texto > archivo` queda en C entendido. No se inventa un parser para cerrarlo ahora.

## Transición

1. El chokepoint sigue consultando `exec_requires_approval` antes de un EXEC.
2. `PROHIBITED` se niega aunque alguien apruebe. Lo no entendido sale `COMMAND_NOT_UNDERSTOOD` y entra en la cola de aprobación con el comando completo. Un grant no lo salta, y apagar `exec_requires_approval` tampoco: sigue pidiendo aprobación interactiva.
3. Sin grant, el comando rutinario también espera aprobación.
4. Lecturas `READ_FILE` y `LIST_DIR` no pasan a pedir aprobación por este documento.

## Revisión

- `tests/test_spec003.py`, `test_battery_of_commands`, cubre ofuscación, desconocidos, composición y rutas protegidas.
- `allow_level_c` no autoriza `UNUNDERSTOOD` ni `PROHIBITED`.
- `exec_requires_approval` del policy por defecto sigue en verdadero.

## Marcha atrás

Quitar `mission_grant` del policy. Sin grant, el clasificador no deja pasar comandos por su cuenta. No se apaga `exec_requires_approval`.

## Qué no entra

No se escribe un AST. La alternativa de un parser propio sigue rechazada en el otro ADR.
