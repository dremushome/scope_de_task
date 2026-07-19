from contextlib import asynccontextmanager
from fastapi import FastAPI
from dwh.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is present upon API startup
    init_db()
    yield

from fast_api.routers import companies, snapshots, uploads

app = FastAPI(
    title="Corporate Credit Rating Data API",
    description="REST API exposing corporate metadata and rating Snapshots",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(companies.router)
app.include_router(snapshots.router)
app.include_router(uploads.router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Corporate Credit Rating API",
        "docs_url": "/docs",
        "status": "online"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
