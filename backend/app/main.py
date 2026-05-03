from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — Phase 3 will add Redis connection here
    yield
    # shutdown — Phase 3 will add Redis cleanup here


app = FastAPI(lifespan=lifespan)

# CORS — add now per CONTEXT.md; tested fully in Phase 5
# IMPORTANT: never use allow_origins=["*"] with allow_credentials=True — FastAPI rejects this
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
