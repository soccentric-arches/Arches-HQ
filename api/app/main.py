from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import audit_log, auth, devices, users


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Arches-HQ API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(devices.router)
    app.include_router(users.router)
    app.include_router(audit_log.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
