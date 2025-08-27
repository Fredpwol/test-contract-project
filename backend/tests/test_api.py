import os
import types
import pathlib
import importlib.util
from fastapi.testclient import TestClient


def load_main_module():
    base_dir = pathlib.Path(__file__).resolve().parents[1]
    main_path = base_dir / "main.py"
    spec = importlib.util.spec_from_file_location("main", str(main_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class DummyStream:
    def __iter__(self):
        class Choice:
            def __init__(self, content):
                self.delta = types.SimpleNamespace(content=content)

        for part in ["<h1>Test</h1>", "<p>ok</p>"]:
            yield types.SimpleNamespace(choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=part))])


class DummyClient:
    def __init__(self):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        return DummyStream()


def test_health():
    app_mod = load_main_module()
    client = TestClient(app_mod.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_generate_stream(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    app_mod = load_main_module()

    class DummyOpenAI:
        def __init__(self, api_key: str):
            self._client = DummyClient()

        @property
        def chat(self):
            return self._client.chat

    app_mod.OpenAI = DummyOpenAI  # type: ignore

    client = TestClient(app_mod.app)
    resp = client.post(
        "/api/generate",
        json={"prompt": "Draft terms of service"},
    )
    assert resp.status_code == 200
    assert resp.text.startswith("<article")
    assert resp.text.endswith("</article>")
    assert "Test" in resp.text
