from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from atcs_simulator.app.main import create_app as create_atcs
from atcs_simulator.app.control_settings import ControlSettings
from backend.app.auth import require_operator
from test_auth import auth_context, login, ORIGIN

KEY = 'isolated-api-test-key-'*3


def observation(status, at, *, source='cctv', sender=None):
    return dict(request_id=str(uuid4()), atcs_run_id=status['atcs_run_id'], sender_id=str(sender or uuid4()),
        action='observe', issued_at=at.isoformat(), expires_at=(at+timedelta(seconds=3)).isoformat(),
        sequence=1, source=source, observations={d: dict(observed_at=at.isoformat(), usable=True) for d in 'UTSB'})


@pytest.fixture
def connected(auth_context, clock):
    client, app, _, _ = auth_context
    clock.wall_offset = (datetime.now(timezone.utc)-clock.utcnow()).total_seconds()
    settings = ControlSettings(_env_file=None, sigap_control_api_key=SecretStr(KEY))
    atcs_app = create_atcs(clock=clock, control_settings=settings)
    with TestClient(atcs_app) as atcs:
        client.portal.call(app.state.atcs_client.aclose)
        def transport(request):
            response = atcs.request(request.method, request.url.path, content=request.content, headers=dict(request.headers))
            return httpx.Response(response.status_code, json=response.json())
        app.state.atcs_client = httpx.AsyncClient(transport=httpx.MockTransport(transport), base_url='http://atcs')
        app.state.control.settings.sigap_control_api_key = SecretStr(KEY)
        yield client, app, atcs, atcs_app


def operator_request(client, action='activate'):
    state = client.get('/api/control').json()
    return dict(request_id=str(uuid4()), action=action, expected_run_id=state['atcs_run_id'], expected_revision=state['revision'])


def test_service_auth_test_source_gate_and_sanitized_schema(clock):
    with TestClient(create_atcs(clock=clock, control_settings=ControlSettings(_env_file=None, sigap_control_api_key=SecretStr(KEY)))) as atcs:
        status = atcs.get('/control').json()
        payload = observation(status, clock.utcnow(), source='integration_test')
        assert atcs.post('/control/commands', json=payload).status_code == 401
        headers = {'Authorization': f'Bearer {KEY}'}
        response = atcs.post('/control/commands', json=payload, headers=headers)
        assert response.status_code == 409 and response.json()['code'] == 'TEST_SOURCE_DISABLED'
        assert not atcs.get('/control').json()['ready']
        invalid = atcs.post('/control/commands', headers=headers, json={**payload, 'secret': KEY})
        assert invalid.status_code == 422 and KEY not in invalid.text
        assert atcs.get('/control/receipts/'+payload['request_id']).status_code == 401


