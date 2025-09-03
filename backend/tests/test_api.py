import os
import sys
import types
import pathlib
import importlib.util
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient


def load_main_module():
    base_dir = pathlib.Path(__file__).resolve().parents[1]
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))
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

def test_generate_stream_success(monkeypatch):
    # Ensure API key is present
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    app_mod = load_main_module()

    import types as _types
    import app.services.generation as gen

    async def _dummy_stream():
        class _Choice:
            def __init__(self, content):
                self.delta = _types.SimpleNamespace(content=content)

        yield _types.SimpleNamespace(choices=[_types.SimpleNamespace(delta=_types.SimpleNamespace(content="Hello"))])
        yield _types.SimpleNamespace(choices=[_types.SimpleNamespace(delta=_types.SimpleNamespace(content=" World"))])

    class _DummyAsyncOpenAI:
        def __init__(self, api_key: str):
            self.chat = _types.SimpleNamespace(
                completions=_types.SimpleNamespace(create=lambda **kwargs: _dummy_stream())
            )

    monkeypatch.setattr(gen, "AsyncOpenAI", _DummyAsyncOpenAI)

    client = TestClient(app_mod.app)
    resp = client.post("/api/generate", json={"prompt": "Draft"})
    assert resp.status_code == 200
    assert "Hello World" in resp.text


def test_sessions_are_independent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    app_mod = load_main_module()
    client = TestClient(app_mod.app)

    # Start first session
    r1 = client.post("/api/session/start", json={})
    assert r1.status_code == 200
    s1 = r1.json()["session_id"]
    client.post(f"/api/session/{s1}/document", json={"html": "# Doc A", "title": "A"})

    # Start second session
    r2 = client.post("/api/session/start", json={})
    assert r2.status_code == 200
    s2 = r2.json()["session_id"]
    client.post(f"/api/session/{s2}/document", json={"html": "# Doc B", "title": "B"})

    # Verify list shows both with distinct titles
    rl = client.get("/api/session/list")
    assert rl.status_code == 200
    sessions = rl.json()["sessions"]
    ids = {s["session_id"] for s in sessions}
    assert s1 in ids and s2 in ids
    # Document titles are per-session and preserved
    titles = {s["session_id"]: s.get("document_title") for s in sessions}
    assert titles.get(s1) == "A"
    assert titles.get(s2) == "B"
