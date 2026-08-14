from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.ai.gateway import AiGateway
from app.ai.provider import build_ai_provider
from app.api import api_router
from app.config import Settings, get_settings
from app.infrastructure.database import create_session_factory


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    active_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(
        title="思辨表达 AI 助教 API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.session_factory = create_session_factory(active_settings)
    app.state.ai_provider = build_ai_provider(
        active_settings.ai_provider,
        active_settings.deepseek_api_key,
        active_settings.deepseek_base_url,
        active_settings.deepseek_model,
    )
    app.state.ai_gateway = AiGateway(app.state.ai_provider)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[active_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready() -> JSONResponse:
        try:
            with app.state.session_factory() as session:
                session.execute(text("SELECT 1"))
            return JSONResponse({"status": "ready"})
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)

    app.include_router(api_router)
    return app


app = create_app()
