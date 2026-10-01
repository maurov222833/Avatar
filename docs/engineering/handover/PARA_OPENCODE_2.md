# PARA_OPENCODE 2 — entregar dos documentos sin cambiarlos

Cursor no recibió el texto de estos archivos. Solo recibió la frase de que venían adjuntos. No los reconstruyas ni los resumas.

Nombres exactos:

- `AVATAR_ENGINEERING_SPEC_003_v2_COMPLETA.md`
- `AVATAR_SPEC_003_ADDENDUM_3_U18_DIRECTOR_DE_DESARROLLO.md`

## Dónde buscar

Solo en las carpetas de Mauro y en el repo de Avatar. No abras `C:\Windows` ni `System32`.

Si no aparecen con `where /r` sobre las carpetas de documentos y de proyectos, para y dilo. No inventes el contenido.

## Qué hacer si los encuentras

1. Copia cada archivo tal cual a `docs/engineering\` del repo Avatar. Misma cantidad de bytes. No corrijas títulos, ni tildes, ni espacios.
2. Calcula el SHA-256 de cada uno (`Get-FileHash -Algorithm SHA256`).
3. En `docs/engineering\SPEC_HASHES.txt`, sustituye la línea `ABSENT` de cada nombre por el hash y la ruta `docs/engineering/<nombre>`. No cambies el hash de `MASTER_DIRECTIVE_002.md`.
4. En `docs/engineering\INDEX.md`, cambia el estado `ABSENT` de esas dos filas a `En el repo`.
5. Commit en la rama `cursor/spec-003-u1-u17-5763`. No hagas merge a `main`. No hagas force-push.
6. Push a `origin` con la credencial que ya tenga el PC. No pegues el token en el chat ni lo guardes en el repo.

## Segunda copia, para que Cursor los lea

El push deja los archivos en GitHub. Esta sesión de Cursor no tiene credencial para hacer fetch, así que el push no los trae aquí.

Después del commit, copia los dos archivos otra vez, sin cambiar un byte, al Escritorio de Mauro, con los mismos nombres. Mauro los adjunta en el siguiente mensaje de Cursor. El SHA-256 del Escritorio tiene que ser el mismo que el del commit.

No pegues el contenido en el chat de OpenCode. No lo resumas.

## Qué devolver

- La ruta donde estaba cada archivo antes de copiarlo.
- El SHA-256 de cada uno.
- El hash del commit.
- Si el push llegó a GitHub o con qué error se detuvo.
- La ruta de las dos copias en el Escritorio.

Cursor commiteará esos bytes solo cuando pueda leerlos. Un push a GitHub no entra solo en la sesión de Cursor.
