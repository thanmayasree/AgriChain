from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.blockchain.ledger import get_ledger
from app.core.config import ROOT, settings
from app.core.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty
from app.services.chain_service import reconcile_ledger


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    get_ledger()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        db.commit()
        reconcile_ledger(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AgriChain API",
    description="Farmer-to-customer agricultural traceability with blockchain verification",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(api_router)  # also expose without /api for spec examples

uploads = ROOT / "uploads"
uploads.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads)), name="uploads")


@app.get("/")
def root():
    from app.api.routes.health import health

    return {"name": "AgriChain", "version": "2.0.0", **health()}
