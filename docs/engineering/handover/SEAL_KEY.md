# Clave del sello de requisitos

La clave vive junto a la base, en `<base>.seal_key`. Mide 32 bytes. Se lee y se escribe en binario (`os.O_BINARY` cuando el sistema lo tiene) para que 0x0A, 0x0D y 0x1A no cambien el archivo.

La clave del PC de Mauro mide 32 bytes. No hay migración.

Si el archivo existe y no mide 32 bytes, la carga falla con `SEAL_KEY_REJECTED` y el tamaño real. No se genera otra clave en silencio.

Regenerar es un comando del operador:

```
avatar seal-key regenerate --db RUTA_DE_LA_BASE --confirm
```

Sin `--confirm` no se escribe nada.

Consecuencias para el registro: los sellos v2 ya guardados en las misiones dejan de coincidir. Esas misiones salen `tampered` y no se marcan completas. El comando no reescribe las filas. Un proceso de Avatar que siga en marcha conserva la clave anterior en memoria: hay que reiniciarlo después.
