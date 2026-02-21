import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from codeintel.api import app


def _make_zip_bytes() -> bytes:
    payload = b"def foo():\n    return 1\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("repo/sample.py", payload)
    return buffer.getvalue()


def test_parse_endpoint() -> None:
    client = TestClient(app)
    zip_bytes = _make_zip_bytes()

    response = client.post(
        "/parse?max_files=5",
        files={"file": ("repo.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "links" in data or "edges" in data


def test_parse_rejects_non_zip() -> None:
    client = TestClient(app)
    response = client.post(
        "/parse",
        files={"file": ("repo.txt", b"not zip", "text/plain")},
    )
    assert response.status_code == 400


def test_parse_requires_input() -> None:
    client = TestClient(app)
    response = client.post("/parse")
    assert response.status_code == 400


def test_parse_repo_url(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    zip_bytes = _make_zip_bytes()

    class FakeResponse:
        def __init__(self, status_code: int, content: bytes, json_payload: dict | None = None) -> None:
            self.status_code = status_code
            self.content = content
            self._json_payload = json_payload

        def json(self) -> dict:
            if self._json_payload is None:
                raise ValueError("No JSON payload")
            return self._json_payload

    def fake_get(url: str, timeout: float = 60.0, **_kwargs) -> FakeResponse:
        if url.startswith("https://api.github.com/repos/"):
            return FakeResponse(200, b"", {"default_branch": "main"})
        return FakeResponse(200, zip_bytes)

    monkeypatch.setattr("codeintel.api.httpx.get", fake_get)

    response = client.post(
        "/parse?repo_url=https://github.com/spacetelescope/jwst&max_files=5"
    )
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
