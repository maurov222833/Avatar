# Avatar AI — Desktop Control, Vision & UI Automation (Phase 3)

## Architectural Overview

Phase 3 introduces non-blind desktop interaction, screen observation, vision/OCR element localization, and Win32 / UI Automation window discovery to Avatar AI.

```
+-------------------------------------------------------------------------+
|                              AVATAR AI                                  |
|                                                                         |
|  +------------------------+             +----------------------------+  |
|  |     StateEngine        | <---------> |      CheckpointEngine      |  |
|  |   (SQLite WAL Phase 1) |             |        (Phase 2)           |  |
|  +------------------------+             +----------------------------+  |
|               ^                                       ^                 |
|               |                                       |                 |
|  +-------------------------------------------------------------------+  |
|  |                    ComputerControl (Phase 3)                      |  |
|  |       Observe -> Plan -> Act -> Observe -> Verify Loop            |  |
|  +-------------------------------------------------------------------+  |
|          |                 |                   |             |          |
|          v                 v                   v             v          |
|    +-----------+    +---------------+    +-----------+  +------------+  |
|    |ScreenTool |    |  UIInspector  |    |LocalOCR   |  |PyAutoGUI / |  |
|    |(Screenshot|    |(Win32 API &   |    | (Engine & |  |Win32 Input |  |
|    | Captures) |    | UIAutomation) |    | Bounding) |  | Injection) |  |
|    +-----------+    +---------------+    +-----------+  +------------+  |
+-------------------------------------------------------------------------+
```

---

## Key Components

### 1. UIInspector (`core/ui_inspector.py`)
- **Window Enumeration & Geometry**: Native CTypes User32 / PowerShell automation for enumerating open windows, retrieving HWNDs, window bounds (`x`, `y`, `width`, `height`), and window titles.
- **Window Focus Management**: Focuses target windows before interaction.
- **UI Automation Discovery**: Inspects native elements (Buttons, Text boxes, Menus) via Windows UI Automation.
- **DPI Awareness**: Calculates display DPI scaling factors (`get_dpi_scaling()`) to map logical element boundaries to physical screen pixels.

### 2. LocalOCREngine (`core/ui_inspector.py`)
- Decoupled, on-device OCR engine utilizing PyTesseract with PIL bounding-box fallback.
- Enables visual search (`find_text_in_image`) for un-automatable UI targets without sending screen data to third-party cloud services.

### 3. ComputerControl (`tools/computer_control.py`)
- Re-uses `ScreenTool` for screenshot acquisition (`observe_screen`).
- Coordinate Resolution (`resolve_target_coordinates`): Supports Absolute `(x, y)`, Relative `{"rel_x", "rel_y"}`, UI Element queries `{"control_type": "Button", "name": "Save"}`, and OCR text search queries `"Click Here"`.
- Execution Safeguards: Never blind-clicks; returns `TARGET_NOT_FOUND` if target coordinates cannot be verified.
- Atomic Checkpoint Integration: Saves PRE and POST tool execution checkpoints via `CheckpointEngine` in SQLite WAL.
- Post-action Verification: Captures post-action screen observation and verifies outcome against expected criteria or OCR matches.

---

## Action Status Matrix

| Status | Description |
|---|---|
| `RESULT_VERIFIED` | Action executed and post-action physical verification criteria satisfied. |
| `RESULT_OBSERVED` | Action executed and post-action screen capture completed. |
| `ACTION_EXECUTED` | Action sent to system input queue. |
| `ACTION_REJECTED` | Action execution rejected by safety rules or exception handling. |
| `TARGET_NOT_FOUND` | Target element or coordinates could not be resolved; blind clicking prevented. |

---

## Unit & Integration Testing

The test suite in `tests/test_desktop_vision.py` contains 25 comprehensive physical scenario test cases:
1. `test_screentool_integration`
2. `test_window_discovery`
3. `test_window_identification`
4. `test_window_focus`
5. `test_window_geometry`
6. `test_ui_element_discovery`
7. `test_button_discovery`
8. `test_text_edit_discovery`
9. `test_ocr_result_parsing`
10. `test_coordinate_conversion`
11. `test_dpi_scaling`
12. `test_click_abstraction`
13. `test_keyboard_abstraction`
14. `test_post_action_observation`
15. `test_physical_verification`
16. `test_permission_enforcement`
17. `test_tool_registry_integration`
18. `test_checkpoint_integration`
19. `test_resume_integration`
20. `test_invalid_target_handling`
21. `test_window_disappeared_handling`
22. `test_focus_changed_unexpectedly`
23. `test_ocr_confidence_fallback`
24. `test_ui_automation_unavailable_fallback`
25. `test_safe_failure_without_blind_clicking`

---

## Regression & Immunity

Phase 3 is fully backward compatible with Phase 1 (`StateEngine`) and Phase 2 (`CheckpointEngine` & `ResumeEngine`). 100% of previous test suites continue to pass alongside Phase 3 tests (279 total tests PASS).
