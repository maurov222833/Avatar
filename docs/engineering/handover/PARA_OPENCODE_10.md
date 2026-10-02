# PARA_OPENCODE 10 — repetir la suite en Windows

Ejecutor: OpenCode, en el PC de Mauro, dentro de `b:\PROYECTOS ANTIGRAVITY\Avatar`.

La primera línea de la respuesta tiene que ser exactamente `INFORME_OPENCODE_10`.

No repitas el forense, los hashes ni la búsqueda de enlaces: el informe 9 ya los trajo. No fusiones a `main`. No toques `test_bot.py` ni `tools/telegram_notifier.py`. No regeneres la clave. No imprimas su contenido ni el de la base. No detengas ni habilites `AvatarWhatsApp247`: en el informe 9 apareció Disabled y Mauro decide eso. No declares `VERIFIED_WINDOWS`.

Si `git status` muestra algo más que esos dos archivos sin seguimiento, detente.

## Traer el arreglo

```text
cd "b:\PROYECTOS ANTIGRAVITY\Avatar"
git status
git fetch origin cursor/spec-003-u1-u17-5763
git merge --ff-only origin/cursor/spec-003-u1-u17-5763
git rev-parse HEAD
git merge-base --is-ancestor ae507e2a02fa7b0429a6321ebbe3837bdb3a3cf2 HEAD
echo ANCESTRO:$LASTEXITCODE
```

`ANCESTRO` tiene que ser 0. Ese commit deja `subprocess.Popen` como clase y devuelve `TARGET_NOT_FOUND` cuando el clic no tiene coordenadas.

## Tamaños, suite, tamaños

```text
Get-Item "memory\state_engine.db","memory\state_engine.db-wal","memory\state_engine.db-shm","memory\state_engine.db.seal_key","memory\screen_observation.png" -ErrorAction SilentlyContinue | Select-Object Name, Length, LastWriteTime | Format-List
python -m unittest discover -s tests -q
echo EXIT:$LASTEXITCODE
Get-Item "memory\state_engine.db","memory\state_engine.db-wal","memory\state_engine.db-shm","memory\state_engine.db.seal_key","memory\screen_observation.png" -ErrorAction SilentlyContinue | Select-Object Name, Length, LastWriteTime | Format-List
```

Pega el resumen (`Ran …`, fallos, errores, omitidas) y el código de salida. Si algo falla, pega ese traceback y no vuelvas a lanzar la suite.
