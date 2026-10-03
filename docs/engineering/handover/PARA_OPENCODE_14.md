# PARA_OPENCODE 14 — nombrar las dos omitidas

Ejecutor: OpenCode, en el PC de Mauro, dentro de `b:\PROYECTOS ANTIGRAVITY\Avatar`.

La primera línea de la respuesta tiene que ser exactamente `INFORME_OPENCODE_14`.

Una sola corrida de la suite. No midas la base, el wal, el shm, la clave ni `screen_observation.png`. No fusiones a `main`. No toques `test_bot.py` ni `tools/telegram_notifier.py`. No regeneres la clave. No imprimas su contenido ni el de la base. No detengas ni habilites `AvatarWhatsApp247`. No declares `VERIFIED_WINDOWS` ni `VERIFIED_PC`. No mates procesos. No vuelvas a lanzar la suite si algo falla.

Si `git status` muestra algo más que esos dos archivos sin seguimiento, detente.

## Traer el cierre

```text
cd "b:\PROYECTOS ANTIGRAVITY\Avatar"
git status
git fetch origin cursor/spec-003-u1-u17-5763
git merge --ff-only origin/cursor/spec-003-u1-u17-5763
git rev-parse HEAD
git merge-base --is-ancestor 2f24f5af4b40d54c5694d3dfd3669192c9149ad7 HEAD
echo ANCESTRO:$LASTEXITCODE
```

`ANCESTRO` tiene que ser 0. Ese commit es documentación: la suite es la de `dce43a3`.

## Nombres de lo omitido

```text
python -m unittest discover -s tests -v > "$env:TEMP\avatar_suite_14.txt" 2>&1
echo EXIT:$LASTEXITCODE
Select-String -Path "$env:TEMP\avatar_suite_14.txt" -Pattern "skipped '"
Select-String -Path "$env:TEMP\avatar_suite_14.txt" -Pattern "^Ran |^OK|^FAILED"
```

Pega cada línea `skipped`, la línea `Ran`, la línea `OK` o `FAILED`, y `EXIT`. No pegues el resto del archivo. No dejes `avatar_suite_14.txt` dentro del repositorio.

En Linux, hoy, se omiten estas seis: las dos de pyautogui (`test_20_invalid_target_handling`, `test_25_safe_failure_without_blind_clicking`), `test_text_mode_corrupts_those_bytes`, `test_junction_that_leaves_the_scope_is_denied`, `test_alternate_data_stream_is_denied` y `test_short_name_on_a_real_volume_is_denied`. En Windows el informe 13 omitió dos. Di el nombre de esas dos y si las cuatro de `windows_only` y las dos de pyautogui salieron `ok` o `skipped`.
