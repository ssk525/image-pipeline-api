"""OpenCV image operations: decode, resize, filter, encode."""

from __future__ import annotations

from enum import Enum

import cv2
import numpy as np


class ImageOpError(ValueError):
    """Raised when an image cannot be decoded, processed, or encoded."""


class Filter(str, Enum):
    none = "none"
    grayscale = "grayscale"
    blur = "blur"
    sharpen = "sharpen"
    denoise = "denoise"
    equalize = "equalize"


class OutputFormat(str, Enum):
    jpeg = "jpeg"
    png = "png"
    webp = "webp"


MEDIA_TYPES = {
    OutputFormat.jpeg: "image/jpeg",
    OutputFormat.png: "image/png",
    OutputFormat.webp: "image/webp",
}

_EXTENSIONS = {
    OutputFormat.jpeg: ".jpg",
    OutputFormat.png: ".png",
    OutputFormat.webp: ".webp",
}

_SHARPEN_KERNEL = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)


def decode(data: bytes, max_pixels: int) -> np.ndarray:
    """Decode bytes to a BGR (or BGRA) array, refusing empty, corrupt, or oversized images."""
    if not data:
        raise ImageOpError("Empty upload")
    buf = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ImageOpError("Could not decode image (supported: JPEG, PNG, WebP, BMP, TIFF)")
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    height, width = image.shape[:2]
    if height * width > max_pixels:
        raise ImageOpError(f"Image has {height * width} pixels; limit is {max_pixels}")
    return image


def target_size(
    width: int,
    height: int,
    out_width: int | None = None,
    out_height: int | None = None,
    max_side: int | None = None,
) -> tuple[int, int]:
    """Work out the output size. One side keeps aspect ratio; max_side only shrinks."""
    if out_width and out_height:
        return out_width, out_height
    if out_width:
        return out_width, max(1, round(height * out_width / width))
    if out_height:
        return max(1, round(width * out_height / height)), out_height
    if max_side and max(width, height) > max_side:
        scale = max_side / max(width, height)
        return max(1, round(width * scale)), max(1, round(height * scale))
    return width, height


def resize(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    height, width = image.shape[:2]
    if size == (width, height):
        return image
    shrinking = size[0] * size[1] < width * height
    interpolation = cv2.INTER_AREA if shrinking else cv2.INTER_CUBIC
    return cv2.resize(image, size, interpolation=interpolation)


def _split_alpha(image: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    if image.ndim == 3 and image.shape[2] == 4:
        return image[:, :, :3], image[:, :, 3]
    return image, None


def apply_filter(image: np.ndarray, name: Filter) -> np.ndarray:
    bgr, alpha = _split_alpha(image)
    if name == Filter.none:
        out = bgr
    elif name == Filter.grayscale:
        out = cv2.cvtColor(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    elif name == Filter.blur:
        out = cv2.GaussianBlur(bgr, (5, 5), 0)
    elif name == Filter.sharpen:
        out = cv2.filter2D(bgr, -1, _SHARPEN_KERNEL)
    elif name == Filter.denoise:
        out = cv2.fastNlMeansDenoisingColored(bgr, None, 7, 7, 7, 21)
    elif name == Filter.equalize:
        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        out = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
    else:
        raise ImageOpError(f"Unknown filter: {name}")
    if alpha is not None:
        out = np.dstack([out, alpha])
    return out


def encode(image: np.ndarray, fmt: OutputFormat, quality: int) -> bytes:
    params: list[int] = []
    if fmt == OutputFormat.jpeg:
        image, _ = _split_alpha(image)
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    elif fmt == OutputFormat.webp:
        params = [cv2.IMWRITE_WEBP_QUALITY, quality]
    elif fmt == OutputFormat.png:
        params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
    ok, buf = cv2.imencode(_EXTENSIONS[fmt], image, params)
    if not ok:
        raise ImageOpError(f"Could not encode as {fmt.value}")
    return buf.tobytes()
