"""
FastAPI prediction service.

Loads the trained Spark MLlib PipelineModel from S3 on startup and
exposes POST /predict for delay prediction and GET /health for liveness checks.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from api.model_loader import ModelLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_S3_PATH: str = os.environ["MODEL_S3_PATH"]

# Shared model instance loaded once at startup
_model_loader: ModelLoader | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model_loader
    logger.info("Loading model from %s", MODEL_S3_PATH)
    # TODO(P4): _model_loader = ModelLoader(MODEL_S3_PATH); _model_loader.load()
    yield
    # TODO(P4): stop Spark session on shutdown if needed


app = FastAPI(title="FlightFlux Prediction API", lifespan=lifespan)


class PredictRequest(BaseModel):
    carrier: str = Field(..., example="AA")
    origin: str = Field(..., example="JFK")
    dest: str = Field(..., example="LAX")
    crs_dep_time: int = Field(..., example=1430, description="Scheduled departure time as HHMM integer")
    distance: float = Field(..., example=2475.0)
    month: int = Field(..., example=5, ge=1, le=12)


class PredictResponse(BaseModel):
    predicted_delay_minutes: float
    risk_label: Literal["low", "medium", "high"]


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    if _model_loader is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    # TODO(P4): call _model_loader.predict(request.model_dump()), return PredictResponse
    pass


if __name__ == "__main__":
    import uvicorn
    print("skeleton — not yet implemented")
    uvicorn.run("api.main:app", host=os.environ.get("API_HOST", "0.0.0.0"), port=int(os.environ.get("API_PORT", "8000")))
