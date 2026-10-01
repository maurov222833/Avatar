# PARA_OPENCODE 2 — entregar dos documentos sin cambiarlos

Cursor no recibió el texto de estos archivos. Solo recibió la frase de que venían adjuntos. No los reconstruyas ni los resumas.

Nombres exactos:

- `AVATAR_ENGINEERING_SPEC_003_v2_COMPLETA.md`
- `AVATAR_SPEC_003_ADDENDUM_3_U18_DIRECTOR_DE_DESARROLLO.md`

## Dónde buscar

Solo en las carpetas de Mauro y en el repo de Avatar. No abras `C:\Windows` ni `System32`.

Si no aparecen con `where /r` sobre las carpetas de documentos y de proyectos, para y dilo. No inventes el contenido.

## Qué hacer si los encuentras

1. Copia cada archivo tal cual al Escritorio, con el mismo nombre. Esa copia es la que Mauro adjunta en Cursor. Misma cantidad de bytes. No corrijas títulos, ni tildes, ni espacios.
2. Calcula el SHA-256 de cada uno (`Get-FileHash -Algorithm SHA256`).
3. En el repo Avatar, commit solo si ya existe la rama `cursor/spec-003-u1-u17-5763`. Si no existe, no la crees desde `main`, no hagas merge y no hagas force-push. Deja las copias en el Escritorio y dilo en el informe.
4. Si la rama existe: copia cada archivo tal cual a `docs/engineering\`, sustituye en `docs/engineering\SPEC_HASHES.txt` la línea `ABSENT` de cada nombre por el hash y la ruta `docs/engineering/<nombre>` (no cambies el hash de `MASTER_DIRECTIVE_002.md`), cambia en `docs/engineering\INDEX.md` el estado `ABSENT` de esas dos filas a `En el repo`, commit en esa rama y push a `origin` con la credencial que ya tenga el PC. No pegues el token en el chat ni lo guardes en el repo.

No pegues el contenido de los documentos en el chat. No lo resumas.

## Qué devolver

La primera línea de tu respuesta tiene que ser exactamente `INFORME_OPENCODE_2`. Después:

- La ruta donde estaba cada archivo antes de copiarlo, o `NO_ENCONTRADO`.
- El SHA-256 de cada uno.
- La ruta de las dos copias en el Escritorio.
- La rama y el `HEAD` del repo Avatar.
- El hash del commit, o `SIN_COMMIT` si la rama no existía.
- Si el push llegó a GitHub o con qué error se detuvo.

Cursor commiteará esos bytes solo cuando pueda leerlos. Un push a GitHub no entra solo en la sesión de Cursor.
