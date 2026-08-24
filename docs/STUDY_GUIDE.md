# Study guide — Image Pipeline API

## One-minute pitch

"I built a small production-style image microservice: upload an image, apply OpenCV resize/filter/encode, get the bytes back with latency headers. Same pattern as an image CDN transform service, but owned end-to-end in Python with tests and Docker."

## Why this project (interview)

| Question they ask | Your angle |
|-------------------|------------|
| Why FastAPI? | Async upload handling, automatic OpenAPI docs, typed params |
| Why OpenCV headless? | Server deploy without GUI deps; `imdecode`/`imencode` pipeline |
| How do you measure quality? | Output size vs quality knob; latency headers; benchmark script |
| Failure modes? | Corrupt uploads, oversized payloads, unsupported codecs → 400/413 |
| How does this relate to camera / embedded? | Geometry + encode under constraints; same ideas as ISP preview pipelines |

## Core pipeline (memorize)

1. Read bytes from multipart upload  
2. `np.frombuffer` → `cv2.imdecode`  
3. Resize (`keep_aspect` or `max_side`)  
4. Optional filter  
5. `cv2.imencode` with quality  
6. Return bytes + `X-Process-Time-Ms`

## Commands to demo live

```bash
python run_api.py
curl -F "file=@samples/sample.jpg" -F "max_side=128" -F "format=webp" \
  http://127.0.0.1:8000/v1/process --output thumb.webp -D -
pytest -q
python run_benchmark.py
```

## Design decisions

- **Form params, not JSON body** — natural for file uploads; matches how browsers and curl send images.
- **Separate `/v1/process/meta`** — benchmarks and CI can assert metrics without writing image files.
- **Headers for observability** — no DB required; good for interviews about metrics without overbuilding.
