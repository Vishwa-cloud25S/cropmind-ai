from fastapi import APIRouter

from app.api.v1 import analyses, farms, health, images, meta, predictions, reports, simulations, zones

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(images.router)
api_router.include_router(analyses.router)
api_router.include_router(predictions.router)
api_router.include_router(farms.router)
api_router.include_router(zones.router)
api_router.include_router(simulations.router)
api_router.include_router(reports.router)
