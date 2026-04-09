"""
Main FastAPI application
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import os

from src.core.config import get_settings, setup_logging
from src.db.database import init_db, close_db
from src.models.schemas import HealthCheckResponse, ErrorResponse

# Configure logging
settings = get_settings()
setup_logging(settings)
logger = logging.getLogger(__name__)


# ========== LIFESPAN EVENTS ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events"""
    # Startup
    logger.info("Starting SatsRemit API")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down SatsRemit API")
    await close_db()
    logger.info("Database connection closed")


# ========== APPLICATION FACTORY ==========

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="SatsRemit API",
        description="Bitcoin Lightning Network Remittance Platform (SA → Zimbabwe)",
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )
    
    # ========== MIDDLEWARE ==========
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [
            "https://app.satsremit.com",
            "https://admin.satsremit.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Trusted hosts
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1"] if settings.debug else [
            "api.satsremit.com",
            "app.satsremit.com",
        ]
    )
    
    # ========== EXCEPTION HANDLERS ==========
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "detail": exc.detail,
                "code": f"HTTP_{exc.status_code}",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception", exc_info=exc)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc) if settings.debug else "An error occurred",
                "code": "INTERNAL_ERROR",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    
    # ========== ROUTES ==========
    
    @app.get("/health", response_model=HealthCheckResponse)
    async def health_check():
        """Health check endpoint"""
        # TODO: Check bitcoind, LND, database, redis connectivity
        return {
            "status": "healthy",
            "bitcoind_synced": True,
            "lnd_active": True,
            "db_connected": True,
            "redis_connected": True,
            "timestamp": datetime.utcnow(),
        }
    
    @app.get("/")
    async def root():
        """API root endpoint"""
        return {
            "app": "SatsRemit",
            "version": "0.1.0",
            "environment": settings.environment,
            "docs": "/api/docs" if not settings.is_production else None,
        }
    
    # ========== ROUTE IMPORTS ==========
    
    # Public routes
    from src.api.routes import public
    app.include_router(public.router, prefix="/api", tags=["public"])
    
    # Agent routes
    from src.api.routes import agent
    app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    
    # Admin routes
    from src.api.routes import admin
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    
    # Webhook routes
    from src.api.routes import webhooks
    app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
    
    logger.info(f"FastAPI application created (environment: {settings.environment})")
    
    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
