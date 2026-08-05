from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import __version__
from .activity_notification_api import create_activity_notification_router
from .auth_api import create_auth_router
from .collection_api import create_collection_api_router
from .collection_correction_api import create_collection_correction_router
from .collection_void_api import create_collection_void_router
from .collector_route_api import create_collector_route_router
from .config import get_settings
from .cross_remittance_api import create_cross_remittance_router
from .database import database_ready
from .management_api import create_management_router
from .notification_api import create_notification_router
from .other_area_api import create_other_area_router
from .remittance_api import create_remittance_router
from .remittance_photo_api import create_remittance_photo_router


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

    app.include_router(create_auth_router())
    app.include_router(create_management_router())
    app.include_router(create_collector_route_router())
    app.include_router(create_other_area_router())
    app.include_router(create_collection_api_router())
    app.include_router(create_collection_correction_router())
    app.include_router(create_collection_void_router())
    app.include_router(create_remittance_router())
    app.include_router(create_cross_remittance_router())
    app.include_router(create_notification_router())
    app.include_router(create_activity_notification_router())
    app.include_router(create_remittance_photo_router())
    return app


app = create_app()
