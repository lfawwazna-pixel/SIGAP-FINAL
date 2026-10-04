from contextlib import asynccontextmanager
from uuid import UUID
import hmac

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from atcs_simulator.app.runtime import AtcsRuntime, Clock, ConflictProvider
from atcs_simulator.app.control_settings import ControlSettings
from contracts.control import ControlCommand, CommandReceipt, ControlStatus
from contracts.configuration import load_config
from contracts.models import AtcsStatus, Capabilities, DatabaseCheck, Health, IntersectionConfig, TrafficEvents
from contracts.traffic import TrafficView
from contracts.adaptive import MeasurementBatch
from adaptive.policy import measure_world


def create_app(config_path: str | None = None, *, clock: Clock | None = None,
               conflict_provider: ConflictProvider | None = None, tick_seconds: float = 0.1,
               event_capacity: int = 1000, control_settings=None, control_policy=None) -> FastAPI:
    config = load_config(config_path)
    control_settings = control_settings or ControlSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime = AtcsRuntime(config, clock=clock, conflict_provider=conflict_provider,
                              tick_seconds=tick_seconds, event_capacity=event_capacity,
                              control_settings=control_settings, control_policy=control_policy)
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(title="SIGAP · ATCS arbiter", version="0.4.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse(status_code=422, content={'detail': {'code': 'INVALID_COMMAND',
            'message': 'Bentuk perintah tidak sesuai kontrak.'}})

    def require_service(request: Request):
        expected = 'Bearer ' + control_settings.sigap_control_api_key.get_secret_value()
        if not control_settings.configured or not hmac.compare_digest(
                request.headers.get('authorization', '').encode(), expected.encode()):
            raise HTTPException(401, detail={'code': 'SERVICE_AUTH_REQUIRED', 'message': 'Identitas layanan tidak valid.'})

    @app.middleware("http")
    async def no_cached_controller_state(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health/live")
    async def live():
        return {"service": "atcs", "liveness": "alive", "stage": "4"}

    @app.get("/health", response_model=Health, responses={503: {"model": Health}})
    async def health():
        status = app.state.runtime.status()
        ready = status.availability == "available"
        report = Health(service="atcs", stage="4", foundation_ready=ready, checked_at=status.observed_at,
                        database=DatabaseCheck(status="not_required", schema_status="not_required"),
                        capabilities=Capabilities(phase_engine=status.engine_state,
                            override='available' if control_settings.configured and ready else 'unavailable'))
        return JSONResponse(report.model_dump(mode="json"), status_code=200 if ready else 503)

    @app.get("/configuration", response_model=IntersectionConfig)
    def configuration():
        return config

    @app.get("/status", response_model=AtcsStatus, responses={503: {"model": AtcsStatus}})
    async def status():
        report = app.state.runtime.status()
        return JSONResponse(report.model_dump(mode="json"),
                            status_code=200 if report.availability == "available" else 503)

    @app.get("/events", response_model=TrafficEvents)
    async def events(after: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500),
                     run_id: UUID | None = None):
        runtime = app.state.runtime
        try:
            return runtime.engine.events(at=runtime.clock.utcnow(), after=after, limit=limit, run_id=run_id)
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "CURSOR_AHEAD",
                "message": "Cursor melebihi riwayat sesi; baca dari awal dengan run_id terkini."}) from None

    @app.get('/traffic', response_model=TrafficView)
    async def traffic():
        return app.state.runtime.traffic_view()

    @app.get('/control', response_model=ControlStatus)
    async def control_status():
        return app.state.runtime.control_status()

    @app.get('/measurements', response_model=MeasurementBatch, dependencies=[Depends(require_service)])
    async def measurements():
        runtime = app.state.runtime
        batch = measure_world(runtime.traffic, config.intersection_id, runtime.engine.run_id, runtime.engine.updated_at)
        if runtime.status().availability != 'available':
            for value in batch.approaches.values():
                value.usable = False
        return batch

    @app.post('/control/commands', response_model=CommandReceipt, dependencies=[Depends(require_service)])
    async def control_command(payload: ControlCommand):
        runtime = app.state.runtime
        if runtime.status().availability != 'available':
            raise HTTPException(503, detail={'code': 'ENGINE_UNAVAILABLE', 'message': 'Mesin fase tidak operasional.'})
        receipt = runtime.engine.control.submit(payload, runtime.clock.monotonic(), runtime.clock.utcnow())
        return JSONResponse(receipt.model_dump(mode='json'), status_code=409 if receipt.outcome == 'rejected' else 200)

    @app.get('/control/receipts/{request_id}', response_model=CommandReceipt, dependencies=[Depends(require_service)])
    async def control_receipt(request_id: UUID):
        item = app.state.runtime.engine.control.receipts.get(request_id)
        if item is None:
            raise HTTPException(404, detail={'code': 'RECEIPT_NOT_FOUND', 'message': 'Tanda terima tidak ditemukan pada sesi ini.'})
        return item[1].model_copy(deep=True)

    return app


app = create_app()
