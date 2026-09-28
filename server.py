import os
import sys
import json
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict

# Asegurar path de Avatar
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import AvatarOrchestrator
from tools.shell_tool import ShellTool
from tools.file_tool import FileTool

app = FastAPI(title="Avatar AI GUI Backend", version="1.0.0")

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
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return "<h1>Avatar GUI Index no encontrado</h1>"

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
        
    with open(orchestrator.llm.config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        
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
    with open(orchestrator.llm.config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    
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
    raw_response = orchestrator.process_user_input(req.message)
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

@app.get("/api/projects")
def list_projects():
    base_dir = "b:/PROYECTOS ANTIGRAVITY"
    try:
        if os.path.exists(base_dir):
            items = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
            return {"projects": items}
        return {"projects": ["Avatar"]}
    except Exception as e:
        return {"projects": ["Avatar"], "error": str(e)}

@app.post("/api/workspace/set")
def set_active_workspace(req: WorkspaceRequest):
    target_path = os.path.join("b:/PROYECTOS ANTIGRAVITY", req.project_name)
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
