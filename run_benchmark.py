"""Time every filter and format on a synthetic image, in-process or against a running server.

    python run_benchmark.py                       # in-process pipeline
    python run_benchmark.py --url http://localhost:8000   # through HTTP (e.g. Docker Compose)
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

from src.image_ops import Filter, OutputFormat
from src.pipeline import ProcessRequest, process

RESULTS = Path(__file__).resolve().parent / "benchmarks" / "results" / "latest.md"


def synthetic_image(width: int, height: int) -> bytes:
    rng = np.random.default_rng(525)
    y, x = np.mgrid[0:height, 0:width]
    base = (127 + 100 * np.sin(x / 37.0) * np.cos(y / 23.0)).astype(np.uint8)
    img = np.dstack([base, np.roll(base, 40, axis=1), np.roll(base, 80, axis=0)])
    img = cv2.add(img, rng.integers(0, 25, size=img.shape, dtype=np.uint8))
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def bench_local(data: bytes, req: ProcessRequest, repeats: int) -> tuple[float, int]:
    times, out_bytes = [], 0
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = process(data, req, max_pixels=100_000_000)
        times.append((time.perf_counter() - t0) * 1000)
        out_bytes = result.output_bytes
    return statistics.median(times), out_bytes


def bench_http(url: str, data: bytes, req: ProcessRequest, repeats: int) -> tuple[float, int]:
    import httpx

    form = {"filter": req.filter.value, "format": req.format.value}
    if req.max_side:
        form["max_side"] = str(req.max_side)
    times, out_bytes = [], 0
    with httpx.Client(base_url=url, timeout=60) as client:
        for _ in range(repeats):
            resp = client.post("/v1/process", files={"file": ("in.png", data, "image/png")}, data=form)
            resp.raise_for_status()
            times.append(float(resp.headers["X-Process-Time-Ms"]))
            out_bytes = int(resp.headers["X-Output-Bytes"])
    return statistics.median(times), out_bytes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Benchmark a running server instead of the in-process pipeline")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    data = synthetic_image(args.width, args.height)
    cases = [ProcessRequest(filter=f, format=OutputFormat.jpeg) for f in Filter]
    cases += [ProcessRequest(format=fmt) for fmt in (OutputFormat.png, OutputFormat.webp)]
    cases.append(ProcessRequest(max_side=640))

    mode = f"HTTP {args.url}" if args.url else "in-process"
    lines = [
        f"Input {args.width}x{args.height} PNG, {len(data)} bytes, median of {args.repeats} runs, {mode}.",
        "",
        "| filter | format | resize | median ms | output bytes |",
        "|---|---|---|---:|---:|",
    ]
    for req in cases:
        if args.url:
            ms, out = bench_http(args.url, data, req, args.repeats)
        else:
            ms, out = bench_local(data, req, args.repeats)
        resize = f"max_side={req.max_side}" if req.max_side else "-"
        lines.append(f"| {req.filter.value} | {req.format.value} | {resize} | {ms:.2f} | {out} |")

    report = "\n".join(lines)
    print(report)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(report + "\n")
    print(f"\nWrote {RESULTS}")


if __name__ == "__main__":
    main()
