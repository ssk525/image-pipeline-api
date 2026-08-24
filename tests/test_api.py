"""Unit and API tests for the image pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import app
from src.image_ops import ImageProcessError, process_image
from src.schemas import FilterOp, OutputFormat, ProcessParams

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_JPG = ROOT / "samples" / "sample.jpg"
SAMPLE_PNG = ROOT / "samples" / "sample.png"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def jpg_bytes() -> bytes:
    return SAMPLE_JPG.read_bytes()


def test_decode_and_resize(jpg_bytes: bytes) -> None:
    result = process_image(
        jpg_bytes,
        ProcessParams(width=320, height=240, keep_aspect=True, format=OutputFormat.jpeg, quality=80),
    )
    assert result.output_width == 320
    assert result.output_height == 240
    assert result.output_bytes > 0
    assert result.process_ms >= 0


def test_max_side(jpg_bytes: bytes) -> None:
    result = process_image(jpg_bytes, ProcessParams(max_side=160, format=OutputFormat.png))
    assert max(result.output_width, result.output_height) == 160
    assert result.format == "png"


def test_filters(jpg_bytes: bytes) -> None:
    for op in FilterOp:
        result = process_image(
            jpg_bytes,
            ProcessParams(max_side=128, filter=op, format=OutputFormat.jpeg, quality=70),
        )
        assert result.filter == op.value
        assert result.output_bytes > 0


def test_invalid_bytes() -> None:
    with pytest.raises(ImageProcessError):
        process_image(b"not-an-image", ProcessParams())


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "image-pipeline-api"


def test_list_ops(client: TestClient) -> None:
    resp = client.get("/v1/ops")
    assert resp.status_code == 200
    assert "grayscale" in resp.json()["operations"]
    assert "webp" in resp.json()["formats"]


def test_process_endpoint(client: TestClient, jpg_bytes: bytes) -> None:
    resp = client.post(
        "/v1/process",
        files={"file": ("sample.jpg", jpg_bytes, "image/jpeg")},
        data={"width": "200", "format": "webp", "filter": "sharpen", "quality": "75"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/webp")
    assert "X-Process-Time-Ms" in resp.headers
    assert int(resp.headers["X-Output-Bytes"]) == len(resp.content)


def test_process_meta(client: TestClient) -> None:
    png = SAMPLE_PNG.read_bytes()
    resp = client.post(
        "/v1/process/meta",
        files={"file": ("sample.png", png, "image/png")},
        data={"max_side": "100", "format": "jpeg", "quality": "60"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_width"] <= 100
    assert body["output_height"] <= 100
    assert body["process_ms"] >= 0


def test_bad_upload(client: TestClient) -> None:
    resp = client.post(
        "/v1/process",
        files={"file": ("bad.bin", b"xyz", "application/octet-stream")},
    )
    assert resp.status_code == 400
