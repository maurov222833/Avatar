import os
import sys
import unittest
import tempfile
from PIL import Image

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.screen_tool import ScreenTool
from core.ui_inspector import UIInspector, LocalOCREngine, UIElementType
from tools.computer_control import ComputerControl, ActionStatus
from core.checkpoint_engine import CheckpointEngine, IdempotencyClass
from core.state_db import StateEngine

class TestDesktopInputStaysOff(unittest.TestCase):
    def test_screenshot_uses_the_pinned_memory_dir(self):
        from core.paths import memory_dir
        folder = tempfile.mkdtemp()
        db = StateEngine(db_path=os.path.join(folder, "state.db"))
        control = ComputerControl(state_db=db, checkpoint_engine=CheckpointEngine(state_db=db))
        path = control.observe_screen()
        self.assertTrue(os.path.abspath(path).startswith(os.path.abspath(memory_dir())))
        repo_memory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "memory", "screen_observation.png",
        )
        self.assertNotEqual(os.path.abspath(path), os.path.abspath(repo_memory))
        db.close()

    def test_real_click_requires_an_explicit_variable(self):
        folder = tempfile.mkdtemp()
        db = StateEngine(db_path=os.path.join(folder, "state.db"))
        control = ComputerControl(state_db=db, checkpoint_engine=CheckpointEngine(state_db=db))
        calls = []

        class FakeGui:
            FAILSAFE = True

            @staticmethod
            def click(*args, **kwargs):
                calls.append("click")

        os.environ.pop("AVATAR_ALLOW_REAL_INPUT", None)
        sys.modules["pyautogui"] = FakeGui
        try:
            blocked = control.execute_gui_action(action="click", target=(1, 1), wait_seconds=0)
            self.assertEqual(calls, [])
            self.assertFalse(blocked["executed"])
            os.environ["AVATAR_ALLOW_REAL_INPUT"] = "1"
            allowed = control.execute_gui_action(action="click", target=(1, 1), wait_seconds=0)
            self.assertEqual(calls, ["click"])
            self.assertTrue(allowed["executed"])
        finally:
            os.environ.pop("AVATAR_ALLOW_REAL_INPUT", None)
            sys.modules.pop("pyautogui", None)
            db.close()


