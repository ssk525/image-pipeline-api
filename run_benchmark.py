"""Local latency / size benchmark for README metrics."""

from __future__ import annotations

import json
from pathlib import Path

from src.image_ops import process_image
from src.schemas import FilterOp, OutputFormat, ProcessParams

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "samples" / "sample.jpg"
OUT_DIR = ROOT / "benchmarks" / "results"


def run() -> None:
    raw = SAMPLE.read_bytes()
    cases = [
        ("resize_320_jpeg", ProcessParams(width=320, height=240, format=OutputFormat.jpeg, quality=85)),
        ("thumbnail_128_webp", ProcessParams(max_side=128, format=OutputFormat.webp, quality=75)),
        ("grayscale_png", ProcessParams(max_side=256, filter=FilterOp.grayscale, format=OutputFormat.png)),
        ("denoise_jpeg", ProcessParams(max_side=320, filter=FilterOp.denoise, format=OutputFormat.jpeg, quality=80)),
        ("sharpen_jpeg", ProcessParams(max_side=320, filter=FilterOp.sharpen, format=OutputFormat.jpeg, quality=85)),
    ]

    rows = []
    for name, params in cases:
        # warm-up + timed run
        process_image(raw, params)
        result = process_image(raw, params)
        rows.append(
            {
                "case": name,
                "input_bytes": result.input_bytes,
                "output_bytes": result.output_bytes,
                "output_size": f"{result.output_width}x{result.output_height}",
                "process_ms": result.process_ms,
                "format": result.format,
                "filter": result.filter,
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "latest.json"
    out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print("| Case | Output | Bytes in → out | Latency (ms) |")
    print("|------|--------|----------------|--------------|")
    for row in rows:
        print(
            f"| {row['case']} | {row['output_size']} ({row['format']}) | "
            f"{row['input_bytes']} → {row['output_bytes']} | {row['process_ms']} |"
        )
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    run()
