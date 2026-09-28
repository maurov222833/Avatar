"""
Loop vivo de WhatsApp: lógica determinista con lector simulado.

No toca WhatsApp real, no usa LLM (process_user_input se sustituye por eco).
Prueba: dedup, remitentes, modo observe, denegación por política, errores honestos.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridges.whatsapp_bridge import WhatsAppBridge
from bridges.whatsapp_reader import WhatsAppMessage, WhatsAppReadError
from core.act_chokepoint import ActStatus


class _TempWorld:
    def __init__(self):
        import tempfile as _t
        self.dir = _t.mkdtemp(prefix="avatar_wa_")
        self._e = None
        self._r = None

    def __enter__(self):
        import core.state_db as sd
        import core.rag_memory as rm
        self._e = sd.StateEngine.__init__
        self._r = rm.RAGMemory.__init__
        world = self

        def engine_init(self, db_path=None, *a, **k):
            return world._e(self, os.path.join(world.dir, "state_engine.db")
                            if db_path is None else db_path)

        def rag_init(self, memory_dir=None, state_db=None, *a, **k):
            return world._r(self, memory_dir or world.dir, state_db)

        sd.StateEngine.__init__ = engine_init
        rm.RAGMemory.__init__ = rag_init
        return self

    def __exit__(self, *exc):
        import core.state_db as sd
        import core.rag_memory as rm
        import shutil
        sd.StateEngine.__init__ = self._e
        rm.RAGMemory.__init__ = self._r
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


class FakeReader:
    """Lector programado: cada read_recent devuelve el siguiente guion."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0
        self.sent = []
        self.sent_texts = set()
        self.launched = False

    def launch(self):
        self.launched = True

    def login_state(self):
        return "LOGGED_IN"

    def open_chat(self, name):
        self.chat = name

    def read_recent(self, limit=10):
        self.calls += 1
        if not self.scripts:
            return []
        item = self.scripts.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def send_text(self, text):
        self.sent.append(text)
        self.sent_texts.add(" ".join(text.split()))
        return "verificado"

    def close(self):
        pass


def _msg(mid, sender, text, incoming=True):
    return WhatsAppMessage(msg_id=mid, incoming=incoming, sender=sender, text=text)


def _bridge(reader, **kw):
    tmp = tempfile.mkdtemp(prefix="avatar_wa_state_")
    b = WhatsAppBridge(reader=reader, poll_seconds=0,
                       state_path=os.path.join(tmp, "state.json"), **kw)
    b.orchestrator.process_user_input = lambda text: f"eco: {text}"
    return b


