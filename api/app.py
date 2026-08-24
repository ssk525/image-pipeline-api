"""FastAPI application for image processing."""

from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from src import __version__
from src.config import get_settings
from src.image_ops import ImageProcessError, process_image
from src.schemas import (
    FilterOp,
    HealthResponse,
    OpsResponse,
    OutputFormat,
    ProcessParams,
)

settings = get_settings()

app = FastAPI(
    title="Image Pipeline API",
    description="REST image processing service: resize, convert, filter (OpenCV).",
    version=__version__,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_name, version=__version__)


@app.get("/v1/ops", response_model=OpsResponse)
def list_ops() -> OpsResponse:
    return OpsResponse(
        operations=[op.value for op in FilterOp],
        formats=[fmt.value for fmt in OutputFormat],
    )


@app.post("/v1/process")
async def process(
    file: UploadFile = File(..., description="Input image (JPEG/PNG/WebP/BMP)"),
    width: int | None = Form(default=None),
    height: int | None = Form(default=None),
    keep_aspect: bool = Form(default=True),
    format: OutputFormat = Form(default=OutputFormat.jpeg),
    quality: int = Form(default=85),
    filter: FilterOp = Form(default=FilterOp.none),
    max_side: int | None = Form(default=None),
) -> Response:
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds limit of {settings.max_upload_bytes} bytes",
        )

    try:
        params = ProcessParams(
            width=width,
            height=height,
            keep_aspect=keep_aspect,
            format=format,
            quality=quality,
            filter=filter,
            max_side=max_side,
        )
        result = process_image(raw, params)
    except ImageProcessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — map unexpected failures to 400
        raise HTTPException(status_code=400, detail=f"Processing failed: {exc}") from exc

    headers = {
        "X-Process-Time-Ms": str(result.process_ms),
        "X-Input-Size": f"{result.input_width}x{result.input_height}",
        "X-Output-Size": f"{result.output_width}x{result.output_height}",
        "X-Input-Bytes": str(result.input_bytes),
        "X-Output-Bytes": str(result.output_bytes),
        "X-Filter": result.filter,
        "X-Format": result.format,
    }
    return Response(content=result.data, media_type=result.content_type, headers=headers)


@app.post("/v1/process/meta")
async def process_meta(
    file: UploadFile = File(...),
    width: int | None = Form(default=None),
    height: int | None = Form(default=None),
    keep_aspect: bool = Form(default=True),
    format: OutputFormat = Form(default=OutputFormat.jpeg),
    quality: int = Form(default=85),
    filter: FilterOp = Form(default=FilterOp.none),
    max_side: int | None = Form(default=None),
) -> JSONResponse:
    """Same pipeline as /v1/process but returns JSON metrics only (no image body)."""
    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds limit of {settings.max_upload_bytes} bytes",
        )
    try:
        params = ProcessParams(
            width=width,
            height=height,
            keep_aspect=keep_aspect,
            format=format,
            quality=quality,
            filter=filter,
            max_side=max_side,
        )
        result = process_image(raw, params)
    except ImageProcessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(
        {
            "input_width": result.input_width,
            "input_height": result.input_height,
            "output_width": result.output_width,
            "output_height": result.output_height,
            "input_bytes": result.input_bytes,
            "output_bytes": result.output_bytes,
            "format": result.format,
            "filter": result.filter,
            "process_ms": result.process_ms,
            "compression_ratio": round(result.output_bytes / max(result.input_bytes, 1), 3),
        }
    )
