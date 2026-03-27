from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.api.routes.appointments import router as appointments_router
from backend.src.api.routes.auth import router as auth_router
from backend.src.api.routes.cabinets import router as cabinets_router
from backend.src.api.routes.calls import router as calls_router
from backend.src.api.routes.health import router as health_router
from backend.src.api.routes.usage import router as usage_router
from backend.src.api.webhooks.telnyx_webhook import router as telnyx_router
from backend.src.api.websockets.audio_ws import router as audio_ws_router
from backend.src.infrastructure.config.settings import settings
from backend.src.infrastructure.logging_config import setup_logging
from backend.src.infrastructure.persistence.database import init_db

setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Declio backend — initializing database")
    init_db()
    yield
    logger.info("Shutting down Declio backend")


app = FastAPI(
    title="Declio API",
    description="Secretaire IA pour kinesitherapeutes",
    version="0.1.0",
    lifespan=lifespan,
)

cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telnyx_router)
app.include_router(appointments_router)
app.include_router(auth_router)
app.include_router(cabinets_router)
app.include_router(calls_router)
app.include_router(health_router)
app.include_router(usage_router)
app.include_router(audio_ws_router)
