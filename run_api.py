"""ASGI entrypoint."""

import uvicorn

from api.app import app
from src.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("api.app:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
