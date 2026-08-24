"""Request / response schemas for the image pipeline API."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    jpeg = "jpeg"
    png = "png"
    webp = "webp"


class FilterOp(str, Enum):
    none = "none"
    grayscale = "grayscale"
    blur = "blur"
    sharpen = "sharpen"
    denoise = "denoise"
    equalize = "equalize"


class ProcessParams(BaseModel):
    """Query / form parameters for image processing."""

    width: Optional[int] = Field(default=None, ge=1, le=8192, description="Target width in pixels")
    height: Optional[int] = Field(default=None, ge=1, le=8192, description="Target height in pixels")
    keep_aspect: bool = Field(default=True, description="Preserve aspect ratio when resizing")
    format: OutputFormat = Field(default=OutputFormat.jpeg, description="Output image format")
    quality: int = Field(default=85, ge=1, le=100, description="Encode quality for JPEG/WebP")
    filter: FilterOp = Field(default=FilterOp.none, description="Optional OpenCV filter")
    max_side: Optional[int] = Field(
        default=None,
        ge=1,
        le=8192,
        description="If set, scale so the longer side equals this value",
    )


class ImageMeta(BaseModel):
    input_width: int
    input_height: int
    output_width: int
    output_height: int
    input_bytes: int
    output_bytes: int
    format: str
    filter: str
    process_ms: float


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class OpsResponse(BaseModel):
    operations: list[str]
    formats: list[str]
