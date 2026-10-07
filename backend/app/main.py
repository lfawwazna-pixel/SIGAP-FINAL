from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.database import check_database, make_engine
from backend.app.auth import AuthService, require_operator, router as auth_router
from backend.app.settings import Settings
from backend.app.simulation import Experiments, router as simulation_router
from backend.app.control import ControlAdapter, router as control_router
from backend.app.adaptive import AdaptiveSender, router as adaptive_router
from backend.app.video import VideoHub, router as video_router
from backend.app.analytics import AnalyticsService, router as analytics_router
from contracts.configuration import load_config
from contracts.models import AtcsStatus, Capabilities, Health, IntersectionConfig, TrafficEvents
from contracts.traffic import TrafficView
from contracts.history import EventArchivePage
from typing import Literal


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    config = load_config(settings.sigap_config_path)
    engine = make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.atcs_client = httpx.AsyncClient(base_url=settings.sigap_atcs_base_url.rstrip("/"), timeout=3.0)
        await app.state.experiments.start()
        app.state.video.start()
        await app.state.adaptive.start(app.state.atcs_client)
        await app.state.analytics.start()
        try:
            yield
        finally:
            await app.state.analytics.stop()
            await app.state.adaptive.stop()
            await app.state.video.stop()
            await app.state.experiments.stop()
            await app.state.atcs_client.aclose()
            if engine is not None:
                engine.dispose()

    app = FastAPI(title="SIGAP · Backend", version="0.6.0", lifespan=lifespan)
    app.state.database_check = lambda: check_database(engine)
    app.state.auth = AuthService(engine, settings)
    app.include_router(auth_router)
    app.state.experiments = Experiments(config)
    app.include_router(simulation_router)
    app.state.control = ControlAdapter(settings, config.intersection_id)
    app.include_router(control_router)
    app.state.adaptive = AdaptiveSender(settings, config.intersection_id)
    app.include_router(adaptive_router)
    app.state.video = VideoHub(settings)
    app.state.adaptive.video = app.state.video
    app.include_router(video_router)
    app.state.analytics = AnalyticsService(settings, config)
    app.include_router(analytics_router)

    @app.middleware("http")
    async def private_responses(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Vary"] = "Cookie"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        # FastAPI's default validation response can echo submitted passwords.
        return JSONResponse(status_code=422, content={"detail": {"code": "INVALID_INPUT",
            "message": "Data yang dikirim tidak valid. Periksa isian dan coba kembali."}})

    @app.get("/api/health/live")
    def live():
        return {"service": "backend", "liveness": "alive", "stage": "5"}

    @app.get("/api/health", response_model=Health, responses={503: {"model": Health}}, dependencies=[Depends(require_operator)])
    def health():
        database = app.state.database_check()
        ready = database.status == "reachable" and database.schema_status == "current"
        report = Health(service="backend", stage="5", foundation_ready=ready,
                        checked_at=datetime.now(timezone.utc), database=database,
                        capabilities=Capabilities(authentication="available" if ready else "unavailable",
                            ai='available' if any(c.view().detection_ready for c in app.state.video.channels.values()) else 'unavailable' if settings.sigap_yolo_enabled else 'not_implemented',
                            cctv='configured' if settings.sigap_camera_urls else 'not_configured',
                            override='available' if ready and len(settings.sigap_control_api_key.get_secret_value()) >= 32 else 'unavailable'))
        return JSONResponse(report.model_dump(mode="json"), status_code=200 if ready else 503)

    @app.get("/api/configuration", response_model=IntersectionConfig, dependencies=[Depends(require_operator)])
    def configuration():
        return config

    async def get_atcs(path: str, model, params=None):
        try:
            response = await app.state.atcs_client.get(path, params=params)
            if response.status_code == 400 and path == "/events":
                body = response.json()
                detail = body.get("detail") if isinstance(body, dict) else None
                if isinstance(detail, dict) and detail.get("code") == "CURSOR_AHEAD":
                    raise HTTPException(status_code=400, detail={"code": "CURSOR_AHEAD",
                        "message": "Cursor melebihi riwayat sesi ATCS."})
            if response.status_code != 503 or model not in (Health, AtcsStatus):
                response.raise_for_status()
            parsed = model.model_validate(response.json())
            if isinstance(parsed, Health) and parsed.service != "atcs":
                raise ValueError("Wrong service")
            if isinstance(parsed, (AtcsStatus, TrafficEvents, TrafficView, EventArchivePage)) and parsed.intersection_id != config.intersection_id:
                raise ValueError("Wrong intersection")
            return JSONResponse(parsed.model_dump(mode="json"), status_code=response.status_code,
                                headers={"Cache-Control": "no-store"})
        except (httpx.HTTPError, ValidationError, ValueError):
            raise HTTPException(status_code=503, detail={"code": "ATCS_UNAVAILABLE",
                "message": "ATCS tidak tersedia atau respons tidak valid."}) from None

    @app.get("/api/atcs/health", response_model=Health, responses={503: {"model": Health}}, dependencies=[Depends(require_operator)])
    async def atcs_health():
        return await get_atcs("/health", Health)

    @app.get("/api/atcs/status", response_model=AtcsStatus, responses={503: {"model": AtcsStatus}}, dependencies=[Depends(require_operator)])
    async def atcs_status():
        return await get_atcs("/status", AtcsStatus)

    @app.get("/api/atcs/events", response_model=TrafficEvents, dependencies=[Depends(require_operator)])
    async def atcs_events(after: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500),
                          run_id: UUID | None = None):
        params = {"after": after, "limit": limit}
        if run_id is not None:
            params["run_id"] = str(run_id)
        return await get_atcs("/events", TrafficEvents, params)

    @app.get('/api/history', response_model=EventArchivePage, dependencies=[Depends(require_operator)])
    async def history(before: int | None = Query(default=None, ge=1), limit: int = Query(default=50, ge=1, le=100),
                      event_filter: Literal['all','phase','incident'] = 'all'):
        params = {'limit':limit,'event_filter':event_filter}
        if before is not None:
            params['before'] = before
        return await get_atcs('/history', EventArchivePage, params)

    @app.get('/api/atcs/traffic', response_model=TrafficView, dependencies=[Depends(require_operator)])
    async def atcs_traffic():
        return await get_atcs('/traffic', TrafficView)

    return app


app = create_app()
