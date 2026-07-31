from fastapi import FastAPI

from . import __version__
from .config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__)

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "gilbic-backend"}

    @app.get("/api/v1/meta")
    def metadata() -> dict[str, str]:
        return {"service": "gilbic-backend", "version": __version__}

    return app


app = create_app()
