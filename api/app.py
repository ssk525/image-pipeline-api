"""FastAPI image microservice: upload an image, get it back resized, filtered, and re-encoded."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from src import __version__
from src.config import get_settings
from src.image_ops import Filter, ImageOpError, OutputFormat
from src.pipeline import ProcessRequest, ProcessResult, process

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("image_pipeline")

app = FastAPI(
    title="Image Pipeline API",
    description="Upload an image; OpenCV resizes, filters, and re-encodes it. "
    "Every response carries process time and byte-size headers.",
    version=__version__,
)


@app.middleware("http")
async def timing_and_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    response.headers["X-Request-ID"] = request_id
    log.info(
        "%s %s -> %s in %.2f ms rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


async def _read_upload(file: UploadFile) -> bytes:
    limit = settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"Upload larger than {limit} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_dims(width: int | None, height: int | None, max_side: int | None) -> None:
    for name, value in (("width", width), ("height", height), ("max_side", max_side)):
        if value is not None and not 1 <= value <= settings.max_output_side:
            raise HTTPException(
                status_code=422,
                detail=f"{name} must be between 1 and {settings.max_output_side}",
            )


async def _run(
    file: UploadFile,
    filter: Filter,
    format: OutputFormat,
    quality: int,
    width: int | None,
    height: int | None,
    max_side: int | None,
) -> ProcessResult:
    if not 1 <= quality <= 100:
        raise HTTPException(status_code=422, detail="quality must be between 1 and 100")
    _validate_dims(width, height, max_side)
    data = await _read_upload(file)
    req = ProcessRequest(
        filter=filter, format=format, quality=quality, width=width, height=height, max_side=max_side
    )
    try:
        return process(data, req, max_pixels=settings.max_pixels)
    except ImageOpError as exc:
        status = 413 if "pixel" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


def _size_headers(result: ProcessResult) -> dict[str, str]:
    return {
        "X-Input-Bytes": str(result.input_bytes),
        "X-Output-Bytes": str(result.output_bytes),
        "X-Input-Size": f"{result.input_size[0]}x{result.input_size[1]}",
        "X-Output-Size": f"{result.output_size[0]}x{result.output_size[1]}",
        "X-Pipeline-Ms": f"{result.total_ms:.2f}",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name, "version": __version__}


@app.get("/v1/ops")
def ops() -> dict:
    return {
        "filters": [f.value for f in Filter],
        "formats": [f.value for f in OutputFormat],
        "resize": ["width", "height", "max_side"],
        "limits": {
            "max_upload_bytes": settings.max_upload_bytes,
            "max_pixels": settings.max_pixels,
            "max_output_side": settings.max_output_side,
        },
    }


@app.post("/v1/process")
async def process_image(
    file: UploadFile = File(...),
    filter: Filter = Form(Filter.none),
    format: OutputFormat = Form(OutputFormat.jpeg),
    quality: int = Form(settings.default_quality),
    width: int | None = Form(None),
    height: int | None = Form(None),
    max_side: int | None = Form(None),
) -> Response:
    result = await _run(file, filter, format, quality, width, height, max_side)
    return Response(content=result.data, media_type=result.media_type, headers=_size_headers(result))


@app.post("/v1/process/meta")
async def process_meta(
    file: UploadFile = File(...),
    filter: Filter = Form(Filter.none),
    format: OutputFormat = Form(OutputFormat.jpeg),
    quality: int = Form(settings.default_quality),
    width: int | None = Form(None),
    height: int | None = Form(None),
    max_side: int | None = Form(None),
) -> JSONResponse:
    result = await _run(file, filter, format, quality, width, height, max_side)
    body = {
        "filter": filter.value,
        "format": format.value,
        "input_bytes": result.input_bytes,
        "output_bytes": result.output_bytes,
        "input_size": list(result.input_size),
        "output_size": list(result.output_size),
        "stage_ms": result.stage_ms,
        "pipeline_ms": round(result.total_ms, 3),
    }
    return JSONResponse(body, headers=_size_headers(result))
