# Arreglos propuestos — suite Windows (informe OpenCode)

Comando, cuando estos commits estén en el PC:

```
cd "b:\PROYECTOS ANTIGRAVITY\Avatar"
git fetch origin cursor/spec-003-u1-u17-5763
git merge --ff-only origin/cursor/spec-003-u1-u17-5763
python -m unittest discover -s tests -q
```

Si `git status` no está limpio o el merge no es fast-forward, detente. No toques `test_bot.py` ni `tools/telegram_notifier.py`. No fusiones a `main`.

Resultado que esta sesión no puede firmar: los 20 de WinError 32 deberían bajar. Los 9 de AppData/TEMP, la tecla y A19 siguen fallando hasta aplicar lo de abajo. Si pasan, el estado de esos tres sigue `UNVERIFIED` hasta pegar el informe.

Fecha: 2026-10-02. No están aplicados. La suite de esta sesión no es Windows.

Conteo que llegó: 740 bien, 36 mal, 4 omitidas. De esos 36, este archivo cubre los que la orden pidió proponer y no corregir todavía: 9 de AppData/TEMP, 1 de tecla, 1 de A19. Los 20 de WinError 32 se cierran en código aparte. No vino el volcado de cada fallo; el motivo de abajo sale del código y de cómo Windows resuelve el temporal.

## AppData / TEMP (9)

`core/path_guard.py` trata `appdata` como almacén de secretos. En Windows, `tempfile.gettempdir()` suele ser `C:\Users\<usuario>\AppData\Local\Temp`. Una prueba que autoriza o escribe ahí cae en la denylist aunque el archivo sea solo de la prueba.

Arreglo propuesto: no abrir AppData. Las pruebas que esperan `Allow` crean su carpeta bajo el workspace del repo, no con el temporal del sistema. `AppData\Local\Temp` no se agrega a la allowlist: también guarda cachés de credenciales.

## Tecla (1)

`tests/test_spec003.py`, `test_hotkey_does_not_need_the_orchestrator`, afirma `os_hotkey_hook_available()` es falso. Esa función devuelve `os.name == "nt"`. En Windows la afirmación falla. El escuchador sigue sin instalarse: `start_hotkey_listener` responde `HOTKEY_LISTENER_OFF` o `HOTKEY_LISTENER_NOT_INSTALLED` y no importa `pynput` ni `keyboard`.

Arreglo propuesto: en Windows afirmar que el gancho no quedó importado ni registrado, no que el sistema operativo sea incapaz de tener uno. No instalar la tecla. El paso 2 sigue esperando una orden escrita.

## A19 (1)

`tests/test_authority_adversarial_003.py`, `test_A19_restart_does_not_preserve_a_valid_authorization`, abre un segundo `StateEngine` sobre el mismo archivo mientras el primero sigue vivo. Con WAL, en Windows esa segunda conexión puede no ver la fila o ver un estado distinto. No hay traceback en este mensaje, así que no se tocó la prueba: cambiarla a ciegas puede debilitar la autoridad.

Arreglo propuesto, cuando llegue la traza: hacer checkpoint del primer motor y cerrarlo antes de abrir el segundo; la afirmación sigue siendo que el estado no es terminal. Si la traza dice otra cosa, se sigue esa traza y no este supuesto.
