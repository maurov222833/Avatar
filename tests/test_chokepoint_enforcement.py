"""
CHOKEPOINT ENFORCEMENT — regression guards for side-effect bypasses.

Every test here corresponds to a real bypass found during IMPLEMENTATION 006. They are
deliberately structural: they scan the source for direct tool invocation, so re-introducing
`ShellTool.execute_command(...)` outside the chokepoint fails the suite even if the runtime
behaviour happens to look fine.

A passing suite here means: "no module outside core/act_chokepoint.py invokes an executor
directly". It does NOT mean the policy is correct or that a shell cannot be reached some other
way — that is Model B and is out of scope in-process.
"""
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Modules allowed to name an executor. The orchestrator may, because it *builds* the
#: chokepoint's executor table; nothing else may.
EXECUTOR_ALLOWLIST = {
    os.path.join("core", "act_chokepoint.py"),
    os.path.join("core", "orchestrator.py"),
}

#: (class, method) pairs that constitute "performing a side effect".
EXECUTOR_CALLS = {
    ("ShellTool", "execute_command"),
    ("FileTool", "write_file"),
    ("WhatsAppAutoReply", "send_reply"),
    ("WhatsAppAutoReply", "focus_whatsapp_window"),
    ("AudioTool", "play_local_audio"),
    ("AudioTool", "play_online_music"),
    ("WebTool", "search_web"),
}


def iter_source_files(subdirs=("core", "tools", "interface", "bridges")):
    for sub in subdirs:
        base = os.path.join(ROOT, sub)
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
            for fn in files:
                if fn.endswith(".py"):
                    yield os.path.join(root, fn)
    # root-level entry points
    for fn in os.listdir(ROOT):
        if fn.endswith(".py"):
            yield os.path.join(ROOT, fn)


def find_direct_executor_calls():
    """
    Return [(relpath, line, 'Class.method')] for executor calls outside the allowlist.

    Two legitimate patterns are excluded:
      * a tool module calling its own method (e.g. `send_reply` -> `focus_whatsapp_window`);
      * a module's `if __name__ == "__main__"` demo block, which is a standalone CLI entry
        point rather than part of the agent's execution path.
    """
    hits = []
    for path in iter_source_files():
        rel = os.path.relpath(path, ROOT)
        if rel in EXECUTOR_ALLOWLIST:
            continue
        source = open(path, encoding="utf-8", errors="ignore").read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        # Lines belonging to a `if __name__ == "__main__":` block.
        main_lines = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.If) and node.lineno
                    and isinstance(node.test, ast.Compare)):
                src = ast.dump(node.test)
                if "__name__" in src and "__main__" in src:
                    for sub in ast.walk(node):
                        if hasattr(sub, "lineno"):
                            main_lines.update(range(sub.lineno,
                                                    (sub.end_lineno or sub.lineno) + 1))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or node.lineno in main_lines:
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                pair = (func.value.id, func.attr)
                if pair in EXECUTOR_CALLS:
                    # A tool module calling its own class method is not a bypass.
                    # Compare normalised names: file `whatsapp_auto_reply.py` defines
                    # class `WhatsAppAutoReply`.
                    owner = os.path.splitext(os.path.basename(path))[0]
                    norm = lambda s: s.replace("_", "").lower()
                    if norm(pair[0]) == norm(owner):
                        continue
                    hits.append((rel, node.lineno, f"{pair[0]}.{pair[1]}"))
    return hits


class TestChokepointEnforcement(unittest.TestCase):

    def test_no_module_bypasses_the_chokepoint(self):
        """
        Proves: no module outside the allowlist invokes a side-effect executor directly.
        This is the regression guard for the /api/terminal/execute, WhatsApp bridge and legacy
        text-path bypasses found in IMPLEMENTATION 006.
        """
        hits = find_direct_executor_calls()
        detail = "\n".join(f"  {r}:{l}  {c}" for r, l, c in hits)
        self.assertEqual(
            hits, [],
            "Side effects must go through ActChokepoint. Direct executor calls found:\n" + detail,
        )

    def test_server_terminal_endpoint_uses_the_chokepoint(self):
        """Proves: the GUI terminal endpoint is policy-checked and recorded."""
        import server
        src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        fn = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "execute_terminal_command":
                fn = node
                break
        self.assertIsNotNone(fn, "the terminal endpoint must still exist")
        called = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
        self.assertIn("perform", called,
                      "the terminal endpoint must call chokepoint.perform()")

    def test_whatsapp_bridge_uses_the_chokepoint(self):
        """Proves: the WhatsApp reply path is policy-checked and recorded."""
        path = os.path.join(ROOT, "bridges", "whatsapp_bridge.py")
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        fns = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.FunctionDef)
                    and node.name in ("process_incoming_whatsapp", "_deliver")):
                fns[node.name] = node
        self.assertIn("process_incoming_whatsapp", fns)
        self.assertIn("_deliver", fns)
        attrs = set()
        for fn in fns.values():
            attrs |= {n.func.attr for n in ast.walk(fn)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("process_user_input", attrs)
        self.assertIn("_deliver", attrs)
        self.assertIn("perform", attrs,
                      "the WhatsApp bridge must call chokepoint.perform()")

    def test_config_endpoint_redacts_secrets(self):
        """
        Proves: /api/config does not hand API keys to a local HTTP client.
        """
        import server
        redacted = server.redact_secrets(
            {"gemini": {"api_key": "sk-real-secret-value"}, "model": "x"})
        self.assertNotIn("sk-real-secret-value", str(redacted))
        self.assertIn("model", redacted)

    def test_legacy_tool_path_uses_the_chokepoint(self):
        """Proves: the text-parsed tool path is routed through the chokepoint too."""
        from core.orchestrator import AvatarOrchestrator
        fn = AvatarOrchestrator._dispatch_tool_action
        src = open(os.path.join(ROOT, "core", "orchestrator.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_dispatch_tool_action":
                attrs = {n.func.attr for n in ast.walk(node)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
                self.assertIn("perform", attrs)
                return
        self.fail("_dispatch_tool_action not found")


if __name__ == "__main__":
    unittest.main(verbosity=2)
