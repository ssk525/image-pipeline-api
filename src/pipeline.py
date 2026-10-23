"""One request through the pipeline: decode, resize, filter, encode, with timings."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from src import image_ops
from src.image_ops import Filter, OutputFormat


@dataclass
class ProcessRequest:
    filter: Filter = Filter.none
    format: OutputFormat = OutputFormat.jpeg
    quality: int = 90
    width: int | None = None
    height: int | None = None
    max_side: int | None = None


@dataclass
class ProcessResult:
    data: bytes
    media_type: str
    input_bytes: int
    output_bytes: int
    input_size: tuple[int, int]
    output_size: tuple[int, int]
    stage_ms: dict[str, float] = field(default_factory=dict)

    @property
    def total_ms(self) -> float:
        return sum(self.stage_ms.values())


def process(data: bytes, req: ProcessRequest, max_pixels: int) -> ProcessResult:
    stage_ms: dict[str, float] = {}

    t0 = time.perf_counter()
    image = image_ops.decode(data, max_pixels=max_pixels)
    stage_ms["decode"] = (time.perf_counter() - t0) * 1000

    in_h, in_w = image.shape[:2]
    size = image_ops.target_size(in_w, in_h, req.width, req.height, req.max_side)
    if size[0] * size[1] > max_pixels:
        raise image_ops.ImageOpError(f"Output size {size[0]}x{size[1]} exceeds the pixel limit")

    t0 = time.perf_counter()
    image = image_ops.resize(image, size)
    stage_ms["resize"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    image = image_ops.apply_filter(image, req.filter)
    stage_ms["filter"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    out = image_ops.encode(image, req.format, req.quality)
    stage_ms["encode"] = (time.perf_counter() - t0) * 1000

    out_h, out_w = image.shape[:2]
    return ProcessResult(
        data=out,
        media_type=image_ops.MEDIA_TYPES[req.format],
        input_bytes=len(data),
        output_bytes=len(out),
        input_size=(in_w, in_h),
        output_size=(out_w, out_h),
        stage_ms={k: round(v, 3) for k, v in stage_ms.items()},
    )
