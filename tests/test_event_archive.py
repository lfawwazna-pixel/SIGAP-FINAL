from datetime import datetime,timezone
from fastapi.testclient import TestClient
from atcs_simulator.app.archive import EventArchive
from atcs_simulator.app.engine import FixedTimeEngine
from atcs_simulator.app.main import create_app
from contracts.configuration import load_config
from contracts.models import ConflictArea

AT=datetime(2026,10,7,tzinfo=timezone.utc)
def engine(archive):
    return FixedTimeEngine(load_config(),now=0,at=AT,event_capacity=2,
        conflict=ConflictArea(state='clear',source='assumed_clear',checked_at=AT),event_sink=archive.append)

def test_archive_survives_memory_eviction_and_new_runs_without_duplicates(tmp_path):
    path=tmp_path/'history.sqlite3'; archive=EventArchive(path); e=engine(archive)
    for n in range(27): e._record('phase_changed',str(n),None,None)
    archive.append(e._events[-1])
    newer=engine(archive)
    archive=EventArchive(path)
    page=archive.page(e.config.intersection_id,AT,limit=20)
    assert len(page.events)==20 and page.has_more
    assert page.events[0].run_id==newer.run_id
    older=archive.page(e.config.intersection_id,AT,before=page.next_before,limit=20)
    assert len(older.events)==9 and not older.has_more
    assert len({v.event_id for v in page.events+older.events})==29
    filtered=archive.page(e.config.intersection_id,AT,event_filter='phase',limit=100)
    assert len(filtered.events)==27

def test_archive_endpoint_is_paginated_and_reopens_after_restart(tmp_path):
    path=tmp_path/'history.sqlite3'
    with TestClient(create_app(archive_path=path)) as c:
        page=c.get('/history').json()
        assert len(page['events'])==1
        assert c.get('/history?before=0').status_code==422
        assert c.get('/history?event_filter=wrong').status_code==422
    with TestClient(create_app(archive_path=path)) as c:
        page=c.get('/history').json()
        assert len(page['events'])==3
        assert len({e['run_id'] for e in page['events']})==2

def test_archive_failure_does_not_stop_phase_control_and_is_not_reported_complete(tmp_path):
    archive=EventArchive(tmp_path/'history.sqlite3')
    archive.failed=True
    e=engine(archive)
    e.tick(now=2,at=AT,conflict=ConflictArea(state='clear',source='assumed_clear',checked_at=AT))
    assert e.phase=='green'
    import pytest
    with pytest.raises(RuntimeError): archive.page(e.config.intersection_id,AT)

def test_backend_archive_requires_operator_and_validates_upstream_identity(auth_context, tmp_path):
    import httpx
    from test_auth import login
    client, app, _, _ = auth_context
    assert client.get('/api/history').status_code==401
    login(client)
    archive=EventArchive(tmp_path/'api.sqlite3'); e=engine(archive)
    page=archive.page(e.config.intersection_id,AT).model_dump(mode='json')
    app.state.atcs_client._transport=httpx.MockTransport(lambda request:httpx.Response(200,json=page))
    assert client.get('/api/history?limit=50').status_code==200
    assert client.get('/api/history?before=0').status_code==422
    page['intersection_id']='wrong'
    assert client.get('/api/history').status_code==503


def test_archive_startup_failure_does_not_disable_controller(tmp_path):
    blocked = tmp_path/'blocked'
    blocked.write_text('not a directory', encoding='utf-8')
    with TestClient(create_app(archive_path=blocked/'events.sqlite3')) as client:
        assert client.get('/status').status_code == 200
        assert client.get('/health/live').status_code == 200
        assert client.get('/history').status_code == 503

from test_auth import auth_context