class TestLiveLoop(unittest.TestCase):

    def test_new_message_processed_once_dedup_on_second_poll(self):
        with _TempWorld():
            reader = FakeReader([
                [_msg("m1", "Mauro", "hola")],
                [_msg("m1", "Mauro", "hola")],
            ])
            b = _bridge(reader)
            calls = []
            orig_process = b.orchestrator.process_user_input
            b.orchestrator.process_user_input = lambda m: calls.append(m) or "ok"
            b._deliver = lambda **k: "delivered"
            summary = b.start_live_bridge("Chat Prueba", max_polls=2)
            self.assertEqual(len(calls), 1, "el mismo mensaje no se reprocesa")
            self.assertEqual(summary["processed"], 1)

    def test_unauthorized_sender_skipped(self):
        with _TempWorld():
            reader = FakeReader([[ _msg("m2", "Desconocido", "haz esto") ]])
            b = _bridge(reader, authorized_senders=["Mauro"])
            calls = []
            b.orchestrator.process_user_input = lambda m: calls.append(m) or "ok"
            b._deliver = lambda **k: "delivered"
            b.start_live_bridge("Chat Prueba", max_polls=1)
            self.assertEqual(calls, [])

    def test_observe_only_reads_without_processing(self):
        with _TempWorld():
            reader = FakeReader([[ _msg("m3", "Mauro", "solo mira") ]])
            b = _bridge(reader, observe_only=True)
            calls = []
            b.orchestrator.process_user_input = lambda m: calls.append(m) or "ok"
            b.start_live_bridge("Chat Prueba", max_polls=1)
            self.assertEqual(calls, [])
            self.assertIn("m3", b._replied_ids)

    def test_denied_send_is_recorded_and_cursor_advances(self):
        """Sin consentimiento: el envío se DENIEGA, queda registrado, no se reintenta."""
        with _TempWorld():
            reader = FakeReader([
                [_msg("m4", "Mauro", "salúdame")],
                [_msg("m4", "Mauro", "salúdame")],
            ])
            b = _bridge(reader)  # usa el path real: eco + chokepoint
            # Denegación hermética: no depende del config de la máquina.
            b.orchestrator.chokepoint.policy.allow_external_messages = False
            b.orchestrator.chokepoint.policy.dry_run = True
            summary = b.start_live_bridge("Chat Prueba", max_polls=2)
            self.assertEqual(summary["processed"], 1)
            acts = b.orchestrator.chokepoint.list_acts()
            sends = [a for a in acts if a["act_type"] == "SEND_WHATSAPP"]
            self.assertTrue(sends, "el intento debe quedar registrado")
            self.assertEqual(sends[-1]["status"], ActStatus.DENIED)
            self.assertIn("EXTERNAL_EFFECT", sends[-1]["policy_reason"])
            self.assertEqual(reader.sent, [], "denegado = nada enviado")

    def test_reader_error_does_not_kill_loop(self):
        with _TempWorld():
            reader = FakeReader([
                WhatsAppReadError(WhatsAppReadError.DOM_UNRECOGNIZED, "boom"),
                [_msg("m5", "Mauro", "tras el error")],
            ])
            b = _bridge(reader)
            calls = []
            b.orchestrator.process_user_input = lambda m: calls.append(m) or "ok"
            b._deliver = lambda **k: "delivered"
            summary = b.start_live_bridge("Chat Prueba", max_polls=2)
            self.assertEqual(len(calls), 1)

    def test_qr_required_raises_honestly(self):
        with _TempWorld():
            reader = FakeReader([])
            reader.login_state = lambda: "QR_REQUIRED"
            b = _bridge(reader)
            with self.assertRaises(WhatsAppReadError) as ctx:
                b.start_live_bridge("Chat Prueba", max_polls=1)
            self.assertEqual(ctx.exception.code, WhatsAppReadError.LOGIN_REQUIRED_QR)

    def test_provider_silence_skips_delivery_but_advances(self):
        """El silencio del proveedor no se envía al chat; el cursor avanza igual."""
        with _TempWorld():
            reader = FakeReader([[ _msg("m6", "Mauro", "hola?") ]])
            b = _bridge(reader)
            b.orchestrator.process_user_input = lambda t: (
                "⚠️ El proveedor devolvió respuestas vacías 2 veces seguidas.")
            delivered = []
            b._deliver = lambda **k: delivered.append(k) or "skip"
            summary = b.start_live_bridge("Chat Prueba", max_polls=1)
            self.assertEqual(delivered, [])
            self.assertIn("m6", b._replied_ids)
            self.assertEqual(summary["processed"], 1)

    def test_own_outgoing_processed_in_self_chat_but_not_own_echo(self):
        """Auto-chat: lo de Mauro (saliente) se procesa; el eco propio no."""
        with _TempWorld():
            reader = FakeReader([[ _msg("m7", "?", "enciende la luz", incoming=False) ]])
            b = _bridge(reader, respond_to_own_outgoing=True)
            calls = []
            b.orchestrator.process_user_input = lambda m: calls.append(m) or "ok"
            b._deliver = lambda **k: reader.sent_texts.add(" ".join("ok".split())) or "d"
            b.start_live_bridge("Chat Prueba", max_polls=1)
            self.assertEqual(calls, ["enciende la luz"])

    def test_own_outgoing_ignored_by_default(self):
        with _TempWorld():
            reader = FakeReader([[ _msg("m8", "?", "ruido", incoming=False) ]])
            b = _bridge(reader)  # respond_to_own_outgoing=False
            calls = []
            b.orchestrator.process_user_input = lambda m: calls.append(m) or "ok"
            b.start_live_bridge("Chat Prueba", max_polls=1)
            self.assertEqual(calls, [])

    def test_max_replies_none_means_unlimited(self):
        with _TempWorld():
            reader = FakeReader([[ _msg("a1", "M", "uno") ], [ _msg("a2", "M", "dos") ]])
            b = _bridge(reader, max_replies=None)
            n = []
            b.orchestrator.process_user_input = lambda m: n.append(m) or "ok"
            b._deliver = lambda **k: "d"
            summary = b.start_live_bridge("Chat Prueba", max_polls=2)
            self.assertEqual(n, ["uno", "dos"])

    def test_stop_file_breaks_loop_cleanly(self):
        import tempfile as _t
        with _TempWorld():
            d = _t.mkdtemp(prefix="avatar_wa_stop_")
            stop = os.path.join(d, "AVATAR_WA_STOP")
            open(stop, "w").close()
            reader = FakeReader([[ _msg("s1", "M", "nunca") ]])
            b = _bridge(reader)
            calls = []
            b.orchestrator.process_user_input = lambda m: calls.append(m) or "ok"
            summary = b.start_live_bridge("Chat Prueba", max_polls=5,
                                          stop_path=stop)
            self.assertEqual(summary["polls"], 0)
            self.assertEqual(calls, [])

    def test_heartbeat_called_each_poll(self):
        with _TempWorld():
            reader = FakeReader([[], []])
            b = _bridge(reader)
            beats = []
            b.start_live_bridge("Chat Prueba", max_polls=2,
                                heartbeat_cb=lambda s: beats.append(s["polls"]))
            self.assertEqual(beats, [1, 2])

    def test_readback_verified_marks_observation(self):
        """El observer honra [READBACK_VERIFIED]; sin marca sigue no-verificado."""
        from core.act_chokepoint import _observe_external_message
        ok = _observe_external_message(
            {}, "[READBACK_VERIFIED] Mensaje enviado y verificado por relectura.")
        self.assertTrue(ok["verified"])
        self.assertTrue(ok["delivery_confirmed"])
        plain = _observe_external_message({}, "pegado y enviado a la ventana activa")
        self.assertFalse(plain["verified"])
        self.assertFalse(plain["delivery_confirmed"])


    def test_text_key_ignores_emoji_and_spacing(self):
        """El DOM altera emojis/espacios: la huella debe igualar igual."""
        from bridges.whatsapp_reader import _text_key
        sent = _text_key("🔧 Prueba de envío Avatar — ignórame")
        seen = _text_key(" Prueba de envío Avatar — ignórame.")
        self.assertTrue(sent)
        self.assertIn(sent[:40], seen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
