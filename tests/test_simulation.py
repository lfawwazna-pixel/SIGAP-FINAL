from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from backend.app.accounts import create_operator
from backend.app.simulation import Experiments
from contracts.configuration import load_config
from contracts.traffic import SimulationCommand, TrafficView
from test_auth import auth_context, login, ORIGIN, PASSWORD


def test_simulation_and_traffic_require_authentication(auth_context):
    client, _, _, _ = auth_context
    assert client.get('/api/simulation').status_code == 401
    assert client.get('/api/atcs/traffic').status_code == 401
    assert client.post('/api/simulation/commands', headers=ORIGIN,
                       json={'action': 'start', 'expected_run_id': str(uuid4())}).status_code == 401


def test_commands_need_csrf_origin_and_do_not_send_atcs_requests(auth_context):
    client, app, _, _ = auth_context
    csrf = login(client).json()['csrf_token']
    async def forbidden(*args, **kwargs):
        pytest.fail('Simulation must never send ATCS commands')
    app.state.atcs_client.get = forbidden
    app.state.atcs_client.post = forbidden
    initial = client.get('/api/simulation').json()
    TrafficView.model_validate(initial)
    assert not initial['running'] and initial['time_seconds'] == 0
    body = {'action': 'spawn', 'expected_run_id': initial['run_id'], 'direction': 'U', 'kind': 'ambulance'}
    assert client.post('/api/simulation/commands', headers=ORIGIN, json=body).status_code == 403
    headers = {**ORIGIN, 'X-CSRF-Token': csrf}
    assert client.post('/api/simulation/commands', headers={**headers, 'Origin': 'https://other.invalid'}, json=body).status_code == 403
    response = client.post('/api/simulation/commands', headers=headers, json=body)
    assert response.status_code == 200
    assert len(response.json()['vehicles']) == 1
    assert response.json()['vehicles'][0]['kind'] == 'ambulance'
    assert response.json()['vehicles'][0]['y'] == -400
    assert response.json()['vehicles'][0]['distance_to_stop'] == 657
    assert response.json()['time_seconds'] == 0
    result = client.post('/api/simulation/commands', headers=headers,
                         json={'action': 'reset', 'expected_run_id': initial['run_id']}).json()
    assert result['vehicles'] == [] and result['run_id'] != initial['run_id'] and not result['running']
    assert client.post('/api/simulation/commands', headers=headers, json=body).status_code == 409


@pytest.mark.parametrize('fields', [
    {'action': 'configure', 'speed': 100}, {'action': 'configure', 'speed': None},
    {'action': 'configure', 'demand': {'U': 10}}, {'action': 'start', 'direction': 'U'},
    {'action': 'spawn', 'direction': 'U', 'kind': 'car', 'distance': 100},
    {'action': 'spawn', 'direction': 'U', 'kind': 'ambulance', 'distance': -1},
    {'action': 'spawn', 'direction': 'U', 'kind': 'ambulance', 'distance': 100},
    {'action': 'override', 'controller': 'ATCS'},
])
def test_bad_commands_cannot_mutate_state(auth_context, fields):
    client, _, _, _ = auth_context
    csrf = login(client).json()['csrf_token']
    initial = client.get('/api/simulation').json()
    response = client.post('/api/simulation/commands', headers={**ORIGIN, 'X-CSRF-Token': csrf},
                           json={**fields, 'expected_run_id': initial['run_id']})
    assert response.status_code == 422
    assert client.get('/api/simulation').json()['time_seconds'] == 0


def test_experiments_are_owned_by_account(auth_context):
    client, _, engine, _ = auth_context
    csrf = login(client).json()['csrf_token']
    initial = client.get('/api/simulation').json()
    client.post('/api/simulation/commands', headers={**ORIGIN, 'X-CSRF-Token': csrf},
                json={'action': 'spawn', 'expected_run_id': initial['run_id'], 'direction': 'U', 'kind': 'ambulance'})
    with Session(engine) as db, db.begin():
        create_operator(db, 'second.operator', 'Second Operator', PASSWORD)
    assert login(client, username='second.operator').status_code == 200
    other = client.get('/api/simulation').json()
    assert other['run_id'] != initial['run_id'] and not other['vehicles']
    login(client)
    assert len(client.get('/api/simulation').json()['vehicles']) == 1


def test_simulation_pause_speed_reset_preserves_configuration_only():
    manager = Experiments(load_config())
    key = uuid4()
    exp = manager.get(key)
    def cmd(**values):
        return manager.command(key, SimulationCommand(expected_run_id=manager.get(key).run_id, **values))
    cmd(action='configure', speed=3, strategy='fixed_time', demand=dict.fromkeys('UTSB', 0))
    cmd(action='start')
    exp.advance(.2)
    assert exp.world.time == pytest.approx(.6)
    cmd(action='pause')
    exp.advance(.2)
    assert exp.world.time == pytest.approx(.6)
    fresh = cmd(action='reset')
    assert fresh.world.time == 0 and fresh.speed == 3 and fresh.strategy == 'fixed_time'
    assert fresh.run_id != exp.run_id and not fresh.running
