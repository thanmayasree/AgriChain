from fastapi import APIRouter

from app.api.routes import (
    analytics,
    auth,
    batches,
    blockchain,
    demo,
    documents,
    events,
    farmers,
    health,
    iot,
    quality,
    recalls,
    risk,
    users,
    verify,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(farmers.router, prefix="/farmers", tags=["farmers"])
api_router.include_router(batches.router, prefix="/batches", tags=["batches"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(quality.router, tags=["quality"])
api_router.include_router(iot.router, tags=["iot"])
api_router.include_router(risk.router, tags=["risk"])
api_router.include_router(blockchain.router, tags=["blockchain"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(verify.router, tags=["verify"])
api_router.include_router(recalls.router, tags=["recalls"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(demo.router, tags=["demo"])
