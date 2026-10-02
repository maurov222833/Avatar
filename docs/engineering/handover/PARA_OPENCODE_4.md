# Suite en Windows — después del arreglo de la clave y de las pruebas

Comando:

```
cd "b:\PROYECTOS ANTIGRAVITY\Avatar"
git status
git fetch origin cursor/spec-003-u1-u17-5763
git merge --ff-only origin/cursor/spec-003-u1-u17-5763
python -m unittest discover -s tests -q
```

Si `git status` no está limpio o el merge no es fast-forward, detente. No toques `test_bot.py` ni `tools/telegram_notifier.py`. No fusiones a `main`. No regeneres la clave de sello: la del PC mide 32 bytes.

Qué debería bajar respecto de los 11 que quedaban en `0699e0f`:

- Las pruebas que esperaban permitir una ruta ya no usan el Temp del sistema. Escriben en `.test_scratch/` dentro del repo. `appdata` sigue prohibido.
- La afirmación de la tecla ya no pide que Windows sea incapaz de tener un gancho. Pide que Avatar no haya registrado un escuchador.
- La clave de sello se lee y se escribe en binario. Un archivo que no mida 32 bytes falla con `SEAL_KEY_REJECTED` y el tamaño. No se crea otra clave sola.

Qué no se reescribió: `test_A19_restart_does_not_preserve_a_valid_authorization`. Si sigue fallando, pega el traceback. No se cierra el primer motor a ciegas.

`tests/test_seal_key.py` tiene una prueba `windows_only` del modo texto. En Windows no debe omitirse. En Linux sí.

La tecla global no se instala. No hay AST de PowerShell.
