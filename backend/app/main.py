"""CropMind AI API entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware

logger = logging.getLogger("cropmind.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging("DEBUG" if settings.app_env == "development" else "INFO")
    logger.info(
        "cropmind-api v%s starting (env=%s, demo_mode=%s)",
        __version__,
        settings.app_env,
        settings.demo_mode,
    )
    yield
    logger.info("cropmind-api shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CropMind AI API",
        version=__version__,
        description=(
            "Precision-agriculture decision support: crop-health imagery → explainable, "
            "geospatially localized intervention zones. Decision support only — no diagnosis "
            "certainty, no chemical dosing guidance."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Binary artifacts (report PDFs, zone exports) are downloaded via authenticated
        # fetch → blob; expose Content-Disposition so the browser can read the
        # server-set, honestly-labelled filename (simulation/report IDs travel in it).
        expose_headers=["Content-Disposition"],
    )
    app.include_router(api_router)
    return app


app = create_app()
