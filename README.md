# Image Pipeline API

A small FastAPI + OpenCV microservice. Upload an image; get it back resized, filtered, and re-encoded as JPEG, PNG, or WebP. Every response carries process-time and byte-size headers, so latency and payload size are visible without opening a log.

No login and no database on purpose: one stateless image pipeline over REST, tested with Pytest, packaged with Docker Compose, and timed with a benchmark script.

## Features

| Area | What it does |
|------|--------------|
| Resize | `width`, `height`, or both; one side keeps aspect ratio; `max_side` only shrinks |
| Filters | `grayscale`, `blur` (Gaussian 5x5), `sharpen` (3x3 kernel), `denoise` (non-local means), `equalize` (histogram on luma) |
| Formats | Output `jpeg`, `png`, `webp` with `quality` 1–100; PNG alpha is kept for PNG/WebP output |
| Headers | `X-Process-Time-Ms`, `X-Request-ID` on every response; `X-Input-Bytes`, `X-Output-Bytes`, `X-Input-Size`, `X-Output-Size`, `X-Pipeline-Ms` on processed images |
| Limits | Upload size (413), decoded pixel count (413), output side length (422), corrupt or empty file (400) |
| Ops | Pytest, Docker (non-root user, health check), Docker Compose, benchmark script, GitHub Actions |

## Pipeline

```
multipart upload ─▶ size-capped read ─▶ cv2.imdecode ─▶ resize ─▶ filter ─▶ cv2.imencode ─▶ bytes + headers
                                        (pixel limit)   (INTER_AREA down,
                                                         INTER_CUBIC up)
```

Each stage is timed; `/v1/process/meta` returns the per-stage milliseconds as JSON.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest -q
python run_api.py            # http://127.0.0.1:8000/docs
```

Docker:

```bash
docker compose up --build
```

## REST API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + version |
| GET | `/v1/ops` | Filters, formats, resize options, limits |
| POST | `/v1/process` | Multipart `file` → processed image bytes + headers |
| POST | `/v1/process/meta` | Same processing, returns JSON (sizes, bytes, per-stage ms) without the image |

Form fields for both POST routes: `file`, `filter`, `format`, `quality`, `width`, `height`, `max_side`.

```bash
curl -s -D - -o out.webp \
  -F file=@photo.png -F filter=sharpen -F format=webp -F max_side=300 \
  http://127.0.0.1:8000/v1/process
```

```
x-input-bytes: 1623522
x-output-bytes: 53302
x-input-size: 900x600
x-output-size: 300x200
x-pipeline-ms: 8.92
x-process-time-ms: 12.12
```

## Benchmark

```bash
python run_benchmark.py                          # in-process pipeline
python run_benchmark.py --url http://localhost:8000   # through HTTP, e.g. against Docker Compose
```

Measured on 23 Oct 2026, Apple Silicon laptop, synthetic 1920x1080 PNG (4.2 MB), median of 3 runs, in-process. Timings depend on the machine.

| filter | format | resize | median ms | output bytes |
|---|---|---|---:|---:|
| none | jpeg | - | 23.90 | 589499 |
| grayscale | jpeg | - | 23.47 | 511947 |
| blur | jpeg | - | 23.12 | 297970 |
| sharpen | jpeg | - | 25.62 | 1291545 |
| denoise | jpeg | - | 439.92 | 231945 |
| equalize | jpeg | - | 30.12 | 853805 |
| none | png | - | 111.40 | 4408500 |
| none | webp | - | 166.22 | 597874 |
| none | jpeg | max_side=640 | 21.27 | 50736 |

Denoise dominates: non-local means is roughly 20x the cost of the other filters at 1080p. Through HTTP the same runs add about 5 ms each for multipart upload and response.

## Project layout

```
api/app.py            FastAPI routes, timing + request-id middleware, upload limits
src/image_ops.py      decode, resize, filters, encode (OpenCV)
src/pipeline.py       one request through the stages, with per-stage timings
src/config.py         settings from environment
tests/test_api.py     Pytest: formats, filters, resize rules, headers, limits, errors
run_benchmark.py      timing table, in-process or over HTTP
```

## License

MIT — see [LICENSE](LICENSE).
