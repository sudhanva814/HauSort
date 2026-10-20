from fastapi import APIRouter
from app.api.v1.endpoints import health, scrape

api_router = APIRouter()
api_router.include_router(health.router, prefix="", tags=["Health"])
api_router.include_router(scrape.router, prefix="", tags=["Scraping & Housing Ads"])
