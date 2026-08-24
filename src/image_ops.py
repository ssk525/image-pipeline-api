"""OpenCV-backed image transform pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from src.schemas import FilterOp, OutputFormat, ProcessParams


class ImageProcessError(ValueError):
    """Raised when input bytes cannot be decoded or params are invalid."""


@dataclass
class ProcessResult:
    data: bytes
    content_type: str
    input_width: int
    input_height: int
    output_width: int
    output_height: int
    input_bytes: int
    output_bytes: int
    format: str
    filter: str
    process_ms: float


_CONTENT_TYPES = {
    OutputFormat.jpeg: "image/jpeg",
    OutputFormat.png: "image/png",
    OutputFormat.webp: "image/webp",
}


def decode_image(raw: bytes) -> np.ndarray:
    if not raw:
        raise ImageProcessError("Empty upload")
    arr = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageProcessError("Could not decode image (unsupported or corrupt file)")
    return image


def _resize(image: np.ndarray, params: ProcessParams) -> np.ndarray:
    h, w = image.shape[:2]

    if params.max_side is not None:
        scale = params.max_side / max(h, w)
        if scale < 1.0 or (params.width is None and params.height is None):
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)

    if params.width is None and params.height is None:
        return image

    target_w = params.width
    target_h = params.height

    if params.keep_aspect:
        if target_w is not None and target_h is not None:
            scale = min(target_w / w, target_h / h)
            target_w = max(1, int(round(w * scale)))
            target_h = max(1, int(round(h * scale)))
        elif target_w is not None:
            scale = target_w / w
            target_h = max(1, int(round(h * scale)))
        elif target_h is not None:
            scale = target_h / h
            target_w = max(1, int(round(w * scale)))
    else:
        target_w = target_w or w
        target_h = target_h or h

    assert target_w is not None and target_h is not None
    interp = cv2.INTER_AREA if (target_w < w or target_h < h) else cv2.INTER_LINEAR
    return cv2.resize(image, (target_w, target_h), interpolation=interp)


def _apply_filter(image: np.ndarray, op: FilterOp) -> np.ndarray:
    if op == FilterOp.none:
        return image
    if op == FilterOp.grayscale:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if op == FilterOp.blur:
        return cv2.GaussianBlur(image, (5, 5), 0)
    if op == FilterOp.sharpen:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        return cv2.filter2D(image, -1, kernel)
    if op == FilterOp.denoise:
        return cv2.fastNlMeansDenoisingColored(image, None, 6, 6, 7, 21)
    if op == FilterOp.equalize:
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
    raise ImageProcessError(f"Unsupported filter: {op}")


def _encode(image: np.ndarray, fmt: OutputFormat, quality: int) -> bytes:
    if fmt == OutputFormat.jpeg:
        ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    elif fmt == OutputFormat.png:
        ok, buf = cv2.imencode(".png", image, [int(cv2.IMWRITE_PNG_COMPRESSION), 3])
    elif fmt == OutputFormat.webp:
        ok, buf = cv2.imencode(".webp", image, [int(cv2.IMWRITE_WEBP_QUALITY), int(quality)])
    else:
        raise ImageProcessError(f"Unsupported format: {fmt}")
    if not ok:
        raise ImageProcessError("Failed to encode output image")
    return buf.tobytes()


def process_image(raw: bytes, params: ProcessParams) -> ProcessResult:
    started = time.perf_counter()
    image = decode_image(raw)
    in_h, in_w = image.shape[:2]
    image = _resize(image, params)
    image = _apply_filter(image, params.filter)
    out = _encode(image, params.format, params.quality)
    out_h, out_w = image.shape[:2]
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return ProcessResult(
        data=out,
        content_type=_CONTENT_TYPES[params.format],
        input_width=in_w,
        input_height=in_h,
        output_width=out_w,
        output_height=out_h,
        input_bytes=len(raw),
        output_bytes=len(out),
        format=params.format.value,
        filter=params.filter.value,
        process_ms=round(elapsed_ms, 2),
    )
