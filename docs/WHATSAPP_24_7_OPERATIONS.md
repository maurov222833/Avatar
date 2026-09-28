# WhatsApp 24/7 — Manual de operaciones y reinstalación

Objetivo: Mauro habla con Avatar a cualquier hora desde su auto-chat de WhatsApp;
Avatar lee, ejecuta con el orquestador completo y responde en el mismo chat.

## 1. Arquitectura (qué pieza hace qué)

```
Teléfono de Mauro ──QR una vez──▶ Chromium persistente (memory/whatsapp_profile)
                                        │  bridges/whatsapp_reader.py
                                        │  lee DOM + envía con relectura
                                        ▼
                              WhatsAppBridge.start_live_bridge()
                              (dedup, autorizados, observe, límites)
                                        │  llama a:
                                        ▼
                              AvatarOrchestrator.process_user_input()
                                        │  responde texto
                                        ▼
                              chokepoint.perform(SEND_WHATSAPP)
                              (política + ledger + executor = lector DOM)
                                        ▼
                              mismo chat (verificado por relectura)
whatsapp_24x7.py = supervisor: navegador fresco por ciclo, backoff ante caídas,
                   espera ante QR expirado, heartbeat, stop-file.
Task Scheduler "AvatarWhatsApp247" = arranca el supervisor al iniciar sesión.
```

## 2. Instalación desde cero (checklist)

1. Requisitos: Windows con sesión interactiva (el navegador es headed), Python +
   `pip install -r requirements.txt` (incluye playwright + chromium),
   teléfono con WhatsApp.
2. Copiar `config.example.json` → `config.json` y `.env.example` → `.env`;
   rellenar `GROQ_API_KEY` (o Gemini) — nunca versionar estos archivos.
3. `python whatsapp_24x7.py --once` (humo: 2 polls).
4. Vincular sesión: arrancar el runner; escanear el QR **una vez** (perfil persistente).
5. Activar envío en `config.json`: `"autonomy": {"dry_run": false,
   "allow_external_messages": true}`. Sin esto, todo se DENIEGA (correcto).
6. Fijar `whatsapp.target_chat`: OJO — el nombre del teléfono y el de Web
   difieren. El auto-chat en Web aparece como el **número** (+57 319 4408824),
   no como "Mauro Vanegas 2025". El buscador solo matchea dígitos parciales
   (el "+" rompe el match); el lector ya maneja esto (cola de 8 dígitos).
7. Registrar tarea: PowerShell **admin** →
   `powershell -ExecutionPolicy Bypass -File Install-AvatarWhatsApp247.ps1`
8. Probar ida y vuelta con un mensaje etiquetado; verificar relectura + ledger.

## 3. Operación diaria

- Logs: `%TEMP%\opencode\wa_live.log` (corridas manuales) / salida de la tarea.
- Heartbeat: `memory/whatsapp_heartbeat.json` (ts, polls, processed, replied).
- Ledger: tabla `acts` (`SEND_WHATSAPP` con `policy_reason`; `OBSERVED` solo con
  `[READBACK_VERIFIED]`).
- Parada limpia: crear `memory\AVATAR_WA_STOP` (el loop termina solo).
- Cursor anti-duplicados: `memory/whatsapp_bridge_state.json` (no borrar a la
  ligera: re-respondería mensajes viejos).
- Si el teléfono se desvincula: el supervisor avisa `QR_REQUIRED` y reintenta
  cada 5 min hasta re-escanear.

## 4. Troubleshooting (todo lo que ya dolió, con su fix)

| Síntoma | Causa real | Fix aplicado / acción |
|---|---|---|
| "Auditoría y análisis procesados correctamente" en loop | Fallback plantilla ante proveedor mudo | Respaldo ejecutivo con estado real (`orchestrator._build_executive_fallback`) |
| Bloque 📌 huérfano con volcado de 60 líneas | Vacío + filler + dump sin recorte | `provider_empty`, corte al 2º vacío, truncado 40 líneas |
| `IndentationError` en `whatsapp_bridge.py` raíz | WRITE_FILE truncado por 400 | Eliminado; el bridge vive en `bridges/` |
| Envío "exitoso" que nunca llegó | Executor ventana-activa + policy DENIED no mostrada | Envío DOM con relectura; denegación visible |
| `SEARCH_CODE` / 400 tool-call | Modelo inventa tools / JSON truncado | Reintento guiado acotado (`llm_provider`) |
| `search box no encontrado` | La píldora crea el input solo al clic | Reveal + espera 30s (`open_chat`) |
| Chat "Mauro Vanegas 2025" inexistente en Web | Teléfono y Web nombran distinto | Buscar por dígitos; verificación de cabecera → `CHAT_NOT_FOUND` honesto |
| Envío no aparece como saliente | Comparación con emoji/espacios del DOM | Huella `_text_key` (alfanumérica) |
| Loop colgado sin logs | `close()` headed colgado / doble lock de perfil | `close()` con watchdog + kill solo de este perfil; navegador compartido |
| Tests que fallan al activar envío | Tests atados al default DENY | Política explícita en cada test (herméticos) |
| Eco infinito (responder a lo propio) | Auto-chat llega como saliente | `sent_texts` + `respond_to_own_outgoing` |
| Silencio del proveedor enviado al chat | Respuesta de escalado como reply | `SILENCE_MARKERS`: se salta el envío, avanza cursor |

## 5. Seguridad (no negociable)

- Envío exige opt-in (`allow_external_messages`); cada intento queda en `acts`.
- `respond_to_own_outgoing` solo para auto-chat; en chats ajenos, solo entrantes.
- `max_replies` y `authorized_senders` como frenos; `stop-file` como kill-switch.
- Claves solo en `config.json`/`.env` locales (gitignored); el repo trae plantillas.
- El lector nunca ejecuta instrucciones del chat como código: el texto web es
  UNTRUSTED y lo interpreta el orquestador con política.
