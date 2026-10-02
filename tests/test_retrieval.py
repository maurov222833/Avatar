"""Búsqueda de memoria: palabras partidas y fichas de conocimiento vigentes."""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rag_memory import RAGMemory
from core.state_db import StateEngine


class RetrievalTests(unittest.TestCase):
    def test_hyphenated_topic_matches_the_word(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            db = stack.enter_context(contextlib.closing(StateEngine(os.path.join(tmp, "s.db"))))
            mem = RAGMemory(memory_dir=tmp, state_db=db)
            mem.save_knowledge("canal-24-7", "El candado del perfil se renueva solo.")
            hit = mem.search_knowledge("canal")
            self.assertIn("candado", hit)

    def test_valid_expertise_is_found_and_expired_is_not(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            db = stack.enter_context(contextlib.closing(StateEngine(os.path.join(tmp, "s.db"))))
            mem = RAGMemory(memory_dir=tmp, state_db=db)
            with open(os.path.join(tmp, "expertise.json"), "w", encoding="utf-8") as handle:
                json.dump([
                    {
                        "domain": "envio",
                        "fact": "El plazo de despacho se cuenta en dias habiles.",
                        "review_by": "2099-01-01",
                        "state": "VALIDATED",
                    },
                    {
                        "domain": "envio",
                        "fact": "La tarifa vieja ya no se usa.",
                        "review_by": "2000-01-01",
                        "state": "VALIDATED",
                    },
                ], handle)
            hit = mem.search_knowledge("plazo de despacho")
            self.assertIn("dias habiles", hit)
            self.assertNotIn("tarifa vieja", hit)

    def test_expertise_alone_is_searchable(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            db = stack.enter_context(contextlib.closing(StateEngine(os.path.join(tmp, "s.db"))))
            mem = RAGMemory(memory_dir=tmp, state_db=db)
            with open(os.path.join(tmp, "expertise.json"), "w", encoding="utf-8") as handle:
                json.dump([{
                    "domain": "proveedor",
                    "fact": "Solo se pide a un proveedor de la lista aprobada.",
                    "review_by": "2099-01-01",
                    "state": "VALIDATED",
                }], handle)
            hit = mem.search_knowledge("proveedor aprobada")
            self.assertIn("lista aprobada", hit)


if __name__ == "__main__":
    unittest.main()
