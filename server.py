import hashlib
import hmac
import os
import secrets
import sys
import json
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict

# Asegurar path de Avatar
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import AvatarOrchestrator
from tools.shell_tool import ShellTool
from tools.file_tool import FileTool
from core.paths import config_path as resolve_config_path, projects_base

app = FastAPI(title="Avatar AI GUI Backend", version="1.0.0")

# A browser page on another origin must not be able to drive this API. The GUI is served by
# this process and receives the token in its own HTML; every /api call has to send it back.
# Host/Origin stay on loopback names so a DNS-rebinding page is rejected before the token matters.
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "testserver", "[::1]"}
http_token = os.environ.get("AVATAR_HTTP_TOKEN", "").strip() or secrets.token_urlsafe(32)


def auth_headers() -> Dict[str, str]:
    return {"X-Avatar-Token": http_token}


def _host_name(value: str) -> str:
    """Return the host, without a numeric port. Anything else is returned unchanged so it fails closed."""
    text = (value or "").strip().lower()
    if text.startswith("["):
        end = text.find("]")
        if end == -1:
            return text
        rest = text[end + 1:]
        if rest and not (rest.startswith(":") and rest[1:].isdigit()):
            return text
        return text[:end + 1]
    name, sep, port = text.partition(":")
    if sep and not port.isdigit():
        return text
    return name


def _token_matches(presented: str) -> bool:
    # Hash both sides so a length mismatch cannot raise or short-circuit early.
    return hmac.compare_digest(
        hashlib.sha256((presented or "").encode("utf-8")).digest(),
        hashlib.sha256(http_token.encode("utf-8")).digest())


@app.middleware("http")
async def local_http_guard(request: Request, call_next):
    if _host_name(request.headers.get("host", "")) not in _LOCAL_HOSTS:
        return JSONResponse({"detail": "HOST_NOT_ALLOWED"}, status_code=403)
    origin = request.headers.get("origin")
    if origin:
        origin_host = ""
        if "://" in origin:
            origin_host = _host_name(origin.split("://", 1)[1].split("/", 1)[0])
        if origin_host not in _LOCAL_HOSTS:
            return JSONResponse({"detail": "ORIGIN_NOT_ALLOWED"}, status_code=403)
    if request.url.path.startswith("/api/") and not _token_matches(request.headers.get("x-avatar-token", "")):
        return JSONResponse({"detail": "HTTP_TOKEN_REQUIRED"}, status_code=401)
    return await call_next(request)

# Instancia del Orquestador
orchestrator = AvatarOrchestrator()

# ----------------------------------------------------------------------
# Secret redaction
# ----------------------------------------------------------------------
# `/api/config` returns the provider configuration. The raw file holds `api_key` entries, so
# returning it verbatim would hand credentials to any process that can reach this port. Keys
# are replaced with a presence marker; the client can see WHICH provider is configured without
# ever seeing the value.
_SECRET_KEYS = ("key", "token", "secret", "password")


