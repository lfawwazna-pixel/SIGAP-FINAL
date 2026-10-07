"""Paired FIFO queue experiment, separate from operational lamps and map.

Both strategies consume the SAME pre-generated arrivals and lane movements.
No field-benefit claims or predetermined improvement percentages are produced.
"""
from collections import deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json, random
from uuid import uuid4
from adaptive.policy import AdaptivePolicy
from contracts.adaptive import MeasurementBatch
from contracts.analytics import ComparisonInput, ComparisonReport, ImpactPoint

DIRECTIONS = 'UTSB'

def arrival_schedule(spec):
    generator = random.Random(spec.seed)
    result = []
    for direction in DIRECTIONS:
        rate = spec.demand_per_minute[direction]
        if not rate: continue
        at = generator.expovariate(rate/60)
        while at<=spec.duration_seconds:
            movement = generator.choices(['left','straight','right'],[25,55,20])[0]
            result.append((round(at,5),direction,movement))
            at += generator.expovariate(rate/60)
    return sorted(result)

def simulate(spec:ComparisonInput, config):
    arrivals = arrival_schedule(spec)
    anchor = datetime(2026,1,1,tzinfo=timezone.utc)
    report = []
    for strategy in ('ATCS','SIGAP'):
        queues = {(d,m):deque() for d in DIRECTIONS for m in ('left','straight','right')}
        service = dict.fromkeys(queues,0.0)
        phase, active, deadline, fixed_next = 'all_red',None,config.fixed_time.all_red_min_seconds,0
        policy = AdaptivePolicy()
        policy.config.maximum_green = 180
        policy.baseline = config.fixed_time.green_seconds
        cursor, completed, cumulative_wait = 0,0,0.0
        points = []
        for second in range(spec.duration_seconds+1):
            now = float(second)
            while cursor<len(arrivals) and arrivals[cursor][0]<=now:
                at,d,m = arrivals[cursor]
                queues[(d,m)].append(at)
                cursor += 1
            if now>=deadline:
                if phase=='green':
                    if strategy=='ATCS': fixed_next=(fixed_next+1)%4
                    phase,deadline='yellow',now+config.fixed_time.yellow_seconds
                elif phase=='yellow':
                    phase,active,deadline='all_red',None,now+config.fixed_time.all_red_min_seconds
                else:
                    if strategy=='ATCS':
                        active=config.fixed_time.sequence[fixed_next]
                        green=config.fixed_time.green_seconds[active]
                    else:
                        at=anchor+timedelta(seconds=now)
                        measurements={}
                        for d in DIRECTIONS:
                            queued=list(queues[(d,'straight')])+list(queues[(d,'right')])
                            seen=int(len(queued)*spec.detection_fraction)
                            measurements[d]=dict(observed_at=at,usable=True,controlled_count=seen,queue_count=seen,
                                oldest_wait_seconds=max(0,now-min(queued)) if queued else 0,slip_count=len(queues[(d,'left')]),exit_available=True,
                                queue_visibility='full' if spec.detection_fraction==1 else 'partial',
                                # Detecting spillback is not guaranteed with a partial view.
                                queue_reaches_boundary=seen>=20)
                        decision=policy.choose(MeasurementBatch(intersection_id=config.intersection_id,source='recording',
                            source_session=uuid4(),sequence=second,approaches=measurements),now,at)
                        active,green=decision.approach,decision.green_seconds
                        policy.served(active,now,green)
                    phase,deadline='green',now+green
                    for movement in ('straight','right'): service[(active,movement)]=0
            for (d,m),queue in queues.items():
                permitted=m=='left' or (phase=='green' and active==d)
                if not permitted or not queue:
                    service[(d,m)]=0
                    continue
                service[(d,m)]+=1
                while queue and service[(d,m)]>=spec.discharge_headway_seconds:
                    service[(d,m)]-=spec.discharge_headway_seconds
                    queue.popleft(); completed+=1
                if not queue: service[(d,m)]=0
            # Queue vehicle-seconds includes arrivals still waiting, avoiding a
            # misleading completed-only average in a congested experiment.
            queued=sum(len(q) for q in queues.values())
            if second: cumulative_wait+=queued
            if second%15==0 or second==spec.duration_seconds:
                f=spec.factors
                fuel=cumulative_wait/3600*f.idle_liters_per_hour
                points.append(ImpactPoint(time_seconds=now,queue_vehicles=queued,queue_meters_estimate=round(queued*f.queue_spacing_meters,2),
                    average_wait_seconds=round(cumulative_wait/cursor,2) if cursor else 0,
                    cumulative_wait_vehicle_seconds=round(cumulative_wait,2),completed_vehicles=completed,arrivals=cursor,
                    idle_fuel_liters=round(fuel,5),co2_kg=round(fuel*f.co2_kg_per_liter,5),
                    fuel_cost_rupiah=round(fuel*f.fuel_rupiah_per_liter,2),time_cost_rupiah=round(cumulative_wait/3600*f.time_rupiah_per_vehicle_hour,2)))
        report.append(points)
    return ComparisonReport(id=str(uuid4()),intersection_id=config.intersection_id,created_at=datetime.now(timezone.utc),
        title='ATCS vs SIGAP · simulasi antrean dengan arus yang sama',input=spec,
        arrival_schedule_sha256=sha256(json.dumps(arrivals,separators=(',',':')).encode()).hexdigest(),
        total_scheduled_arrivals=len(arrivals),atcs=report[0],sigap=report[1],assumptions=[
            'Model antrean FIFO per lajur, langkah 1 detik; bukan pengukuran dampak di lapangan.',
            'Waktu kedatangan dan pilihan belok identik; ATCS memakai baseline persimpangan, SIGAP memakai kebijakan video yang sama dengan aplikasi.',
            'Kedatangan diasumsikan pada area antrean; waktu tempuh mendekat tidak dimodelkan. Ruas pintas dan keluaran diasumsikan lancar.',
            'Pilihan belok diasumsikan 25% kiri, 55% lurus, dan 20% kanan; satu antrean layanan per pergerakan.',
            'Tunggu rata-rata adalah waktu antre terakumulasi per seluruh kedatangan, termasuk kendaraan yang belum selesai.',
            'Panjang antrean adalah total gabungan seluruh pendekat dikali asumsi jarak; bukan panjang satu lajur atau meter hasil kalibrasi kamera.',
            'Fraksi deteksi hanya mengurangi hitungan antrean; waktu tunggu tertua diasumsikan diketahui. Kalibrasi dan kendaraan tertutup belum dimodelkan.',
            'BBM/CO2 hanya estimasi idle berbasis vehicle-seconds; harga BBM dan nilai waktu merupakan asumsi yang dapat diubah, bukan harga terkini.',
            'Faktor CO2 default setara bensin 2,35 kg/liter, diturunkan dari EPA 8.887 g/US gallon. Armada campuran belum dimodelkan.',
            'Respons darurat dan keselamatan belum dinilai; tidak ada klaim deteksi ambulans/pemadam terverifikasi.'],
        baseline_green_seconds=config.fixed_time.green_seconds,yellow_seconds=config.fixed_time.yellow_seconds,
        all_red_seconds=config.fixed_time.all_red_min_seconds,adaptive_policy=policy.config)
