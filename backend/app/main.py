
import logging

from app.routers.search import router as search_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.routers.repositories import router as repositories_router

from app.db import engine

# Ensure the ingestion stage logs are visible when Uvicorn is run from a
# terminal, even if its root logger is configured above WARNING.
logging.getLogger("app").setLevel(logging.INFO)

app = FastAPI(
    title="GenAI Portfolio API",
    description="Backend for RepoPilot and TenderLens",
    version="0.2.0",
)
app.include_router(repositories_router)
app.include_router(search_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "GenAI Portfolio API is running",
        "projects": ["RepoPilot", "TenderLens"],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "genai-portfolio-api",
    }


@app.get("/health/db")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except SQLAlchemyError:
        return {
            "status": "error",
            "database": "unavailable",
        }
