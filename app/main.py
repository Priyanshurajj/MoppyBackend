"""
Moppy Backend — FastAPI Application Entry Point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.features.auth.router import router as auth_router
from app.features.services.router import router as services_router
from app.features.bookings.router import router as bookings_router
from app.features.cleaners.router import router as cleaners_router
from app.features.admin.router import router as admin_router
from app.features.tracking.router import router as tracking_router

app = FastAPI(
    title="Moppy API",
    description="Backend API for Moppy — Instant Home Cleaning Service",
    version="0.1.0",
)

# ── CORS (Allow Android apps on any origin during dev) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Feature Routers ──
app.include_router(auth_router)
app.include_router(services_router)
app.include_router(bookings_router)
app.include_router(cleaners_router)
app.include_router(admin_router)
app.include_router(tracking_router)

# Future routers will be added here as features are built:
# app.include_router(services_router)
# app.include_router(bookings_router)
# app.include_router(payments_router)
# app.include_router(cleaners_router)

# ── Mount Static Files (for images) ──
import os
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return {
        "app": "Moppy API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
