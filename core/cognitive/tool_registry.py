from typing import Dict, Optional, List, Any
from core.cognitive.models import ToolDefinition, RiskLevel

class ToolRegistry:
    """
    Registro formal y tipado de herramientas autorizadas en Avatar AI.
    """
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool(ToolDefinition(
            name="COMMAND",
            description="Ejecuta un comando en PowerShell sin ventana visible.",
            input_schema={"command": "str"},
            risk_level=RiskLevel.MEDIUM,
            execution_mode="sync",
            timeout=120
        ))
        self.register_tool(ToolDefinition(
            name="READ_FILE",
            description="Lee un archivo local.",
            input_schema={"file_path": "str"},
            risk_level=RiskLevel.LOW,
            execution_mode="sync",
            timeout=30
        ))
        self.register_tool(ToolDefinition(
            name="WRITE_FILE",
            description="Crea o modifica un archivo local.",
            input_schema={"file_path": "str", "content": "str"},
            risk_level=RiskLevel.HIGH,
            execution_mode="sync",
            timeout=30
        ))
        self.register_tool(ToolDefinition(
            name="LIST_DIR",
            description="Lista el contenido de un directorio.",
            input_schema={"dir_path": "str"},
            risk_level=RiskLevel.LOW,
            execution_mode="sync",
            timeout=30
        ))
        self.register_tool(ToolDefinition(
            name="WEB_SEARCH",
            description="Realiza búsquedas en internet.",
            input_schema={"query": "str"},
            risk_level=RiskLevel.LOW,
            execution_mode="sync",
            timeout=30
        ))
        self.register_tool(ToolDefinition(
            name="FETCH_URL",
            description="Descarga el contenido de una URL.",
            input_schema={"url": "str"},
            risk_level=RiskLevel.LOW,
            execution_mode="sync",
            timeout=30
        ))
        self.register_tool(ToolDefinition(
            name="PLAY_AUDIO",
            description="Reproduce un archivo o búsqueda de audio.",
            input_schema={"audio_source": "str"},
            risk_level=RiskLevel.LOW,
            execution_mode="sync",
            timeout=30
        ))
        self.register_tool(ToolDefinition(
            name="SEND_WHATSAPP",
            description="Envía un mensaje de texto por WhatsApp.",
            input_schema={"message": "str"},
            risk_level=RiskLevel.MEDIUM,
            execution_mode="sync",
            timeout=30
        ))

    def register_tool(self, tool_def: ToolDefinition):
        tool_def.validate()
        self._tools[tool_def.name] = tool_def

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def is_registered(self, name: str) -> bool:
        return name in self._tools

    def list_registered_tools(self) -> List[str]:
        return list(self._tools.keys())

# Instancia global por defecto
default_tool_registry = ToolRegistry()