def test_operator_auth_csrf_acceptance_duplicate_and_receipt(connected, clock):
    client, app, atcs, _ = connected
    assert client.get('/api/control').status_code == 401
    assert client.get('/api/control/receipts/'+str(uuid4())).status_code == 401
    view = login(client).json()
    payload = observation(atcs.get('/control').json(), clock.utcnow())
    assert atcs.post('/control/commands', headers={'Authorization': f'Bearer {KEY}'}, json=payload).status_code == 200
    body = operator_request(client)
    assert client.post('/api/control/commands', headers=ORIGIN, json=body).status_code == 403
    assert client.post('/api/control/commands', headers={'X-CSRF-Token': view['csrf_token']}, json=body).status_code == 403
    headers = {**ORIGIN, 'X-CSRF-Token': view['csrf_token']}
    response = client.post('/api/control/commands', headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['outcome'] == 'accepted'
    duplicate = client.post('/api/control/commands', headers=headers, json=body)
    assert duplicate.json()['duplicate'] is True
    assert duplicate.json()['session_id'] == response.json()['session_id']
    receipt = client.get('/api/control/receipts/'+body['request_id'])
    assert receipt.status_code == 200 and receipt.json()['outcome'] == 'accepted'
    assert KEY not in receipt.text and KEY not in client.get('/api/control').text
    release = client.post('/api/control/commands', headers=headers, json=operator_request(client, 'release'))
    assert release.status_code == 200 and release.json()['outcome'] == 'accepted'
    assert client.get('/api/control').json()['state'] == 'returning_atcs'


def test_stale_state_and_missing_source_are_rejected(connected, clock):
    client, app, atcs, _ = connected
    view = login(client).json()
    headers = {**ORIGIN, 'X-CSRF-Token': view['csrf_token']}
    body = operator_request(client)
    assert client.post('/api/control/commands', headers=headers, json=body).status_code == 409
    atcs.post('/control/commands', headers={'Authorization': f'Bearer {KEY}'}, json=observation(atcs.get('/control').json(), clock.utcnow()))
    response = client.post('/api/control/commands', headers=headers, json=body)
    assert response.json()['detail']['code'] == 'STATE_CHANGED'


def test_monitor_only_account_cannot_control(connected):
    client, app, _, _ = connected
    view = login(client).json()
    from backend.app.auth import COOKIE_NAME
    principal = app.state.auth.current(client.cookies[COOKIE_NAME])
    principal = replace(principal, operator=principal.operator.model_copy(update={'permissions': ['monitor:read']}))
    app.dependency_overrides[require_operator] = lambda: principal
    result = client.post('/api/control/commands', headers={**ORIGIN, 'X-CSRF-Token': view['csrf_token']}, json=operator_request(client))
    assert result.status_code == 403 and result.json()['detail']['code'] == 'ACCESS_DENIED'


def test_sandbox_commands_do_not_touch_control_authority(connected):
    client, _, atcs, _ = connected
    view = login(client).json()
    original = atcs.get('/control').json()
    simulation = client.get('/api/simulation').json()
    for action in ('start', 'pause', 'reset'):
        response = client.post('/api/simulation/commands', headers={**ORIGIN, 'X-CSRF-Token': view['csrf_token']},
            json=dict(action=action, expected_run_id=simulation['run_id']))
        assert response.status_code == 200
    current = atcs.get('/control').json()
    assert (current['atcs_run_id'], current['revision'], current['state']) == (original['atcs_run_id'], original['revision'], 'fixed_time')


def test_transport_timeout_does_not_report_applied_and_retry_is_idempotent(connected, clock):
    client, app, atcs, _ = connected
    view = login(client).json()
    atcs.post('/control/commands', headers={'Authorization': f'Bearer {KEY}'}, json=observation(atcs.get('/control').json(), clock.utcnow()))
    client.portal.call(app.state.atcs_client.aclose)
    lose_response = True
    def transport(request):
        nonlocal lose_response
        response = atcs.request(request.method, request.url.path, content=request.content, headers=dict(request.headers))
        if request.method == 'POST' and lose_response:
            lose_response = False
            raise httpx.ReadTimeout('private-upstream-error', request=request)
        return httpx.Response(response.status_code, json=response.json())
    app.state.atcs_client = httpx.AsyncClient(transport=httpx.MockTransport(transport), base_url='http://atcs')
    body = operator_request(client)
    headers = {**ORIGIN, 'X-CSRF-Token': view['csrf_token']}
    response = client.post('/api/control/commands', headers=headers, json=body)
    assert response.status_code == 503 and response.json()['detail']['code'] == 'COMMAND_UNCONFIRMED'
    assert 'private-upstream-error' not in response.text
    session = atcs.get('/control').json()['session_id']
    retried = client.post('/api/control/commands', headers=headers, json=body)
    assert retried.status_code == 200 and retried.json()['duplicate']
    assert atcs.get('/control').json()['session_id'] == session


def test_control_proxy_rejects_wrong_intersection_and_invalid_receipt(connected):
    client, app, atcs, _ = connected
    login(client)
    snapshot = {**atcs.get('/control').json(), 'intersection_id': 'WRONG'}
    client.portal.call(app.state.atcs_client.aclose)
    app.state.atcs_client = httpx.AsyncClient(base_url='http://atcs', transport=httpx.MockTransport(lambda request: httpx.Response(200, json=snapshot)))
    assert client.get('/api/control').status_code == 503
    assert client.get('/api/control/receipts/'+str(uuid4())).status_code == 503


def test_operator_release_immediately_clears_video_evp_evidence(connected, clock):
    client, app, atcs, _ = connected
    view = login(client).json()
    headers = {**ORIGIN, 'X-CSRF-Token': view['csrf_token']}
    atcs.post('/control/commands', headers={'Authorization': f'Bearer {KEY}'},
              json=observation(atcs.get('/control').json(), clock.utcnow()))
    assert client.post('/api/control/commands', headers=headers,
                       json=operator_request(client)).json()['outcome'] == 'accepted'
    adaptive = app.state.adaptive
    adaptive.video_mode = True
    adaptive.control_owned = True
    adaptive.priority_session = uuid4()
    adaptive.priority_sent = adaptive.emergency_serving = True
    adaptive.emergency.records['prior-session'] = {'hits': 3}
    adaptive.emergency.events.append('Prioritas EVP sebelumnya')
    adaptive.video.vision.focus = True
    response = client.post('/api/control/commands', headers=headers,
                           json=operator_request(client, 'release'))
    assert response.status_code == 200 and response.json()['outcome'] == 'accepted'
    assert client.get('/api/control').json()['state'] == 'returning_atcs'
    assert not adaptive.control_owned and adaptive.priority_session is None
    assert not adaptive.priority_sent and not adaptive.emergency_serving
    assert not adaptive.emergency.records and not adaptive.emergency.events
    assert adaptive.emergency.snapshot().state == 'idle'
    assert not adaptive.video.vision.focus