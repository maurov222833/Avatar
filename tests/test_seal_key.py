"""La clave de sello se lee y se escribe en binario.

0x0A, 0x0D y 0x1A tienen que sobrevivir. Una clave de otro tamaño falla
cerrada y no se regenera sola.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from core.state_db import (
    StateEngine,
    _O_BINARY,
    _read_binary,
    _write_binary_exclusive,
    regenerate_seal_key,
    regenerate_seal_key_cli,
)
from tests.scratch_dir import work_dir


def _control_key() -> bytes:
    key = bytearray(range(32))
    key[0] = 0x0A
    key[1] = 0x0D
    key[2] = 0x1A
    key[31] = 0x0A
    return bytes(key)


class SealKeyBinaryTests(unittest.TestCase):
    def setUp(self):
        self.dir = work_dir("seal_")
        self.db = os.path.join(self.dir, "state.db")

    def test_roundtrip_keeps_lf_cr_and_ctrl_z(self):
        key = _control_key()
        with mock.patch("core.state_db.secrets.token_bytes", return_value=key):
            engine = StateEngine(db_path=self.db)
            try:
                loaded = engine._load_seal_key()
            finally:
                engine.close()
        self.assertEqual(loaded, key)
        self.assertEqual(len(loaded), 32)
        self.assertEqual(_read_binary(self.db + ".seal_key"), key)
        self.assertIn(b"\x0a", loaded)
        self.assertIn(b"\x0d", loaded)
        self.assertIn(b"\x1a", loaded)

    def test_binary_flag_is_set_when_the_os_defines_it(self):
        if hasattr(os, "O_BINARY"):
            self.assertEqual(_O_BINARY, os.O_BINARY)
            self.assertNotEqual(_O_BINARY, 0)
        else:
            self.assertEqual(_O_BINARY, 0)

    def test_deformed_key_fails_closed_and_names_the_size(self):
        path = self.db + ".seal_key"
        _write_binary_exclusive(path, b"\x0a\x0d\x1a" + b"x" * 31)
        engine = StateEngine(db_path=self.db)
        try:
            with self.assertRaises(ValueError) as caught:
                engine._load_seal_key()
        finally:
            engine.close()
        message = str(caught.exception)
        self.assertIn("SEAL_KEY_REJECTED", message)
        self.assertIn("size=34", message)
        self.assertEqual(len(_read_binary(path)), 34)
        again = StateEngine(db_path=self.db)
        try:
            with self.assertRaises(ValueError):
                again._load_seal_key()
        finally:
            again.close()
        self.assertEqual(len(_read_binary(path)), 34)

    def test_regenerate_needs_confirm_and_old_seals_stop_matching(self):
        engine = StateEngine(db_path=self.db)
        try:
            mission = engine.create_mission(
                mission_id="msn-seal",
                raw_prompt="probe",
                declare_no_requirements=True,
            )
            old = engine._load_seal_key()
            self.assertEqual(engine.requirements_seal_state(engine.get_mission(mission)), "intact")
        finally:
            engine.close()
        self.assertEqual(regenerate_seal_key_cli(["--db", self.db]), 2)
        self.assertEqual(_read_binary(self.db + ".seal_key"), old)
        path = regenerate_seal_key(self.db)
        self.assertEqual(path, self.db + ".seal_key")
        fresh = StateEngine(db_path=self.db)
        try:
            self.assertEqual(len(fresh._load_seal_key()), 32)
            self.assertNotEqual(fresh._load_seal_key(), old)
            self.assertEqual(
                fresh.requirements_seal_state(fresh.get_mission(mission)),
                "tampered",
            )
        finally:
            fresh.close()

    @unittest.skipUnless(os.name == "nt", "windows_only: el modo texto traduce 0x0A y corta en 0x1A.")
    def test_text_mode_corrupts_those_bytes(self):
        path = os.path.join(self.dir, "text.bin")
        payload = bytes([0x41, 0x0A, 0x42, 0x0D, 0x43, 0x1A, 0x44])
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        with open(path, "r", encoding="latin-1") as handle:
            text = handle.read()
        self.assertNotEqual(text.encode("latin-1"), payload)


if __name__ == "__main__":
    unittest.main()
