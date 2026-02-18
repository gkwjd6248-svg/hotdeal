"""API v1 router -- aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from app.api.v1 import alerts, auth, categories, comments, deals, health, ingest, products, search, shops, trending

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(deals.router, prefix="/deals", tags=["deals"])
api_v1_router.include_router(products.router, prefix="/products", tags=["products"])
api_v1_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_v1_router.include_router(shops.router, prefix="/shops", tags=["shops"])
api_v1_router.include_router(search.router, prefix="/search", tags=["search"])
api_v1_router.include_router(trending.router, prefix="/trending", tags=["trending"])
api_v1_router.include_router(comments.router, prefix="/deals", tags=["comments"])
api_v1_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_v1_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
