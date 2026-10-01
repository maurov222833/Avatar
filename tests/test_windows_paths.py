"""Rutas que solo un volumen Windows puede demostrar.

En Linux se omiten con motivo windows_only. No cuentan como VERIFIED_WINDOWS.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

from core.path_guard import authorize_path


def _windows(reason: str):
    if os.name != "nt":
        raise unittest.SkipTest(f"windows_only: {reason}")


class WindowsPathTests(unittest.TestCase):
    def test_short_name_with_extension_is_denied_on_any_system(self):
        decision, reason = authorize_path(r"C:\NOMBRE~1.TXT", "write", tempfile.mkdtemp())
        self.assertEqual(decision, "DENY")
        self.assertEqual(reason, "PATH_SHORT_NAME_8_3")

    def test_junction_that_leaves_the_scope_is_denied(self):
        _windows("un junction NTFS no existe en Linux.")
        scope = tempfile.mkdtemp()
        outside = tempfile.mkdtemp()
        link = os.path.join(scope, "salto")
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link, outside],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            self.skipTest("windows_only: mklink /J no pudo crear el junction. Sigue UNVERIFIED.")
        decision, reason = authorize_path(os.path.join(link, "nota.txt"), "write", scope)
        self.assertEqual(decision, "DENY", reason)

    def test_alternate_data_stream_is_denied(self):
        _windows("un alternate data stream es de NTFS.")
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "nota.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("visible")
        stream = path + ":oculto"
        try:
            with open(stream, "w", encoding="utf-8") as handle:
                handle.write("oculto")
        except OSError as exc:
            self.skipTest(f"windows_only: no se pudo crear el ADS ({exc}). Sigue UNVERIFIED.")
        decision, reason = authorize_path(stream, "read", folder)
        self.assertEqual(decision, "DENY")
        self.assertEqual(reason, "PATH_ALTERNATE_DATA_STREAM")

    def test_short_name_on_a_real_volume_is_denied(self):
        _windows("el nombre 8.3 se comprueba sobre un archivo real de NTFS.")
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "nombre-largo-de-prueba.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x")
        probe = subprocess.run(
            ["cmd", "/c", "dir", "/x", folder],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0 or "~" not in probe.stdout:
            self.skipTest("windows_only: dir /x no mostró un nombre 8.3. Sigue UNVERIFIED.")
        decision, reason = authorize_path(os.path.join(folder, "NOMBRE~1.TXT"), "write", folder)
        self.assertEqual(decision, "DENY")
        self.assertEqual(reason, "PATH_SHORT_NAME_8_3")


if __name__ == "__main__":
    unittest.main()
