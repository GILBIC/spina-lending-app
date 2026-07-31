from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import __version__
from .config import get_settings
from .database import database_ready


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__)

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "gilbic-backend"}

    @app.get("/health/ready")
    def readiness() -> JSONResponse:
        ready = database_ready(settings)
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "unavailable",
                "service": "gilbic-backend",
                "database": "ok" if ready else "unavailable",
            },
        )

    @app.get("/api/v1/meta")
    def metadata() -> dict[str, str]:
        return {"service": "gilbic-backend", "version": __version__}

    return app


app = create_app()
