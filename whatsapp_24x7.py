"""
Avatar WhatsApp 24/7 — runner persistente con supervisor.

Mantiene el puente vivo día y noche:
  - Cada ciclo usa un navegador fresco (evita pudrimiento de estado) y lo cierra
    con watchdog al terminar.
  - Si el ciclo muere (excepción/cuelgue), espera con backoff y reintenta.
  - Si la sesión QR expiró, NO cuenta como fallo: avisa y reintenta cada 5 min
    hasta que el dueño re-escanee.
  - Heartbeat en memory/whatsapp_heartbeat.json para monitoreo externo.
  - Parada limpia creando memory/AVATAR_WA_STOP.

Uso:
    python whatsapp_24x7.py            # infinito hasta stop-file o Ctrl+C
    python whatsapp_24x7.py --once     # un solo ciclo (diagnóstico)

Config (config.json -> bloque "whatsapp", todo opcional):
    target_chat, poll_seconds, max_replies_por_ciclo(0=ilimitado),
    autostart_live (solo aplica al daemon de la GUI, no a este runner).
"""
import json
import os
import sys
import time
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

HEARTBEAT_PATH = os.path.join(BASE_DIR, "memory", "whatsapp_heartbeat.json")
STOP_PATH = os.path.join(BASE_DIR, "memory", "AVATAR_WA_STOP")
# Primer reintento rápido (calle): 15s; luego se espacía hasta 15 min.
BACKOFFS = [15, 60, 300, 900]
QR_RETRY_S = 300


def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [24x7] {msg}", flush=True)


def load_whatsapp_config():
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("whatsapp", {}) or {}
    except Exception:
        return {}


def write_heartbeat(status, stats=None, note=""):
    try:
        os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
        with open(HEARTBEAT_PATH, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(),
                       "ts_human": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "status": status,
                       "stats": stats or {},
                       "note": note}, f)
    except Exception as exc:
        log(f"heartbeat fallido: {exc}")


def beat(stats):
    write_heartbeat("RUNNING", dict(stats))


def run_cycle(cfg, max_polls=0):
    """Un ciclo completo: navegador fresco -> loop hasta fallo/parada. Devuelve motivo."""
    from bridges.whatsapp_bridge import WhatsAppBridge, WhatsAppReadError
    from bridges.whatsapp_reader import WhatsAppWebReader

    target = cfg.get("target_chat", "Mauro Vanegas 2025")
    reader = WhatsAppWebReader(
        profile_dir=os.path.join(BASE_DIR, "memory", "whatsapp_profile"))
    bridge = WhatsAppBridge(
        poll_seconds=int(cfg.get("poll_seconds", 8)),
        max_replies=None,  # ilimitado; el supervisor manda
        respond_to_own_outgoing=bool(cfg.get("respond_to_own_outgoing", True)),
        authorized_senders=cfg.get("authorized_senders"),
        observe_only=False,
        reader=reader,
    )
    try:
        summary = bridge.start_live_bridge(
            target, max_polls=max_polls, heartbeat_cb=beat, stop_path=STOP_PATH)
        return ("STOP", f"loop terminó: {summary}")
    except WhatsAppReadError as exc:
        if exc.code == WhatsAppReadError.LOGIN_REQUIRED_QR:
            return ("QR", "sesión expirada: re-escanea el QR")
        return ("FAIL", f"{exc.code}: {exc.detail}")
    finally:
        try:
            reader.close()
        except Exception:
            pass


def supervise(once=False):
    cfg = load_whatsapp_config()
    log(f"config whatsapp: target={cfg.get('target_chat', '(defecto)')}")
    failures = 0
    while True:
        if os.path.exists(STOP_PATH):
            log("stop-file presente al arrancar; salgo sin iniciar.")
            write_heartbeat("STOPPED", note="stop-file")
            return
        write_heartbeat("STARTING_CYCLE")
        try:
            outcome, note = run_cycle(cfg, max_polls=(2 if once else 0))
        except Exception:
            outcome, note = "FAIL", traceback.format_exc(limit=3).replace("\n", " | ")
        if outcome == "STOP":
            log(note)
            write_heartbeat("STOPPED", note=note)
            return
        if outcome == "QR":
            log(f"ALERTA: {note}. Reintento en {QR_RETRY_S}s (avisa al dueño).")
            write_heartbeat("QR_REQUIRED", note=note)
            time.sleep(QR_RETRY_S)
            continue
        failures += 1
        wait = BACKOFFS[min(failures - 1, len(BACKOFFS) - 1)]
        log(f"ciclo caído ({note}). Reintento #{failures} en {wait}s.")
        write_heartbeat("BACKOFF", note=f"{note} | reintento en {wait}s")
        if once:
            return
        time.sleep(wait)


if __name__ == "__main__":
    once = "--once" in sys.argv[1:]
    _logf = open(os.path.join(BASE_DIR, "memory", "whatsapp_24x7.log"),
                 "a", encoding="utf-8")

    class _Tee:
        def __init__(self, *streams):
            self.streams = streams

        def write(self, data):
            for s in self.streams:
                try:
                    s.write(data)
                except Exception:
                    pass

        def flush(self):
            for s in self.streams:
                try:
                    s.flush()
                except Exception:
                    pass

    sys.stdout = _Tee(sys.stdout, _logf)
    sys.stderr = sys.stdout
    log("arranque 24/7" + (" (una vez)" if once else ""))
    try:
        supervise(once=once)
    except KeyboardInterrupt:
        log("interrumpido por teclado.")
        write_heartbeat("STOPPED", note="KeyboardInterrupt")
