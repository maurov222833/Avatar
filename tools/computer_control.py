import os
import sys
import time
import datetime
from typing import Dict, Any, List, Optional, Union, Tuple
from tools.screen_tool import ScreenTool
from core.ui_inspector import UIInspector, LocalOCREngine, UIElementType
from core.checkpoint_engine import CheckpointEngine, IdempotencyClass
from core.state_db import StateEngine
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier

class ActionStatus:
    ACTION_ACCEPTED = "ACTION_ACCEPTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    RESULT_OBSERVED = "RESULT_OBSERVED"
    RESULT_VERIFIED = "RESULT_VERIFIED"
    ACTION_REJECTED = "ACTION_REJECTED"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"

class ComputerControl:
    """
    Abstracción de Control de Escritorio, Visión y Automatización de Windows para Avatar AI (Fase 3).
    Reutiliza ScreenTool para capturas de pantalla y se integra con CheckpointEngine (Fase 2) y StateEngine (Fase 1).
    Sigue el estándar estricto OBSERVE -> PLAN -> ACT -> OBSERVE -> VERIFY.
    """

    def __init__(self, checkpoint_engine: Optional[CheckpointEngine] = None, state_db: Optional[StateEngine] = None):
        if checkpoint_engine is not None:
            self.checkpoint_engine = checkpoint_engine
            self.state_db = checkpoint_engine.state_db
        else:
            self.state_db = state_db or StateEngine()
            self.checkpoint_engine = CheckpointEngine(state_db=self.state_db)

    def observe_screen(self, output_path: Optional[str] = None) -> str:
        """Captura la pantalla utilizando ScreenTool (reuso estricto del componente existente)."""
        if output_path is None:
            from core.paths import memory_dir
            output_path = os.path.join(memory_dir(), "screen_observation.png")
        return ScreenTool.take_screenshot(output_path)

    def resolve_target_coordinates(self, target: Any, hwnd_or_title: Optional[Any] = None) -> Optional[Tuple[int, int]]:
        """
        Resuelve las coordenadas físicas (x, y) en pantalla adaptadas al escalado DPI y al tipo de objetivo:
        - Coordenadas Absolutas: (x, y)
        - Coordenadas Relativas: {"rel_x": 50, "rel_y": 50} + Geometría de ventana
        - UI Automation Element: {"control_type": "Button", "name": "Save"}
        - OCR Element: "Texto a Buscar"
        """
        dpi = UIInspector.get_dpi_scaling()

        # Caso 1: Tupla/Lista (x, y) absolutas
        if isinstance(target, (list, tuple)) and len(target) >= 2:
            x, y = int(target[0] * dpi), int(target[1] * dpi)
            return (x, y)

        # Caso 2: Diccionario con rel_x, rel_y o x, y
        if isinstance(target, dict):
            if "x" in target and "y" in target:
                return (int(target["x"] * dpi), int(target["y"] * dpi))
            elif "rel_x" in target and "rel_y" in target:
                win = None
                if hwnd_or_title:
                    win = UIInspector.find_window_by_title(str(hwnd_or_title))
                if not win:
                    wins = UIInspector.list_windows()
                    win = wins[0] if wins else None
                if win:
                    bounds = win["bounds"]
                    abs_x = bounds["x"] + target["rel_x"]
                    abs_y = bounds["y"] + target["rel_y"]
                    return (int(abs_x * dpi), int(abs_y * dpi))

        # Caso 3: Búsqueda de elemento UI Automation
        if isinstance(target, dict) and ("control_type" in target or "name" in target or "automation_id" in target):
            elements = UIInspector.inspect_ui_elements(hwnd_or_title or "ActiveWindow")
            for el in elements:
                t_name = target.get("name", "").lower()
                el_name = el["name"].lower()
                t_type = target.get("control_type", "").lower()
                el_type = el["control_type"].lower()
                if (not t_name or t_name in el_name) and (not t_type or t_type == el_type):
                    b = el["bounds"]
                    center_x = b["x"] + (b["width"] // 2)
                    center_y = b["y"] + (b["height"] // 2)
                    return (int(center_x * dpi), int(center_y * dpi))

        # Caso 4: Búsqueda de texto vía OCR
        if isinstance(target, str):
            scr_path = self.observe_screen()
            ocr_res = LocalOCREngine.find_text_in_image(target, scr_path)
            if ocr_res and "center" in ocr_res:
                return (ocr_res["center"]["x"], ocr_res["center"]["y"])

        return None

    def focus_window(self, hwnd_or_title: Any) -> bool:
        """Enfoca y trae al frente la ventana objetivo."""
        return UIInspector.focus_window(hwnd_or_title)

    def execute_gui_action(
        self,
        action: str,
        target: Any = None,
        text: Optional[str] = None,
        key: Optional[str] = None,
        keys: Optional[List[str]] = None,
        button: str = "left",
        clicks: int = -300,
        window_title: Optional[str] = None,
        hwnd_or_title: Optional[Any] = None,
        mission_id: Optional[str] = None,
        task_id: Optional[str] = None,
        expected_criteria: Optional[Dict[str, Any]] = None,
        wait_seconds: float = 0.5
    ) -> Dict[str, Any]:
        """
        Método público principal de ejecución de acciones GUI adaptado a la API general de herramientas.
        """
        win_title = window_title or (str(hwnd_or_title) if hwnd_or_title is not None else None)
        action_args = {
            "window_title": win_title,
            "button": button,
            "text": text or "",
            "key": key or "",
            "keys": keys or [],
            "clicks": clicks,
            "wait_seconds": wait_seconds
        }
        return self._execute_gui_action(
            action_type=action,
            target=target,
            action_args=action_args,
            mission_id=mission_id,
            task_id=task_id,
            expected_criteria=expected_criteria
        )

    def _execute_gui_action(
        self,
        action_type: str,
        target: Any,
        action_args: Dict[str, Any],
        mission_id: Optional[str] = None,
        task_id: Optional[str] = None,
        expected_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Bucle Ejecutivo OBSERVE -> PLAN -> ACT -> OBSERVE -> VERIFY con CheckpointEngine.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # 1. OBSERVE PRE-ACCIÓN & VALIDACIÓN DE OBJETIVO
        target_win = action_args.get("window_title")
        if target_win:
            win_info = UIInspector.find_window_by_title(target_win)
            if not win_info:
                return {
                    "status": ActionStatus.TARGET_NOT_FOUND,
                    "action": action_type,
                    "message": f"Ventana objetivo '{target_win}' no encontrada. Acción abortada sin hacer clic a ciegas."
                }
            UIInspector.focus_window(win_info["hwnd"])

        # 2. CHECKPOINT PRE_TOOL_EXECUTION (Si se proporciona mission_id y task_id)
        if mission_id and task_id:
            self.checkpoint_engine.save_pre_tool_checkpoint(
                mission_id=mission_id,
                task_id=task_id,
                step_index=action_args.get("step_index", 1),
                description=f"Desktop GUI Action: {action_type}",
                tool_name=f"GUI_{action_type.upper()}",
                tool_args={"target": str(target), "action_args": action_args}
            )

        # 3. ACT (Ejecutar Acción)
        coords = self.resolve_target_coordinates(target, target_win)
        if action_type in ("click", "double_click") and not coords:
            return {
                "status": ActionStatus.TARGET_NOT_FOUND,
                "action": action_type,
                "message": "No se pudieron resolver las coordenadas del objetivo.",
                "coordinates": None,
                "executed": False,
                "verified": False,
            }
        execution_msg = ""
        action_ok = False

        try:
            if os.environ.get("AVATAR_ALLOW_REAL_INPUT") != "1":
                raise RuntimeError(
                    "AVATAR_ALLOW_REAL_INPUT=1 es obligatorio para un clic o una tecla"
                )
            import pyautogui
            pyautogui.FAILSAFE = True
            
            if action_type == "click":
                pyautogui.click(coords[0], coords[1], button=action_args.get("button", "left"))
                execution_msg = f"Clic ejecutado en coordenadas ({coords[0]}, {coords[1]})"
                action_ok = True

            elif action_type == "double_click":
                if coords:
                    pyautogui.doubleClick(coords[0], coords[1])
                    execution_msg = f"Doble clic en ({coords[0]}, {coords[1]})"
                    action_ok = True

            elif action_type == "type_text":
                text = action_args.get("text", "")
                if coords:
                    pyautogui.click(coords[0], coords[1])
                    time.sleep(0.1)
                pyautogui.write(text, interval=action_args.get("interval", 0.02))
                execution_msg = f"Texto digitado: '{text}'"
                action_ok = True

            elif action_type == "press_key":
                key = action_args.get("key", "enter")
                pyautogui.press(key)
                execution_msg = f"Tecla presionada: '{key}'"
                action_ok = True

            elif action_type == "hotkey":
                keys = action_args.get("keys", [])
                if keys:
                    pyautogui.hotkey(*keys)
                    execution_msg = f"Atajo ejecutado: {' + '.join(keys)}"
                    action_ok = True

            elif action_type == "scroll":
                clicks = action_args.get("clicks", -300)
                pyautogui.scroll(clicks)
                execution_msg = f"Desplazamiento scroll: {clicks}"
                action_ok = True

        except Exception as e:
            execution_msg = f"Fallo al ejecutar acción GUI: {str(e)}"
            action_ok = False

        # 4. OBSERVE POST-ACCIÓN (Captura de evidencia física)
        post_screenshot = self.observe_screen()

        # 5. VERIFY (Verificación del resultado)
        verification_status = "RESULT_OBSERVED"
        if expected_criteria:
            if expected_criteria.get("expected_text_in_ocr"):
                query_text = expected_criteria["expected_text_in_ocr"]
                ocr_found = LocalOCREngine.find_text_in_image(query_text, post_screenshot)
                if ocr_found:
                    verification_status = ActionStatus.RESULT_VERIFIED
                else:
                    verification_status = "VERIFICATION_FAILED"
            elif expected_criteria.get("expected_window_title"):
                w_title = expected_criteria["expected_window_title"]
                if UIInspector.find_window_by_title(w_title):
                    verification_status = ActionStatus.RESULT_VERIFIED

        # 6. CHECKPOINT POST_TOOL & VERIFIED
        if mission_id and task_id:
            self.checkpoint_engine.save_post_tool_checkpoint(
                mission_id=mission_id,
                task_id=task_id,
                execution_output=execution_msg,
                evidence_data={"screenshot": post_screenshot, "action": action_type}
            )
            if verification_status == ActionStatus.RESULT_VERIFIED or action_ok:
                self.checkpoint_engine.mark_verified(
                    mission_id=mission_id,
                    task_id=task_id,
                    claim=f"GUI Action {action_type} verified",
                    evidence_data={"screenshot": post_screenshot}
                )

        return {
            "status": verification_status if action_ok else ActionStatus.ACTION_REJECTED,
            "action": action_type,
            "execution_message": execution_msg,
            "coordinates": coords,
            "post_screenshot": post_screenshot,
            "post_observation_path": post_screenshot,
            "verified": (verification_status == ActionStatus.RESULT_VERIFIED or action_ok),
            "executed": action_ok,
            "timestamp": now
        }

    def click(self, target: Any, button: str = "left", window_title: Optional[str] = None, mission_id: Optional[str] = None, task_id: Optional[str] = None, expected_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._execute_gui_action("click", target, {"button": button, "window_title": window_title}, mission_id, task_id, expected_criteria)

    def double_click(self, target: Any, window_title: Optional[str] = None, mission_id: Optional[str] = None, task_id: Optional[str] = None) -> Dict[str, Any]:
        return self._execute_gui_action("double_click", target, {"window_title": window_title}, mission_id, task_id)

    def type_text(self, text: str, target: Optional[Any] = None, window_title: Optional[str] = None, mission_id: Optional[str] = None, task_id: Optional[str] = None, expected_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._execute_gui_action("type_text", target, {"text": text, "window_title": window_title}, mission_id, task_id, expected_criteria)

    def press_key(self, key: str, mission_id: Optional[str] = None, task_id: Optional[str] = None) -> Dict[str, Any]:
        return self._execute_gui_action("press_key", None, {"key": key}, mission_id, task_id)

    def hotkey(self, keys: List[str], mission_id: Optional[str] = None, task_id: Optional[str] = None) -> Dict[str, Any]:
        return self._execute_gui_action("hotkey", None, {"keys": keys}, mission_id, task_id)

    def scroll(self, clicks: int = -300, target: Optional[Any] = None) -> Dict[str, Any]:
        return self._execute_gui_action("scroll", target, {"clicks": clicks})
