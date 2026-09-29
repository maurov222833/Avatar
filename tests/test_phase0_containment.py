"""
Fase 0, después de U1.

- La API HTTP exige un token y rechaza Host/Origin que no sean locales.
- La multitarea determinista solo corre en un canal local y con el prefijo avatar-exec:.
- `.env` no pisa una variable que el proceso ya tiene.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHttpGuard(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        import server
        self.server = server
        self.client = TestClient(server.app)
        self.headers = server.auth_headers()

    def test_api_without_token_is_rejected(self):
        for path in ("/api/config", "/api/whatsapp/status"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401, path)
            self.assertEqual(response.json()["detail"], "HTTP_TOKEN_REQUIRED")
        for path in ("/api/terminal/execute", "/api/chat", "/api/whatsapp/webhook"):
            response = self.client.post(
                path, json={"command": "echo x", "message": "hola", "sender": "a"})
            self.assertEqual(response.status_code, 401, path)
            self.assertEqual(response.json()["detail"], "HTTP_TOKEN_REQUIRED")

    def test_page_embeds_the_token_and_api_accepts_it(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.server.http_token, page.text)
        response = self.client.get("/api/config", headers=self.headers)
        self.assertEqual(response.status_code, 200)

    def test_foreign_host_and_origin_are_rejected(self):
        foreign = self.client.get("/api/config", headers={**self.headers, "host": "evil.example"})
        self.assertEqual(foreign.status_code, 403)
        self.assertEqual(foreign.json()["detail"], "HOST_NOT_ALLOWED")
        origin = self.client.get("/", headers={"origin": "http://evil.example"})
        self.assertEqual(origin.status_code, 403)
        self.assertEqual(origin.json()["detail"], "ORIGIN_NOT_ALLOWED")
        local = self.client.get("/api/config", headers={
            **self.headers, "origin": "http://127.0.0.1:8000"})
        self.assertEqual(local.status_code, 200)
        disguised = self.client.get("/api/config", headers={
            **self.headers, "host": "[::1]evil.example"})
        self.assertEqual(disguised.status_code, 403)


class TestMultiTaskChannel(unittest.TestCase):

    def _orch(self):
        from core.orchestrator import AvatarOrchestrator
        orch = AvatarOrchestrator()
        orch.chokepoint.policy.exec_requires_approval = False
        return orch

    def test_remote_command_lines_are_not_executed(self):
        orch = self._orch()
        ran = []
        orch.chokepoint.executors["COMMAND"] = lambda a: ran.append(a["command"]) or "ok"
        text = "avatar-exec:\necho UNO\necho DOS"
        orch.process_user_input(text, max_steps=1, channel="remote")
        self.assertEqual(ran, [])

    def test_local_without_prefix_is_not_executed(self):
        orch = self._orch()
        ran = []
        orch.chokepoint.executors["COMMAND"] = lambda a: ran.append(a["command"]) or "ok"
        orch.process_user_input("echo UNO\necho DOS", max_steps=1, channel="local")
        self.assertEqual(ran, [])

    def test_local_prefix_reaches_the_chokepoint(self):
        orch = self._orch()
        ran = []
        def execute(args):
            command = args["command"]
            ran.append(command)
            token = command.split()[-1]
            return f"[Resultado PowerShell (ExitCode: 0)]:\nstdout:\n{token}\n"
        orch.chokepoint.executors["COMMAND"] = execute
        orch.process_user_input("avatar-exec:\necho UNO\necho DOS", max_steps=4, channel="local")
        self.assertEqual(ran, ["echo UNO", "echo DOS"])


class TestDotenvDoesNotOverride(unittest.TestCase):

    def test_existing_env_wins_over_file(self):
        from core.llm_provider import LLMProvider
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, ".env")
        with open(path, "w", encoding="utf-8") as f:
            f.write("AVATAR_DOTENV_PROBE=from-file\n")
        provider = LLMProvider(config_path=os.path.join(folder, "none.json"))
        key = "AVATAR_DOTENV_PROBE"
        from unittest import mock
        with mock.patch.dict(os.environ, {key: "from-env"}):
            provider._load_env(path)
            self.assertEqual(os.environ[key], "from-env")
        with mock.patch.dict(os.environ, {key: ""}):
            provider._load_env(path)
            self.assertEqual(os.environ[key], "")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(key, None)
            provider._load_env(path)
            self.assertEqual(os.environ[key], "from-file")


if __name__ == "__main__":
    unittest.main()
