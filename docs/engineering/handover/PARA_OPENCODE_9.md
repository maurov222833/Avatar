# PARA_OPENCODE 9 — suite en Windows, tamaños, captura, hashes y forense

Ejecutor: OpenCode, en el PC de Mauro, dentro de `b:\PROYECTOS ANTIGRAVITY\Avatar`.

La primera línea de la respuesta tiene que ser exactamente `INFORME_OPENCODE_9`.

Este archivo no cambia ningún estado de evidencia. `VERIFIED_WINDOWS` lo decide Cursor cuando llegue el informe, no OpenCode.

No fusiones a `main`. No toques `test_bot.py` ni `tools/telegram_notifier.py`. No regeneres la clave de sello. No imprimas su contenido ni el de la base. No abras `C:\Windows` ni `System32` para escribir. No uses `Remove-Item -Recurse` ni `del /s` sobre un enlace: eso seguiría el junction y borraría el destino. No detengas la tarea `AvatarWhatsApp247`. No instales la tecla global. No hay AST de PowerShell.

Si `git status` no está limpio, o el merge no es fast-forward, detente y pega solo eso.

## 1. Traer el commit

```text
cd "b:\PROYECTOS ANTIGRAVITY\Avatar"
git status
git fetch origin cursor/spec-003-u1-u17-5763
git merge --ff-only origin/cursor/spec-003-u1-u17-5763
git rev-parse HEAD
```

Pega `git rev-parse HEAD`. Tiene que contener `79f337d4119503dc5162833c4d27247aae27afb8` (este encargo puede ir en un commit posterior, solo de documentación). Compruébalo:

```text
git merge-base --is-ancestor 79f337d4119503dc5162833c4d27247aae27afb8 HEAD
echo ANCESTRO:$LASTEXITCODE
```

Si `ANCESTRO` no es 0, detente.

## 2. Tamaños antes de la suite

Solo nombre, bytes y hora. Nada del contenido.

```text
Get-Item "memory\state_engine.db","memory\state_engine.db-wal","memory\state_engine.db-shm","memory\state_engine.db.seal_key","memory\screen_observation.png" -ErrorAction SilentlyContinue | Select-Object FullName, Length, LastWriteTime | Format-List
```

## 3. Suite

```text
python -m unittest discover -s tests -q
echo EXIT:$LASTEXITCODE
```

Pega el resumen (`Ran …`, `OK` o `FAILED`, omitidas) y el código de salida. Si hay fallos, pega el traceback de cada uno. No reejecutes la suite para “ver si ahora pasa”.

## 4. Tamaños después, y qué escribió la captura

El mismo `Get-Item` del paso 2.

Además, sin abrir la imagen:

```text
Get-ChildItem -Path "memory","$env:TEMP" -Filter "screen_observation.png" -Recurse -ErrorAction SilentlyContinue | Select-Object FullName, Length, LastWriteTime
```

Si `Get-ChildItem -Recurse` fuese a entrar en un junction, no lo hagas: lista `memory` sin recursión y, en `%TEMP%`, solo carpetas `avatar_test_*`.

## 5. Hashes de las dos specs en Descargas

No las edites. No las copies al repo.

```text
Get-FileHash -Algorithm SHA256 "$env:USERPROFILE\Downloads\AVATAR_ENGINEERING_SPEC_003_v2_COMPLETA.md"
Get-FileHash -Algorithm SHA256 "$env:USERPROFILE\Downloads\AVATAR_SPEC_003_ADDENDUM_3_U18_DIRECTOR_DE_DESARROLLO.md"
```

Si un archivo no está, lista los `.md` de Descargas cuyo nombre empiece por `AVATAR_` y hashea esos. Pega ruta, bytes y SHA-256. Esos hashes los usa Cursor para corregir `SPEC_PERDIDAS_DECISION.md`. No lo edites tú.

Los hashes ya archivados en el repo, para comparar y no para sustituir la medida, son:

- spec v2: `5e698e4a472f59ccc6a4999aa7293aead577c665bd38661737e5581e7bc549d1`
- adenda U18: `7735f8efa66d1f216e1aa9e5aef232dc9ea9572c35efe77157d17c262d73e6c2`

## 6. Quitar los dos enlaces que apuntan a C:\Windows

Están en el sandbox del repo, con los nombres `salto_fuera` y `enlace_fuera`. Primero mira el destino sin entrar:

```text
cmd /c dir /AL "b:\PROYECTOS ANTIGRAVITY\Avatar\sandbox\scope"
```

Si esa carpeta no existe, busca solo un nivel bajo `sandbox` (`dir /AL` sin `/S`). Para y dilo si no aparecen.

Cuando veas cada uno, confirma el destino:

```text
cmd /c fsutil reparsepoint query "b:\PROYECTOS ANTIGRAVITY\Avatar\sandbox\scope\salto_fuera"
cmd /c fsutil reparsepoint query "b:\PROYECTOS ANTIGRAVITY\Avatar\sandbox\scope\enlace_fuera"
```

Solo si el destino es `C:\Windows`, quita el enlace y no el destino:

```text
cmd /c rmdir "b:\PROYECTOS ANTIGRAVITY\Avatar\sandbox\scope\salto_fuera"
cmd /c rmdir "b:\PROYECTOS ANTIGRAVITY\Avatar\sandbox\scope\enlace_fuera"
```

Vuelve a listar con `dir /AL`. `C:\Windows` tiene que seguir existiendo. Si el destino no es exactamente `C:\Windows`, no borres nada.

## 7. Forense del ledger, sobre una copia del respaldo

No abras la base viva. Copia el respaldo a una carpeta de trabajo y lee esa copia.

```text
New-Item -ItemType Directory -Force ".test_scratch\forense_009" | Out-Null
Copy-Item "sandbox\respaldo_memory\state_engine.db" ".test_scratch\forense_009\state_engine.db"
Copy-Item "sandbox\respaldo_memory\state_engine.db-wal" ".test_scratch\forense_009\" -ErrorAction SilentlyContinue
Copy-Item "sandbox\respaldo_memory\state_engine.db-shm" ".test_scratch\forense_009\" -ErrorAction SilentlyContinue
python tools\ledger_forensics.py ".test_scratch\forense_009\state_engine.db"
```

Si el nombre dentro de `sandbox\respaldo_memory` no es `state_engine.db`, lista esa carpeta (nombre y bytes, sin abrir) y usa el `.db` que haya. Pega la salida entera de `ledger_forensics.py`. Al terminar:

```text
cmd /c rmdir /s /q ".test_scratch\forense_009"
```

Ese `rmdir` es de una carpeta normal de copias, no de un junction.

## Qué devolver

1. `git rev-parse HEAD` y el estado de `git status` antes del merge.
2. Tamaños de la base, `-wal`, `-shm` y `.seal_key` antes y después. La clave tiene que seguir midiendo 32 bytes.
3. Si `memory\screen_observation.png` cambió de hora o de tamaño, y cualquier otra ruta donde haya aparecido.
4. Resumen de la suite, código de salida, y tracebacks si los hay.
5. SHA-256 de las dos specs en Descargas.
6. Destino de cada enlace antes de quitarlo, y el `dir /AL` de después.
7. El informe del forense.

No declares `VERIFIED_WINDOWS`. No edites `SPEC_003_CIERRE.md` ni `SPEC_PERDIDAS_DECISION.md`.
