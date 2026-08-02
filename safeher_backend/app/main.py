import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, users, alerts, helpers, location, ping, ai
from app.config import settings
from app.services.scheduler import run_dead_switch_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = asyncio.create_task(run_dead_switch_scheduler())
    yield
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="SafeHer API",
    description="🛡️ Women's safety backend — alerts, live location, helpers, dead man's switch",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — restrict to your domain in production
_origins = (
    ["*"]
    if settings.ENVIRONMENT == "development"
    else ["https://safeher.app", "https://api.safeher.app"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router,     prefix="/api/v1")
app.include_router(users.router,    prefix="/api/v1")
app.include_router(alerts.router,   prefix="/api/v1")
app.include_router(helpers.router,  prefix="/api/v1")
app.include_router(location.router, prefix="/api/v1")
app.include_router(ping.router,     prefix="/api/v1")
app.include_router(ai.router,       prefix="/api/v1")


@app.get("/")
def root():
    return {
        "app":     "SafeHer",
        "version": "1.0.0",
        "status":  "running 🛡️",
        "docs":    "/docs"
    }
