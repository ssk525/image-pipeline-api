# Image Pipeline API

> FastAPI + OpenCV service for **resize, format conversion, and image filters** — with latency headers, Docker deploy, and measured benchmarks.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-orange)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

**[GitHub](https://github.com/ssk525/image-pipeline-api)** · **[Architecture](#architecture)** · **[REST API](#rest-api)** · **[Benchmarks](#benchmarks)** · **[Resume bullets](docs/RESUME_BULLETS.md)**

---

## What This Is

A compact **image processing microservice** (imgproxy-style), not a notebook demo:

- Accepts image uploads over REST (`multipart/form-data`)
- Resizes with aspect-ratio control or `max_side` thumbnails
- Converts JPEG / PNG / WebP
- Applies OpenCV filters: grayscale, blur, sharpen, denoise, histogram equalize
- Returns binary image plus `X-Process-Time-Ms` and size headers
- Ships with Pytest coverage, Docker Compose, and a local benchmark script

---

## Architecture

```
┌──────────────┐     multipart upload      ┌────────────────────────────┐
│  Client /    │ ─────────────────────────▶│  FastAPI  /v1/process      │
│  curl / app  │                           └─────────────┬──────────────┘
└──────────────┘                                         │
                                                         ▼
                                           ┌────────────────────────────┐
                                           │  OpenCV pipeline           │
                                           │  1. decode                 │
                                           │  2. resize / max_side      │
                                           │  3. filter (optional)      │
                                           │  4. encode + metrics       │
                                           └─────────────┬──────────────┘
                                                         │
                                                         ▼
                                           image bytes + X-* headers
```

| Stage | Component | Details |
|-------|-----------|---------|
| 1. Ingest | FastAPI UploadFile | Size-capped upload (`MAX_UPLOAD_BYTES`) |
| 2. Decode | `cv2.imdecode` | JPEG/PNG/WebP/BMP |
| 3. Geometry | resize / max_side | Aspect-preserving or forced box |
| 4. Filter | OpenCV ops | grayscale, blur, sharpen, denoise, equalize |
| 5. Encode | `cv2.imencode` | quality for JPEG/WebP |
| 6. Observe | response headers | latency ms, in/out dimensions & bytes |

---

## Quick Start

### Prerequisites

- Python 3.10+
- (Optional) Docker

### Install & run

```bash
git clone https://github.com/ssk525/image-pipeline-api.git
cd image-pipeline-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_api.py
```

Open docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Example request

```bash
curl -X POST "http://127.0.0.1:8000/v1/process" \
  -F "file=@samples/sample.jpg" \
  -F "width=320" \
  -F "format=webp" \
  -F "filter=sharpen" \
  -F "quality=80" \
  --output out.webp -D -
```

### Docker

```bash
docker compose up --build
```

---

## REST API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| GET | `/v1/ops` | Supported filters & formats |
| POST | `/v1/process` | Process image → binary body + `X-*` headers |
| POST | `/v1/process/meta` | Same pipeline → JSON metrics only |

### Process form fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `file` | file | required | Input image |
| `width` / `height` | int | — | Target size |
| `keep_aspect` | bool | `true` | Preserve aspect ratio |
| `max_side` | int | — | Longer side cap (thumbnails) |
| `format` | enum | `jpeg` | `jpeg` \| `png` \| `webp` |
| `quality` | int | `85` | JPEG/WebP quality 1–100 |
| `filter` | enum | `none` | see `/v1/ops` |

---

## Benchmarks

Run locally:

```bash
python run_benchmark.py
```

Example numbers on a sample 640×480 JPEG (machine-dependent):

| Case | Output | Bytes in → out | Latency (ms) |
|------|--------|----------------|--------------|
| resize_320_jpeg | 320x240 (jpeg) | 26593 → 12470 | 0.51 |
| thumbnail_128_webp | 128x96 (webp) | 26593 → 1146 | 0.95 |
| grayscale_png | 256x192 (png) | 26593 → 2522 | 2.21 |
| denoise_jpeg | 320x240 (jpeg) | 26593 → 10483 | 71.43 |
| sharpen_jpeg | 320x240 (jpeg) | 26593 → 15774 | 0.5 |

Replace the table with your `run_benchmark.py` output before interviews.

---

## Tests

```bash
pytest -q
```

---

## Layout

```
api/app.py           FastAPI routes
src/image_ops.py     OpenCV decode → transform → encode
src/schemas.py       Request models / enums
src/config.py        Settings from env
tests/               API + unit tests
samples/             Demo images
docs/                Resume bullets + study notes
run_api.py           Server entrypoint
run_benchmark.py     Latency / size table
Dockerfile           Production-style container
docker-compose.yml   One-command local deploy
```

---

## License

MIT — see [LICENSE](LICENSE).
