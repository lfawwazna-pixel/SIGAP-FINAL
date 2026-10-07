"""Cached TomTom collector, local forecasts and a separate impact experiment."""
import asyncio
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta, timezone
from io import StringIO
from math import cos, hypot, radians
from pathlib import Path
import csv, json, sqlite3
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from contracts.analytics import AnalyticsView, RoadPoint, RoadAnalytics, TrafficSample, ComparisonInput, ComparisonReport
from backend.app.auth import error, require_operator
from backend.app.mutations import require_mutation
from backend.app.traffic_forecast import forecast
from backend.app.impact_comparison import simulate

class AnalyticsStore:
    def __init__(self,path): self.path=Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path,timeout=.5)
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS samples(direction TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(direction,observed_at))')
                db.execute('CREATE TABLE IF NOT EXISTS comparisons(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
                yield db
        finally: db.close()

    def save(self,samples):
        with self.connect() as db:
            db.executemany('INSERT OR REPLACE INTO samples VALUES(?,?,?)',[(s.direction,s.observed_at.isoformat(),s.model_dump_json()) for s in samples])
            db.execute('DELETE FROM samples WHERE observed_at<?',((datetime.now(timezone.utc)-timedelta(hours=72)).isoformat(),))

    def history(self,direction):
        with self.connect() as db:
            rows=db.execute('SELECT payload FROM samples WHERE direction=? ORDER BY observed_at DESC LIMIT 180',(direction,)).fetchall()
        return [TrafficSample.model_validate_json(row[0]) for row in reversed(rows)]

    def comparison(self,identity=None):
        with self.connect() as db:
            row=db.execute('SELECT payload FROM comparisons WHERE id=?',(identity,)).fetchone() if identity else db.execute('SELECT payload FROM comparisons ORDER BY created_at DESC LIMIT 1').fetchone()
        return ComparisonReport.model_validate_json(row[0]) if row else None

    def save_comparison(self,report):
        with self.connect() as db:
            db.execute('INSERT INTO comparisons VALUES(?,?,?)',(report.id,report.created_at.isoformat(),report.model_dump_json()))
            db.execute('DELETE FROM comparisons WHERE id NOT IN (SELECT id FROM comparisons ORDER BY created_at DESC LIMIT 50)')

def parse_flow(body,direction,point,at):
    value=body['flowSegmentData']
    coordinates=value['coordinates']['coordinate']
    if not coordinates: raise ValueError('Missing road geometry')
    # Project onto the returned polyline, not only its vertices: a long straight
    # road can have vertices far away even when the query lies on the segment.
    scale_x=111320*cos(radians(point.latitude))
    xy=[((float(p['longitude'])-point.longitude)*scale_x,(float(p['latitude'])-point.latitude)*111320) for p in coordinates]
    candidates=list(xy)
    for a,b in zip(xy,xy[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1]
        length=dx*dx+dy*dy
        t=max(0,min(1,-(a[0]*dx+a[1]*dy)/length)) if length else 0
        candidates.append((a[0]+t*dx,a[1]+t*dy))
    nearest=min(candidates,key=lambda p:hypot(*p))
    speed,free=float(value['currentSpeed']),float(value['freeFlowSpeed'])
    if free<=0: raise ValueError('No free-flow baseline')
    closure=value['roadClosure']
    if not isinstance(closure,bool): raise ValueError('Invalid closure')
    return TrafficSample(observed_at=at,direction=direction,current_speed_kmh=speed,free_flow_speed_kmh=free,
        current_travel_seconds=value['currentTravelTime'],free_flow_travel_seconds=value['freeFlowTravelTime'],
        confidence=value['confidence'],road_closed=closure,congestion_percent=round(max(0,min(100,(1-speed/free)*100)),2),
        delay_seconds=max(0,float(value['currentTravelTime'])-float(value['freeFlowTravelTime'])),
        segment_latitude=point.latitude+nearest[1]/111320,segment_longitude=point.longitude+nearest[0]/scale_x,point_distance_m=round(hypot(*nearest),1))

class AnalyticsService:
    def __init__(self,settings,config):
        self.settings,self.config=settings,config
        self.config_error=None
        try:
            raw=json.loads(Path(settings.sigap_analytics_config).read_text(encoding='utf-8'))
            if raw['intersection_id']!=config.intersection_id or set(raw['points'])!=set('UTSB'):
                raise ValueError('Analytics points must match intersection')
            self.points={d:RoadPoint.model_validate(raw['points'][d]) for d in 'UTSB'}
        except (ValueError,KeyError,OSError,TypeError):
            self.points={}
            self.config_error='Titik analitik belum sesuai konfigurasi persimpangan; periksa traffic-analytics.json.'
        self.store=AnalyticsStore(settings.sigap_analytics_store)
        self.errors,self.client,self.task={},None,None
        self.busy=asyncio.Lock()
        self.configured=bool(settings.sigap_tomtom_api_key.get_secret_value()) and self.config_error is None
        self.backoff=False

    async def start(self):
        if not self.configured: return
        self.client=httpx.AsyncClient(timeout=6)
        self.task=asyncio.create_task(self.run(),name='regional-traffic-analytics')

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError): await self.task
        if self.client: await self.client.aclose()

    async def collect(self,at=None):
        at=at or datetime.now(timezone.utc)
        self.backoff=False
        async def road(direction,point):
            try:
                response=await self.client.get('https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/12/json',
                    params={'key':self.settings.sigap_tomtom_api_key.get_secret_value(),
                        'point':f'{point.latitude},{point.longitude}','unit':'KMPH','thickness':1})
                if response.status_code==429:
                    self.backoff=True
                    raise ValueError('Rate limit')
                response.raise_for_status()
                sample=parse_flow(response.json(),direction,point,at)
                self.errors.pop(direction,None)
                return sample
            except (httpx.HTTPError,ValueError,KeyError,TypeError):
                # Never expose upstream URLs, key, response body or exception text.
                self.errors[direction]='Sampel TomTom belum tersedia; periksa akses Traffic API, kuota, dan titik ruas.'
        samples=await asyncio.gather(*(road(d,p) for d,p in self.points.items()))
        good=[s for s in samples if s is not None]
        if good: await asyncio.to_thread(self.store.save,good)

    async def run(self):
        while True:
            try: await self.collect()
            except asyncio.CancelledError: raise
            except Exception:
                self.errors=dict.fromkeys('UTSB','Penyimpanan analitik belum tersedia; pengendali tetap bekerja.')
            await asyncio.sleep(max(600,self.settings.sigap_tomtom_poll_seconds) if self.backoff else self.settings.sigap_tomtom_poll_seconds)

    def snapshot(self,now=None):
        now=now or datetime.now(timezone.utc)
        roads=[]
        for direction,point in self.points.items():
            try: history=self.store.history(direction)
            except (sqlite3.Error,OSError,ValueError): history=[]
            latest=history[-1] if history else None
            state,message='no_data','Belum ada pengamatan TomTom untuk ruas ini.'
            if latest:
                if (now-latest.observed_at).total_seconds() < -.5: state,message='error','Waktu sampel tidak valid; kondisi sekarang belum dapat diverifikasi.'
                elif (now-latest.observed_at).total_seconds()>600: state,message='stale','Sampel terakhir lebih dari 10 menit; tidak dianggap kondisi sekarang.'
                elif latest.point_distance_m>250: state,message='error','Ruas yang dipilih TomTom terlalu jauh; sesuaikan titik pengamatan.'
                elif latest.confidence<.5: state,message='low_confidence','Keyakinan provider rendah; prediksi ditahan.'
                elif latest.road_closed: state,message='closed','Provider menandai ruas ditutup; jangan tafsirkan sebagai antrean biasa.'
                else: state,message='ready','Pengamatan ruas terdekat dari TomTom.'
            if direction in self.errors: state,message='error',self.errors[direction]
            prediction=forecast(history,now)
            if direction in self.errors:
                prediction=prediction.model_copy(update=dict(state='unavailable',method='none',points=[],message='Pengambilan data sedang gagal; prediksi ditahan.'))
            roads.append(RoadAnalytics(direction=direction,point=point,state=state,message=message,latest=latest,history=history,forecast=prediction))
        valid=sum(r.state in ('ready','closed') for r in roads)
        status='not_configured' if not self.configured else 'connected' if valid==4 else 'partial' if valid else 'unavailable'
        message=('API key TomTom belum dikonfigurasi pada backend.' if not self.configured else
            'TomTom terhubung; indeks berdasarkan rasio kecepatan, bukan jumlah kendaraan.' if valid==4 else
            'Sebagian ruas belum tersedia; data lama/tidak valid diberi tanda.' if valid else
            'Menunggu pengamatan Traffic Flow yang valid.')
        try: comparison=self.store.comparison()
        except (sqlite3.Error,OSError,ValueError): comparison=None
        stamps=[s.observed_at for r in roads for s in r.history]
        return AnalyticsView(intersection_id=self.config.intersection_id,generated_at=now,provider_status=status,
            provider_message=self.config_error or message,poll_seconds=self.settings.sigap_tomtom_poll_seconds,
            attribution='Traffic data © TomTom; indeks dan prediksi lokal SIGAP.',history_since=min(stamps) if stamps else None,
            roads=roads,latest_comparison=comparison)

    async def compare(self,spec):
        if self.busy.locked(): raise error(429,'ANALYTICS_BUSY','Satu perbandingan sedang diproses. Tunggu sebentar.')
        async with self.busy:
            report=await asyncio.to_thread(simulate,spec,self.config)
            try: await asyncio.to_thread(self.store.save_comparison,report)
            except (sqlite3.Error,OSError): raise error(503,'ANALYTICS_STORAGE','Hasil belum dapat disimpan. Pengendali tidak terpengaruh.') from None
            return report

router=APIRouter(prefix='/api/analytics',tags=['Analitik dan dampak'])

@router.get('',response_model=AnalyticsView,dependencies=[Depends(require_operator)])
def snapshot(request:Request): return request.app.state.analytics.snapshot()

@router.post('/comparison',response_model=ComparisonReport,dependencies=[Depends(require_mutation)])
async def compare(spec:ComparisonInput,request:Request): return await request.app.state.analytics.compare(spec)

@router.get('/comparison/{identity}/csv',dependencies=[Depends(require_operator)])
def export(identity:UUID,request:Request):
    try: report=request.app.state.analytics.store.comparison(str(identity))
    except (sqlite3.Error,OSError,ValueError): raise error(503,'ANALYTICS_STORAGE','Arsip perbandingan belum tersedia.') from None
    if not report: raise error(404,'COMPARISON_MISSING','Perbandingan tidak ditemukan.')
    output=StringIO(); writer=csv.writer(output)
    writer.writerow(['source','seed','duration_seconds','demand_U','demand_T','demand_S','demand_B','detection_fraction','headway_seconds','idle_liters_per_hour','co2_kg_per_liter','fuel_rupiah_per_liter','time_rupiah_per_vehicle_hour','queue_spacing_meters','arrival_schedule_sha256'])
    writer.writerow([report.source,report.input.seed,report.input.duration_seconds,*[report.input.demand_per_minute[d] for d in 'UTSB'],report.input.detection_fraction,report.input.discharge_headway_seconds,*report.input.factors.model_dump().values(),report.arrival_schedule_sha256])
    writer.writerow(['baseline_green_seconds','yellow_seconds','all_red_seconds','adaptive_policy'])
    writer.writerow([json.dumps(report.baseline_green_seconds),report.yellow_seconds,report.all_red_seconds,report.adaptive_policy.model_dump_json()])
    fields=list(report.atcs[0].model_dump())
    writer.writerow(['strategy',*fields])
    for strategy,points in [('ATCS',report.atcs),('SIGAP',report.sigap)]:
        for point in points: writer.writerow([strategy,*[point.model_dump()[f] for f in fields]])
    return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="sigap-impact-{identity}.csv"'})