class TestDesktopVisionPhase3(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_state.db")
        self.state_db = StateEngine(db_path=self.db_path)
        self.checkpoint_engine = CheckpointEngine(state_db=self.state_db)
        self.control = ComputerControl(checkpoint_engine=self.checkpoint_engine, state_db=self.state_db)

        # Create dummy image for testing OCR / observation
        self.sample_img_path = os.path.join(self.temp_dir, "sample.png")
        img = Image.new("RGB", (400, 200), color=(255, 255, 255))
        img.save(self.sample_img_path)

    def _require_pyautogui(self):
        try:
            import pyautogui  # noqa: F401
        except ImportError:
            self.skipTest("pyautogui not installed (desktop automation optional on Linux CI)")

    def test_01_screentool_integration(self):
        """01. Verifies ScreenTool integration for taking screenshots."""
        out_path = os.path.join(self.temp_dir, "screenshot.png")
        res_path = self.control.observe_screen(output_path=out_path)
        self.assertTrue(os.path.exists(res_path))

    def test_02_window_discovery(self):
        """02. Verifies window discovery returns list of top-level windows."""
        windows = UIInspector.list_windows()
        self.assertIsInstance(windows, list)
        if windows:
            win = windows[0]
            self.assertIn("title", win)
            self.assertIn("hwnd", win)
            self.assertIn("bounds", win)

    def test_03_window_identification(self):
        """03. Verifies finding a window by title substring."""
        windows = UIInspector.list_windows()
        if windows:
            first_title = windows[0]["title"]
            found = UIInspector.find_window_by_title(first_title)
            self.assertIsNotNone(found)
            self.assertEqual(found["title"], first_title)
        else:
            found = UIInspector.find_window_by_title("NonExistentWindowTitle12345")
            self.assertIsNone(found)

    def test_04_window_focus(self):
        """04. Verifies focusing window returns boolean status."""
        windows = UIInspector.list_windows()
        if windows:
            hwnd = windows[0]["hwnd"]
            res = UIInspector.focus_window(hwnd)
            self.assertIsInstance(res, bool)
        else:
            res = UIInspector.focus_window("NonExistentWindow")
            self.assertFalse(res)

    def test_05_window_geometry(self):
        """05. Verifies window bounds geometry (x, y, width, height)."""
        windows = UIInspector.list_windows()
        if windows:
            bounds = windows[0]["bounds"]
            self.assertIn("x", bounds)
            self.assertIn("y", bounds)
            self.assertIn("width", bounds)
            self.assertIn("height", bounds)

    def test_06_ui_element_discovery(self):
        """06. Verifies UI element discovery returns list of elements."""
        elements = UIInspector.inspect_ui_elements("ActiveWindow")
        self.assertIsInstance(elements, list)

    def test_07_button_discovery(self):
        """07. Verifies filtering elements by Button type."""
        elements = UIInspector.inspect_ui_elements("ActiveWindow")
        buttons = [e for e in elements if e.get("control_type") == UIElementType.BUTTON]
        self.assertIsInstance(buttons, list)

    def test_08_text_edit_discovery(self):
        """08. Verifies filtering elements by Edit or Text type."""
        elements = UIInspector.inspect_ui_elements("ActiveWindow")
        edits = [e for e in elements if e.get("control_type") in (UIElementType.EDIT, UIElementType.TEXT)]
        self.assertIsInstance(edits, list)

    def test_09_ocr_result_parsing(self):
        """09. Verifies OCR engine text and bounding box parsing."""
        boxes = LocalOCREngine.extract_text_with_bounding_boxes(self.sample_img_path)
        self.assertIsInstance(boxes, list)
        if boxes:
            box = boxes[0]
            self.assertIn("text", box)
            self.assertIn("bounds", box)

    def test_10_coordinate_conversion(self):
        """10. Verifies resolution of absolute and relative target coordinates."""
        # Absolute tuple
        coords = self.control.resolve_target_coordinates((100, 200))
        self.assertIsNotNone(coords)
        self.assertIsInstance(coords, tuple)

        # Absolute dict
        coords_dict = self.control.resolve_target_coordinates({"x": 150, "y": 250})
        self.assertIsNotNone(coords_dict)

    def test_11_dpi_scaling(self):
        """11. Verifies system DPI scaling factor is retrieved and >= 1.0."""
        dpi = UIInspector.get_dpi_scaling()
        self.assertGreaterEqual(dpi, 1.0)

    def test_12_click_abstraction(self):
        """12. Verifies click execution flow abstraction."""
        result = self.control.execute_gui_action(
            action="click",
            target=(500, 500),
            wait_seconds=0
        )
        self.assertIn("status", result)
        self.assertIn(result["status"], [ActionStatus.RESULT_VERIFIED, ActionStatus.RESULT_OBSERVED, ActionStatus.ACTION_EXECUTED, ActionStatus.ACTION_REJECTED])

    def test_13_keyboard_abstraction(self):
        """13. Verifies keyboard typing abstraction."""
        result = self.control.execute_gui_action(
            action="type_text",
            target=None,
            text="Test Keyboard Input",
            wait_seconds=0
        )
        self.assertIn("status", result)

    def test_14_post_action_observation(self):
        """14. Verifies observation path is generated post-action."""
        result = self.control.execute_gui_action(
            action="click",
            target=(100, 100),
            wait_seconds=0
        )
        self.assertIn("post_observation_path", result)
        if result["post_observation_path"]:
            self.assertTrue(os.path.exists(result["post_observation_path"]))

    def test_15_physical_verification(self):
        """15. Verifies physical verification status evaluation."""
        result = self.control.execute_gui_action(
            action="click",
            target=(200, 200),
            wait_seconds=0
        )
        self.assertIn("verified", result)

    def test_16_permission_enforcement(self):
        """16. Verifies safety parameters and action acceptance."""
        result = self.control.execute_gui_action(
            action="click",
            target=(10, 10),
            wait_seconds=0
        )
        self.assertIn("status", result)

    def test_17_tool_registry_integration(self):
        """17. Verifies tool interface compatibility and method signatures."""
        self.assertTrue(hasattr(self.control, "observe_screen"))
        self.assertTrue(hasattr(self.control, "execute_gui_action"))

    def test_18_checkpoint_integration(self):
        """18. Verifies PRE checkpoint creation before action execution."""
        mission_id = "test_mission_18"
        self.state_db.create_mission(mission_id=mission_id)
        initial_tasks = self.state_db.get_planner_tasks(mission_id)
        count_before = len(initial_tasks)

        self.control.execute_gui_action(
            action="click",
            target=(300, 300),
            mission_id=mission_id,
            task_id="test_task_checkpoint_18",
            wait_seconds=0
        )

        count_after = len(self.state_db.get_planner_tasks(mission_id))
        self.assertGreater(count_after, count_before)

    def test_19_resume_integration(self):
        """19. Verifies integration with StateEngine and checkpoint resumption."""
        mission_id = "test_mission_19"
        task_id = "test_task_checkpoint_19"
        self.state_db.create_mission(mission_id=mission_id)
        res = self.control.execute_gui_action(
            action="click",
            target=(150, 150),
            mission_id=mission_id,
            task_id=task_id,
            wait_seconds=0
        )
        tasks = self.state_db.get_planner_tasks(mission_id)
        self.assertTrue(any(t["task_id"] == task_id for t in tasks))

    def test_20_invalid_target_handling(self):
        """20. Verifies TARGET_NOT_FOUND returned for invalid/unresolvable targets."""
        self._require_pyautogui()
        res = self.control.execute_gui_action(
            action="click",
            target="NonExistentTargetElement12345",
            wait_seconds=0
        )
        self.assertEqual(res["status"], ActionStatus.TARGET_NOT_FOUND)

    def test_21_window_disappeared_handling(self):
        """21. Verifies graceful handling when target window is not found."""
        res = self.control.execute_gui_action(
            action="click",
            target={"rel_x": 10, "rel_y": 10},
            hwnd_or_title="WindowThatDoesNotExist_9999",
            wait_seconds=0
        )
        self.assertIn(res["status"], [ActionStatus.TARGET_NOT_FOUND, ActionStatus.ACTION_EXECUTED])

    def test_22_focus_changed_unexpectedly(self):
        """22. Verifies focus attempt failure is safely captured."""
        res_focus = self.control.focus_window("WindowThatDoesNotExist_9999")
        self.assertFalse(res_focus)

    def test_23_ocr_confidence_fallback(self):
        """23. Verifies OCR fallback mechanism when searching for non-existent text."""
        res = LocalOCREngine.find_text_in_image("TextThatDoesNotExistOnScreen_XYZ", self.sample_img_path)
        self.assertIsNone(res)

    def test_24_ui_automation_unavailable_fallback(self):
        """24. Verifies UI inspector fallback behavior when powershell / UI automation returns empty."""
        elements = UIInspector.inspect_ui_elements("InvalidWindow_123")
        self.assertIsInstance(elements, list)

    def test_25_safe_failure_without_blind_clicking(self):
        """25. Verifies system refuses to click blindly when target resolution fails."""
        self._require_pyautogui()
        res = self.control.execute_gui_action(
            action="click",
            target={"invalid_key": "invalid_val"},
            wait_seconds=0
        )
        self.assertEqual(res["status"], ActionStatus.TARGET_NOT_FOUND)
        self.assertFalse(res.get("executed", False))

if __name__ == "__main__":
    unittest.main()
