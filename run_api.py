"""Start the API with uvicorn using settings from the environment."""

import uvicorn

from src.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("api.app:app", host=settings.host, port=settings.port)
