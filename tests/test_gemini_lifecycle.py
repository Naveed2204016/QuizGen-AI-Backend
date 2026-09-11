import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from app.clients import gemini


class ClientLifecycleTests(unittest.TestCase):
    def test_parallel_requests_own_and_close_their_clients(self):
        clients = []

        class Client:
            def __init__(self):
                self.closed = False
                self.models = self
                clients.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.closed = True

            def generate_content(self, **kwargs):
                assert not self.closed
                assert kwargs["config"].automatic_function_calling.disable
                return SimpleNamespace(text='{"questions": []}')

        with patch.object(gemini, "get_gemini_client", side_effect=Client), patch.object(
            gemini, "get_settings", return_value=SimpleNamespace(gemini_model="test")
        ):
            with ThreadPoolExecutor(max_workers=3) as pool:
                results = list(pool.map(lambda _: gemini.generate_json(
                    system_instruction="test", prompt="test", max_output_tokens=100
                ), range(6)))
        self.assertEqual(len(results), 6)
        self.assertEqual(len(clients), 6)
        self.assertTrue(all(client.closed for client in clients))

    def test_unhandled_errors_are_readable_cross_origin(self):
        from fastapi.testclient import TestClient
        from app.main import app

        async def fail():
            raise RuntimeError("private diagnostic")

        route_count = len(app.app.router.routes)
        app.app.add_api_route("/__test_failure", fail)
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/__test_failure", headers={"Origin": "http://localhost:5500"})
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5500")
            self.assertIn("internal error", response.json()["detail"])
            self.assertNotIn("private diagnostic", response.text)
        finally:
            del app.app.router.routes[route_count:]
