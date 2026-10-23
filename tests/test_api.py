"""API and image-op tests."""

from __future__ import annotations

import os

os.environ["MAX_UPLOAD_BYTES"] = str(2 * 1024 * 1024)
os.environ["MAX_PIXELS"] = str(4_000_000)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from src import image_ops  # noqa: E402
from src.image_ops import Filter, OutputFormat  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _png(width: int = 120, height: int = 80, channels: int = 3) -> bytes:
    rng = np.random.default_rng(7)
    img = rng.integers(0, 255, size=(height, width, channels), dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _decode(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    assert img is not None
    return img


def test_health_has_timing_and_request_id(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "image-pipeline-api"
    assert float(resp.headers["X-Process-Time-Ms"]) >= 0
    assert resp.headers["X-Request-ID"]


def test_ops_lists_filters_and_formats(client: TestClient) -> None:
    body = client.get("/v1/ops").json()
    assert set(body["filters"]) == {"none", "grayscale", "blur", "sharpen", "denoise", "equalize"}
    assert set(body["formats"]) == {"jpeg", "png", "webp"}


@pytest.mark.parametrize("fmt,magic", [("jpeg", b"\xff\xd8"), ("png", b"\x89PNG"), ("webp", b"RIFF")])
def test_convert_formats(client: TestClient, fmt: str, magic: bytes) -> None:
    resp = client.post(
        "/v1/process", files={"file": ("in.png", _png(), "image/png")}, data={"format": fmt}
    )
    assert resp.status_code == 200, resp.text
    assert resp.content.startswith(magic)
    assert resp.headers["content-type"] == image_ops.MEDIA_TYPES[OutputFormat(fmt)]


@pytest.mark.parametrize("name", [f.value for f in Filter])
def test_every_filter_runs(client: TestClient, name: str) -> None:
    resp = client.post(
        "/v1/process",
        files={"file": ("in.png", _png(), "image/png")},
        data={"filter": name, "format": "png"},
    )
    assert resp.status_code == 200, resp.text
    assert _decode(resp.content).shape[:2] == (80, 120)


def test_grayscale_channels_are_equal(client: TestClient) -> None:
    resp = client.post(
        "/v1/process",
        files={"file": ("in.png", _png(), "image/png")},
        data={"filter": "grayscale", "format": "png"},
    )
    img = _decode(resp.content)
    assert np.array_equal(img[:, :, 0], img[:, :, 1])
    assert np.array_equal(img[:, :, 1], img[:, :, 2])


def test_resize_keeps_aspect_with_one_side(client: TestClient) -> None:
    resp = client.post(
        "/v1/process",
        files={"file": ("in.png", _png(120, 80), "image/png")},
        data={"width": "60", "format": "png"},
    )
    assert resp.headers["X-Output-Size"] == "60x40"
    assert _decode(resp.content).shape[:2] == (40, 60)


def test_max_side_only_shrinks(client: TestClient) -> None:
    big = client.post(
        "/v1/process",
        files={"file": ("in.png", _png(120, 80), "image/png")},
        data={"max_side": "60", "format": "png"},
    )
    assert big.headers["X-Output-Size"] == "60x40"
    small = client.post(
        "/v1/process",
        files={"file": ("in.png", _png(120, 80), "image/png")},
        data={"max_side": "500", "format": "png"},
    )
    assert small.headers["X-Output-Size"] == "120x80"


def test_size_headers_match_bytes(client: TestClient) -> None:
    raw = _png()
    resp = client.post("/v1/process", files={"file": ("in.png", raw, "image/png")})
    assert int(resp.headers["X-Input-Bytes"]) == len(raw)
    assert int(resp.headers["X-Output-Bytes"]) == len(resp.content)
    assert float(resp.headers["X-Pipeline-Ms"]) >= 0


def test_meta_returns_json_without_image(client: TestClient) -> None:
    resp = client.post(
        "/v1/process/meta",
        files={"file": ("in.png", _png(), "image/png")},
        data={"filter": "denoise", "max_side": "60"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_size"] == [60, 40]
    assert set(body["stage_ms"]) == {"decode", "resize", "filter", "encode"}
    assert body["output_bytes"] > 0


def test_png_alpha_survives_png_output(client: TestClient) -> None:
    resp = client.post(
        "/v1/process",
        files={"file": ("in.png", _png(channels=4), "image/png")},
        data={"filter": "blur", "format": "png"},
    )
    assert _decode(resp.content).shape[2] == 4


def test_corrupt_upload_is_400(client: TestClient) -> None:
    resp = client.post("/v1/process", files={"file": ("x.png", b"not an image", "image/png")})
    assert resp.status_code == 400
    assert "X-Process-Time-Ms" in resp.headers


def test_empty_upload_is_400(client: TestClient) -> None:
    resp = client.post("/v1/process", files={"file": ("x.png", b"", "image/png")})
    assert resp.status_code == 400


def test_oversized_upload_is_413(client: TestClient) -> None:
    resp = client.post(
        "/v1/process", files={"file": ("big.bin", b"\0" * (2 * 1024 * 1024 + 1), "image/png")}
    )
    assert resp.status_code == 413


def test_too_many_pixels_is_413(client: TestClient) -> None:
    resp = client.post(
        "/v1/process",
        files={"file": ("in.png", _png(120, 80), "image/png")},
        data={"width": "8000", "height": "8000"},
    )
    assert resp.status_code == 413


def test_bad_quality_and_filter_are_422(client: TestClient) -> None:
    files = {"file": ("in.png", _png(), "image/png")}
    assert client.post("/v1/process", files=files, data={"quality": "0"}).status_code == 422
    assert client.post("/v1/process", files=files, data={"filter": "emboss"}).status_code == 422


def test_target_size_rules() -> None:
    assert image_ops.target_size(100, 50, out_width=40, out_height=10) == (40, 10)
    assert image_ops.target_size(100, 50, out_height=25) == (50, 25)
    assert image_ops.target_size(100, 50, max_side=50) == (50, 25)
    assert image_ops.target_size(100, 50) == (100, 50)
