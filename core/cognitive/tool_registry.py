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
        self.register_tool(ToolDefinition(
            name="WHATSAPP_STATUS",
            description="Estado real de la sesión de WhatsApp Web.",
            input_schema={},
            risk_level=RiskLevel.LOW,
            execution_mode="sync",
            timeout=120
        ))
        self.register_tool(ToolDefinition(
            name="WHATSAPP_READ",
            description="Lee mensajes de un chat de WhatsApp.",
            input_schema={"chat": "str", "limit": "str"},
            risk_level=RiskLevel.LOW,
            execution_mode="sync",
            timeout=180
        ))
        self.register_tool(ToolDefinition(
            name="WHATSAPP_SEND",
            description="Envía por navegador dedicado con verificación.",
            input_schema={"message": "str", "chat": "str"},
            risk_level=RiskLevel.MEDIUM,
            execution_mode="sync",
            timeout=180
        ))
        # Actos que ya ejecuta el chokepoint. El riesgo de aquí es etiqueta del
        # planificador; la política real sigue en ActPolicy (no cambia EXEC).
        for name, description, schema, risk in (
            ("AUDIO_CONTROL", "Pausa, reanuda, cambia o cierra la pestaña de música del navegador del sistema.",
             {"action": "str", "target": "str", "query": "str"}, RiskLevel.MEDIUM),
            ("SCREEN_CAPTURE", "Captura el escritorio.",
             {"output_path": "str"}, RiskLevel.LOW),
            ("UPDATE_CONFIG", "Actualiza una clave permitida de config.json.",
             {"key": "str", "value": "str"}, RiskLevel.HIGH),
            ("TELEGRAM_STATUS", "Estado del bot de Telegram.", {}, RiskLevel.LOW),
            ("TELEGRAM_SEND", "Envía un mensaje al chat allowlist.",
             {"chat_id": "str", "message": "str"}, RiskLevel.HIGH),
            ("TELEGRAM_TEST", "Prueba de ida y vuelta con Telegram.", {}, RiskLevel.MEDIUM),
            ("BROWSER_NAVIGATE", "Navega en el navegador Playwright.",
             {"url": "str"}, RiskLevel.MEDIUM),
            ("BROWSER_OBSERVE", "Lee la página Playwright activa.", {}, RiskLevel.LOW),
            ("BROWSER_CLICK", "Clic en un selector Playwright.",
             {"selector": "str"}, RiskLevel.MEDIUM),
            ("BROWSER_FILL", "Rellena un campo Playwright.",
             {"selector": "str", "value": "str"}, RiskLevel.MEDIUM),
            ("BROWSER_CLOSE", "Cierra la sesión Playwright.", {}, RiskLevel.LOW),
            ("DESKTOP_OBSERVE", "Observa el escritorio.",
             {"output_path": "str"}, RiskLevel.LOW),
            ("DESKTOP_CLICK", "Clic de escritorio. Sigue pidiendo aprobación EXEC.",
             {"target": "str"}, RiskLevel.HIGH),
            ("DESKTOP_TYPE", "Teclea en el escritorio. Sigue pidiendo aprobación EXEC.",
             {"text": "str"}, RiskLevel.HIGH),
            ("DESKTOP_HOTKEY", "Atajo de ventana allowlist (minimizar, escritorio). Sin aprobación EXEC.",
             {"action": "str", "target": "str"}, RiskLevel.MEDIUM),
        ):
            self.register_tool(ToolDefinition(
                name=name,
                description=description,
                input_schema=schema,
                risk_level=risk,
                execution_mode="sync",
                timeout=60,
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

    @classmethod
    def list_tools(cls) -> List[str]:
        """
        Nombres que el parser de texto y SAR pueden aceptar.

        Unión del registro cognitivo y de ACT_TYPES (chokepoint): una sola
        fuente para no mantener otra lista a mano en el orquestador.
        """
        names = set(default_tool_registry.list_registered_tools())
        try:
            from core.act_chokepoint import ACT_TYPES
            names.update(ACT_TYPES.keys())
        except Exception:
            pass
        return sorted(names)

# Instancia global por defecto
default_tool_registry = ToolRegistry()
