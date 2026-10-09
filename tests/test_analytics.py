import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from backend.app.analytics import AnalyticsService, AnalyticsStore, parse_flow
from backend.app.impact_comparison import simulate
from backend.app.settings import Settings
from backend.app.traffic_forecast import forecast
from contracts.analytics import ComparisonInput, ComparisonReport, RoadPoint, TrafficSample
from contracts.configuration import load_config
from tests.test_auth import auth_context, login, ORIGIN

AT = datetime.now(timezone.utc)
POINT = RoadPoint(label='Test road',latitude=-6.945,longitude=107.64)

def sample(at=AT, direction='U', value=40, **changes):
    return TrafficSample(observed_at=at,direction=direction,current_speed_kmh=30,
        free_flow_speed_kmh=50,current_travel_seconds=90,free_flow_travel_seconds=50,
        confidence=.9,road_closed=False,congestion_percent=value,delay_seconds=40,
        segment_latitude=POINT.latitude,segment_longitude=POINT.longitude,point_distance_m=10).model_copy(update=changes)

def history(n=16, values=None):
    return [sample(AT-timedelta(seconds=120*(n-i-1)),value=values[i] if values else 40+i*.5) for i in range(n)]

def flow(point=POINT, **changes):
    return {'flowSegmentData':dict(currentSpeed=30,freeFlowSpeed=50,currentTravelTime=90,
        freeFlowTravelTime=50,confidence=.9,roadClosure=False,
        coordinates={'coordinate':[{'latitude':point.latitude-.01,'longitude':point.longitude},
                                   {'latitude':point.latitude+.01,'longitude':point.longitude}]},**changes)}

def service(tmp_path, key='test-key-never-exposed'):
    return AnalyticsService(Settings(_env_file=None,sigap_tomtom_api_key=SecretStr(key),
        sigap_analytics_store=str(tmp_path/'analytics.sqlite3')),load_config())

def test_flow_uses_polyline_projection_and_explicit_speed_ratio():
    result=parse_flow(flow(),'U',POINT,AT)
    assert result.congestion_percent==40 and result.delay_seconds==40
    assert result.point_distance_m==0  # vertices are >1 km away, actual road is not
    assert result.segment_latitude==pytest.approx(POINT.latitude)

@pytest.mark.parametrize('field,value',[('freeFlowSpeed',0),('currentSpeed',-1),('confidence',2),('roadClosure','false'),('currentSpeed',float('nan'))])
def test_invalid_provider_values_are_rejected(field,value):
    body=flow(); body['flowSegmentData'][field]=value
    with pytest.raises((ValueError,ValidationError)): parse_flow(body,'U',POINT,AT)

def test_forecast_needs_real_contiguous_samples_and_stops_at_bad_data():
    assert forecast(history(11),AT).state=='collecting'
    assert forecast(history(11),AT).points==[]
    rows=history(); rows[-3]=rows[-3].model_copy(update={'confidence':.2})
    result=forecast(rows,AT)
    assert result.state=='collecting' and result.training_samples==2 and result.points==[]
    rows=history(); rows[-2]=rows[-2].model_copy(update={'observed_at':AT-timedelta(seconds=900)})
    assert forecast(rows,AT).training_samples==1

@pytest.mark.parametrize('changes,state',[({'road_closed':True},'unavailable'),({'confidence':.1},'unavailable'),({'point_distance_m':900},'unavailable'),({'observed_at':AT-timedelta(seconds=601)},'stale'),({'observed_at':AT+timedelta(seconds=10)},'unavailable')])
def test_forecast_is_withheld_for_unusable_latest_sample(changes,state):
    rows=history(); rows[-1]=rows[-1].model_copy(update=changes)
    result=forecast(rows,AT)
    assert result.state==state and result.points==[]

def test_forecast_holdout_uses_past_only_and_exposes_baseline():
    rows=history(20,values=[25]*16+[95,95,95,95])
    result=forecast(rows,AT)
    assert result.state=='ready' and result.method=='persistence'
    assert result.baseline_mae==17.5  # 70 point surprise / four held-out targets
    assert result.validation_mae==17.5
    assert len(result.points)==15 and result.points[0].at==AT+timedelta(seconds=120)
    assert all(0<=p.lower<=p.congestion_percent<=p.upper<=100 for p in result.points)

def test_store_survives_restart_deduplicates_and_preserves_no_invented_history(tmp_path):
    store=AnalyticsStore(tmp_path/'data.sqlite3')
    store.save([sample(),sample()])
    restored=AnalyticsStore(store.path)
    assert restored.history('U')==[sample()] and restored.history('T')==[]
    report=simulate(ComparisonInput(duration_seconds=300),load_config())
    restored.save_comparison(report)
    assert AnalyticsStore(store.path).comparison(report.id)==report

def test_collector_queries_four_roads_once_and_polling_snapshots_use_cache(tmp_path):
    svc=service(tmp_path); requests=[]
    def respond(request):
        requests.append(request)
        lat,lon=map(float,request.url.params['point'].split(','))
        return httpx.Response(200,json=flow(RoadPoint(label='road',latitude=lat,longitude=lon)))
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            svc.client=client; await svc.collect(AT)
    asyncio.run(run())
    for _ in range(4):
        result=svc.snapshot(AT)
        assert result.provider_status=='connected' and len(result.roads)==4
        assert all(len(r.history)==1 and r.forecast.points==[] for r in result.roads)
    assert len(requests)==4
    assert all(r.url.host=='api.tomtom.com' and r.url.params['key']=='test-key-never-exposed' for r in requests)
    assert 'test-key-never-exposed' not in result.model_dump_json()

