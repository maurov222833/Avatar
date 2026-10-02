# ADR — Clasificación de riesgo de comandos (U3, fase 1)

Fecha de este texto: 2026-10-02. Sustituye el resumen del 2026-09-30 que vivía en este mismo archivo. El cierre del analizador sigue en `U3_POWERSHELL_AST_ADR.md` (2026-10-01): la alternativa 2 no se escribe.

Estado: documento entregado. No hay código nuevo de AST en este paso. `exec_requires_approval` sigue en verdadero.

## Problema

Hoy la aprobación obligatoria cubre el riesgo EXEC: `COMMAND`, `DESKTOP_CLICK` y `DESKTOP_TYPE`. Leer y varios actos locales no pasan por esa puerta. La spec pide un modelo por efecto (A–D y prohibido), no por el nombre del acto, sin apagar la aprobación general.

## Decisión

Queda el clasificador de `core/command_risk.py`. No se añade un parser de PowerShell.

- Niveles A, B, C, D y `PROHIBITED`.
- Sin grant de misión, un comando sigue pidiendo aprobación, igual que ahora.
- Con grant, solo A y B de ese grant se ejecutan sin preguntar otra vez. C exige `allow_level_c` además del nivel. D y `PROHIBITED` no los concede el grant.
- Si el texto no se entiende (comillas rotas, ofuscación, tuberías, `Invoke-Expression`), no es A. Ante duda, C. Lo prohibido no tiene aprobación.
- Un envoltorio (`powershell -Command`, `cmd /c`, `bash -c`, `sudo`) no baja el nivel: el comando interior solo puede subirlo.
- La allowlist sigue siendo la línea completa, no un prefijo. Vive en `config/avatar/command_allowlist.yaml`.

## Niveles de la directriz, en comandos concretos

| Nivel | Efecto (directriz 5.3) | Lo que clasifica el código hoy |
|---|---|---|
| A | Lectura y pruebas no destructivas | `git status`, `git diff`, `git log`, `git show`, `pytest`, `python -m pytest`, `npm test`, `ls`, `dir`, `pwd`, `whoami`, `cat`, `type`, `Get-ChildItem`, `Get-Content`, `Get-Location` |
| B | Escritura reversible dentro del proyecto | `git add`, `git commit`, `git checkout` / `switch` sin descartar, `npm install` / `pnpm` / `yarn` sin `-g`, `pip install` sin `-g`, `--user` ni `--prefix` |
| C | Fuera del workspace, global, red, publicación | Comando vacío, git sin subcomando, `git diff --output`, `git push` sin force, `git reset` sin `--hard`, `git clean` parcial, `Env:`, instalación global, `sc`/`net` start/stop/delete, `curl`/`wget`/`irm`, y todo lo que no entra en otra fila (`UNCLASSIFIED_DEFAULT_C`) |
| D | Destructivo o irreversible | `git push --force`, `git reset --hard`, `git clean -fd`, `git checkout --` / `restore`, `git branch -d`, `rm` / `del` / `erase` / `Remove-Item` / `rmdir`, `shutdown` / `Restart-Computer` / `Stop-Computer` |
| PROHIBITED | Sin aprobación posible | `format`, `diskpart`, `bcdedit`, `reg delete`, `Set-ExecutionPolicy`, `Invoke-Expression`, `iex`, `irm \| iex`, `runas`, `Start-Process` con `RunAs`, `Set-MpPreference`, `netsh advfirewall` |

`DESKTOP_CLICK` y `DESKTOP_TYPE` no tienen línea de comando. Siguen en la puerta de EXEC: piden aprobación. No bajan a A por este ADR.

## Transición

1. El chokepoint sigue consultando `exec_requires_approval` antes de ejecutar un EXEC.
2. El clasificador corre dentro de esa puerta. Un `PROHIBITED` se niega aunque alguien apruebe. Un grant solo abre A y B, o C si el grant lo dice.
3. Sin grant, el comportamiento visible no cambia: el comando rutinario también espera aprobación.
4. Lecturas (`READ_FILE`, `LIST_DIR`) y otras escrituras locales no pasan a pedir aprobación por este documento. Moverlas al modelo por nivel sería otro paso, y no está autorizado aquí.

## Revisión

- La batería de `tests/test_spec003.py` (`test_battery_of_commands`) tiene que seguir clasificando como la tabla.
- Un comando ofuscado (`-EncodedCommand`, concatenación, sustitución) no sale A.
- `exec_requires_approval` del policy por defecto sigue en verdadero.
- El chokepoint niega un acto que el grant no cubre, aunque el modelo lo pida.

## Marcha atrás

Quitar `mission_grant` del policy. Sin grant, el clasificador no deja pasar comandos por su cuenta. No se apaga `exec_requires_approval`.

## Qué no entra

No se escribe un AST. La alternativa de un parser propio queda rechazada en `U3_POWERSHELL_AST_ADR.md`. Pedirle el árbol a PowerShell en el PC (`Parser.ParseInput`) sigue `UNVERIFIED` y no se codifica en este paso.