def redact_secrets(obj):
    """Return a copy of `obj` with any secret-looking leaf replaced by a presence marker."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(t in str(k).lower() for t in _SECRET_KEYS) and isinstance(v, str):
                out[k] = f"***set({len(v)} chars)***" if v else ""
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(v) for v in obj]
    return obj


# Rutas de archivos estáticos para la GUI
gui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui")
app.mount("/static", StaticFiles(directory=gui_dir), name="static")

class ChatRequest(BaseModel):
    message: str

class ModelChangeRequest(BaseModel):
    provider: str

class ConfigUpdateRequest(BaseModel):
    gemini_key: Optional[str] = None
    openai_key: Optional[str] = None
    groq_key: Optional[str] = None
    github_key: Optional[str] = None
    ollama_url: Optional[str] = None

class CommandRequest(BaseModel):
    command: str

class WorkspaceRequest(BaseModel):
    project_name: str

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join(gui_dir, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>Avatar GUI Index no encontrado</h1>")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    # json.dumps makes the token a quoted JS string, so it cannot break out of the script.
    tag = "<script>window.AVATAR_HTTP_TOKEN = " + json.dumps(http_token) + ";</script>"
    if "</head>" in html:
        html = html.replace("</head>", tag + "\n</head>", 1)
    else:
        html = tag + html
    return HTMLResponse(html)

@app.get("/api/config")
def get_config():
    orchestrator.llm.load_config(force=True)
    return redact_secrets(orchestrator.llm.config)

@app.get("/api/config/health")
def get_provider_health():
    orchestrator.llm.load_config(force=True)
    return orchestrator.llm.get_health_report()


@app.post("/api/config/update")
def update_config(req: ConfigUpdateRequest):
    cfg = orchestrator.llm.config
    if req.gemini_key is not None:
        cfg.setdefault("gemini", {})["api_key"] = req.gemini_key.strip()
    if req.openai_key is not None:
        cfg.setdefault("openai", {})["api_key"] = req.openai_key.strip()
    if req.groq_key is not None:
        cfg.setdefault("groq", {})["api_key"] = req.groq_key.strip()
    if req.github_key is not None:
        cfg.setdefault("github", {})["api_key"] = req.github_key.strip()
    if req.ollama_url is not None:
        cfg.setdefault("ollama", {})["url"] = req.ollama_url.strip()
        
    with open(resolve_config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    orchestrator.llm.config_path = resolve_config_path()
        
    orchestrator.llm.load_config(force=True)
    # Nunca devolver secretos en claro: /api/config los redacta y este endpoint debe igualarlo.
    return {"status": "success", "config": redact_secrets(cfg)}

@app.post("/api/config/provider")
def set_provider(req: ModelChangeRequest):
    provider = req.provider.lower().strip()
    allowed = ["gemini", "groq", "github", "openai", "lmstudio", "ollama"]
    if provider not in allowed:
        raise HTTPException(status_code=400, detail=f"Proveedor inválido. Opciones: {allowed}")
    
    cfg = orchestrator.llm.config
    cfg["default_provider"] = provider
    with open(resolve_config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    orchestrator.llm.config_path = resolve_config_path()
    
    orchestrator.llm.load_config(force=True)
    return {"status": "success", "active_provider": provider}

@app.post("/api/chat")
def chat_with_avatar(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    
    try:
        response = orchestrator.process_user_input(req.message)
    except Exception as e:
        print(f"[ERROR /api/chat]: {e}")
        import traceback
        traceback.print_exc()
        response = f"⚠️ Ocurrió un error al procesar tu solicitud: {str(e)}"

    active_provider = orchestrator.llm.config.get("default_provider", "gemini")
    
    return {
        "user_message": req.message,
        "avatar_response": response,
        "provider": active_provider
    }

class WhatsAppWebhookRequest(BaseModel):
    sender: str
    message: str

@app.post("/api/whatsapp/webhook")
def whatsapp_webhook(req: WhatsAppWebhookRequest):
    if not req.message.strip():
        return {"status": "ignored", "reason": "empty message"}
    
    print(f"\n💬 [Mensaje Entrante de WhatsApp - {req.sender}]: {req.message}")
    raw_response = orchestrator.process_user_input(req.message, channel="remote")
    from tools.reasoning_engine import ReasoningEngine
    clean_response = ReasoningEngine.extract_clean_response(raw_response)
    
    return {
        "status": "success",
        "sender": req.sender,
        "user_message": req.message,
        "avatar_response": clean_response
    }

@app.post("/api/terminal/execute")
def execute_terminal_command(req: CommandRequest):
    """
    Execute a shell command on behalf of the GUI terminal.

    Routed through the act chokepoint like every other side effect, so it is policy-checked,
    bound to a mission and recorded in the act ledger. Previously this called
    `ShellTool.execute_command` directly, which meant an unauthenticated HTTP request could
    run arbitrary PowerShell with no policy, no record and no workspace guard.
    """
    if orchestrator.chokepoint is None:
        orchestrator.chokepoint = orchestrator._build_chokepoint()
    output = orchestrator.chokepoint.perform(
        act_type="COMMAND",
        args={"command": req.command},
        mission_id="gui-terminal",
        task_id="gui-terminal-task",
        execution_id=f"gui-exec-{uuid.uuid4().hex[:8]}",
    )
    return {"command": req.command, "output": output}

class MissionResumeRequest(BaseModel):
    mission_id: str
@app.post("/api/missions/resume")
def resume_mission(req: MissionResumeRequest):
    """
    Continue an interrupted mission from its persisted checkpoints.

    Previously the ResumeEngine had no runtime caller, so interrupted work could only
    restart from zero. Resumed task execution goes through the orchestrator's chokepoint
    dispatcher, hence policy-checked and recorded.
    """
    if not req.mission_id.strip():
        raise HTTPException(status_code=400, detail="mission_id no puede estar vacío.")
    try:
        result = orchestrator.resume_mission(req.mission_id.strip())
    except Exception as e:
        print(f"[ERROR /api/missions/resume]: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    return result

@app.get("/api/whatsapp/status")
def whatsapp_status():
    """
    Estado del puente 24/7: heartbeat del supervisor + últimos acts + modo.
    Solo lectura. Permite saber si el puente vive sin tener que hablarle.
    """
    heartbeat = {}
    try:
        hb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "memory", "whatsapp_heartbeat.json")
        if os.path.exists(hb_path):
            with open(hb_path, "r", encoding="utf-8") as f:
                heartbeat = json.load(f)
    except Exception:
        heartbeat = {"status": "UNKNOWN"}
    recent = []
    try:
        if orchestrator.chokepoint is not None:
            for a in orchestrator.chokepoint.list_acts()[-5:]:
                recent.append({"act_type": a["act_type"], "status": a["status"],
                               "created_at": a.get("created_at", "")})
    except Exception:
        pass
    return {"heartbeat": heartbeat, "recent_acts": recent,
            "mode": orchestrator.operating_mode().get("mode", "?")}

@app.get("/api/projects")
def list_projects():
    base_dir = projects_base()
    try:
        if os.path.exists(base_dir):
            items = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
            return {"projects": items}
        return {"projects": ["Avatar"]}
    except Exception as e:
        return {"projects": ["Avatar"], "error": str(e)}

@app.post("/api/workspace/set")
def set_active_workspace(req: WorkspaceRequest):
    target_path = os.path.join(projects_base(), req.project_name)
    if os.path.exists(target_path):
        return {"status": "success", "workspace": target_path, "project": req.project_name}
    return {"status": "warning", "message": f"Carpeta {req.project_name} no encontrada, usando workspace actual."}

@app.post("/api/attach")
async def attach_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text_content = content.decode("utf-8", errors="ignore")
        return {
            "filename": file.filename,
            "content_snippet": text_content[:500],
            "full_content": text_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer archivo: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