def test_provider_errors_keep_old_samples_mark_failure_and_redact_key(tmp_path):
    svc=service(tmp_path); svc.store.save([sample()])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(429,text='test-key-never-exposed'))) as client:
            svc.client=client; await svc.collect(AT)
    asyncio.run(run())
    result=svc.snapshot(AT)
    assert svc.backoff and result.provider_status=='unavailable'
    assert result.roads[0].latest is not None and result.roads[0].state=='error'
    assert all(r.forecast.points==[] for r in result.roads)
    assert 'test-key-never-exposed' not in result.model_dump_json()

def test_missing_key_does_not_start_network_or_break_comparison(tmp_path):
    svc=service(tmp_path,key=''); asyncio.run(svc.start())
    assert svc.client is None and svc.task is None
    assert svc.snapshot(AT).provider_status=='not_configured'
    report=asyncio.run(svc.compare(ComparisonInput(duration_seconds=300)))
    assert svc.store.comparison(report.id)==report

def test_simulation_has_same_arrivals_conserves_vehicles_and_is_reproducible():
    spec=ComparisonInput(duration_seconds=300)
    first=simulate(spec,load_config()); second=simulate(spec,load_config())
    assert first.arrival_schedule_sha256==second.arrival_schedule_sha256
    assert first.atcs==second.atcs and first.sigap==second.sigap
    assert first.atcs[-1].arrivals==first.sigap[-1].arrivals==first.total_scheduled_arrivals
    for a,b in zip(first.atcs,first.sigap):
        assert a.time_seconds==b.time_seconds and a.arrivals==b.arrivals
        assert a.arrivals+a.initial_queue_vehicles==a.queue_vehicles+a.completed_vehicles
        assert b.arrivals+b.initial_queue_vehicles==b.queue_vehicles+b.completed_vehicles
    changed=simulate(spec.model_copy(update={'seed':43}),load_config())
    assert changed.arrival_schedule_sha256!=first.arrival_schedule_sha256

def test_zero_demand_does_not_fabricate_queue_wait_or_benefit():
    report=simulate(ComparisonInput(demand_per_minute=dict.fromkeys('UTSB',0)),load_config())
    assert report.total_scheduled_arrivals==0 and report.emergency_status=='not_evaluated'
    assert all(p.queue_vehicles==p.completed_vehicles==p.co2_kg==p.average_wait_seconds==0 for p in report.atcs+report.sigap)

def test_impact_factors_are_applied_only_to_queue_vehicle_seconds():
    spec=ComparisonInput(duration_seconds=300,class_mix=dict(motorcycle=0,car=1,bus=0,truck=0),factors=dict(idle_liters_per_hour=1,co2_kg_per_liter=2,
        fuel_rupiah_per_liter=5000,time_rupiah_per_vehicle_hour=3600,queue_spacing_meters=5))
    report=simulate(spec,load_config())
    for p in [report.atcs[-1],report.sigap[-1]]:
        assert p.idle_fuel_liters==pytest.approx(p.cumulative_wait_vehicle_seconds/3600,abs=1e-5)
        assert p.co2_kg==pytest.approx(p.cumulative_wait_vehicle_seconds/1800,abs=1e-5)
        assert p.time_cost_rupiah==pytest.approx(p.cumulative_wait_vehicle_seconds,abs=.0001)
        assert p.queue_meters_estimate==p.queue_vehicles*5

@pytest.mark.parametrize('bad',[dict(duration_seconds=1801),dict(duration_seconds=300.5),dict(detection_fraction=0),dict(demand_per_minute={'U':1}),dict(demand_per_minute=dict(U=181,T=2,S=2,B=2)),dict(factors={'idle_liters_per_hour':float('inf')})])
def test_comparison_rejects_unbounded_or_ambiguous_inputs(bad):
    with pytest.raises(ValidationError): ComparisonInput(**bad)

def test_analytics_requires_login_csrf_and_exports_the_same_persisted_report(auth_context,tmp_path):
    client,app,_,_=auth_context
    app.state.analytics=service(tmp_path,key='')
    assert client.get('/api/analytics').status_code==401
    assert client.post('/api/analytics/comparison',json={}).status_code==401
    session=login(client).json()
    assert client.get('/api/analytics').status_code==200
    assert client.post('/api/analytics/comparison',headers=ORIGIN,json={}).status_code==403
    headers={**ORIGIN,'X-CSRF-Token':session['csrf_token']}
    commands=list(app.state.control.commands)
    response=client.post('/api/analytics/comparison',headers=headers,json={'duration_seconds':300})
    assert response.status_code==200
    assert list(app.state.control.commands)==commands
    report=ComparisonReport.model_validate(response.json())
    assert client.get('/api/analytics').json()['latest_comparison']['id']==report.id
    export=client.get(f'/api/analytics/comparison/{report.id}/csv')
    assert export.status_code==200 and 'ATCS,' in export.text and 'SIGAP,' in export.text
    assert report.arrival_schedule_sha256 in export.text and 'adaptive_policy' in export.text
    assert 'test-key-never-exposed' not in export.text
    assert client.get('/api/analytics/comparison/not-a-uuid/csv').status_code==422
