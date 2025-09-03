import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .config import load_settings
from .routes.generate import router as generate_router
from .routes.health import router as health_router
from .routes.stream_test import router as stream_test_router
from .routes.session import router as session_router
from .routes.chat import router as chat_router


def create_app() -> FastAPI:
    # Load environment variables from .env if present
    if os.getenv("DOTENV_DISABLED", "false").lower() not in {"1", "true", "yes"}:
        load_dotenv()

    settings = load_settings()

    app = FastAPI(title="AI Contract Generator API", version="0.2.0")

    # CORS
    cors_origins = settings.cors_allow_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(generate_router, prefix="/api")
    app.include_router(stream_test_router, prefix="/api")
    app.include_router(session_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")

    return app


