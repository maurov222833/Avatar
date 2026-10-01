# PARA_OPENCODE 1 — rutas de Windows

Ejecutor: OpenCode, en el PC de Mauro, dentro de la carpeta del repo Avatar. No abras `C:\Windows` ni `System32` para escribir. No instales la tecla global. No bajes `exec_requires_approval`.

La copia tiene que incluir `tests/test_windows_paths.py` (commit posterior a `339d2c5` cuando Mauro lo traiga). Si el archivo no está, no inventes el test: para y dilo.

## Comando

```text
python -m unittest tests.test_windows_paths -v
```

## Resultado esperado en Windows

Tres pruebas, ninguna omitida:

| Prueba | Esperado | Evidencia si pasa |
|---|---|---|
| `test_junction_that_leaves_the_scope_is_denied` | `DENY` al escribir a través de un junction que sale de la carpeta de la misión | `VERIFIED_WINDOWS` de ese caso |
| `test_alternate_data_stream_is_denied` | `DENY` y motivo `PATH_ALTERNATE_DATA_STREAM` | `VERIFIED_WINDOWS` de ese caso |
| `test_short_name_on_a_real_volume_is_denied` | `DENY` y motivo `PATH_SHORT_NAME_8_3` | `VERIFIED_WINDOWS` de ese caso |

Si `mklink`, el ADS o `dir /x` no pueden correr, la prueba se omite. Una omisión **no** es `VERIFIED_WINDOWS`. El estado sigue `UNVERIFIED`.

## Resultado esperado en Linux

Las tres se omiten con el motivo `windows_only: ...`. Eso no verifica Windows.

## Qué devolver

El texto completo de `python -m unittest tests.test_windows_paths -v`, el código de salida, y si alguna prueba se omitió, la línea del motivo.
