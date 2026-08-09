from fastapi import APIRouter

from app.api.v1 import analyses, health, images, meta, predictions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(images.router)
api_router.include_router(analyses.router)
api_router.include_router(predictions.router)
