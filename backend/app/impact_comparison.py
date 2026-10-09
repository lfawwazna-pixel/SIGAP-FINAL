"""Reproducible paired experiments; no predetermined benefit or live commands."""
from datetime import datetime, timezone
from hashlib import sha256
import json, random
from math import sqrt
from statistics import mean, stdev
from uuid import uuid4
from contracts.analytics import ComparisonInput, ComparisonReport, DemandProvenance, PairedRun, PairedMetric, Reference
from backend.app.impact_queue import Arrival, QueueExperiment, DIRECTIONS, KINDS, MOVEMENTS

T95 = (2.776,2.571,2.447,2.365,2.306,2.262,2.228,2.201,2.179,2.160,2.145,2.131,2.120,2.110,2.101,2.093,2.086,2.080,2.074,2.069,2.064,2.060,2.056,2.052,2.048,2.045)
METRICS = ('average_wait_seconds','queue_vehicles','queue_meters_estimate','maximum_lane_queue_meters','co2_kg','idle_fuel_liters','fuel_cost_rupiah','time_cost_rupiah','completed_vehicles','cost')
REFERENCES = [
    Reference(title='Polban · simpang Soekarno Hatta–Ibrahim Adjie (2025)', url='https://jurnal.polban.ac.id/proceeding/article/view/6701/4025', use='Tabel 7: hijau U 85, T 150, S 95, B 100 detik; kuning 3 dan semua merah 2 detik. Urutan U–T–S–B adalah desain proyek. Konfigurasi ATCS lapangan terkini belum dikonfirmasi.'),
    Reference(title='FHWA · Traffic Signal Timing Manual, Chapter 3', url='https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm', use='Dasar vehicle-seconds, headway dan startup lost time. Model proyek menghitung waktu dalam antrean; bukan seluruh control delay HCM.'),
    Reference(title='FHWA · Evaluating Adaptive Signal Control, Chapter 3', url='https://ops.fhwa.dot.gov/publications/fhwahop13031/chap3.htm', use='Evaluasi berpasangan dengan kondisi setara; manfaat bergantung pada baseline dan pola arus.'),
    Reference(title='DOE AFDC · PREP methodology, Table 5', url='https://afdc.energy.gov/prep/prep_methodology.html', use='Referensi idle mobil bensin 0,23 US gal/jam dan diesel berat 0,8 US gal/jam, dikonversi ke liter. Motor 0,2 L/jam serta pemetaan bus/truk ke diesel berat adalah asumsi proyek, belum kalibrasi lokal.'),
    Reference(title='EPA · Greenhouse Gas Equivalencies', url='https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator-calculations-and-references', use='Faktor pembakaran sekitar 2,35 kg CO₂/L bensin dan 2,69 kg CO₂/L diesel. Jenis bahan bakar kendaraan tidak dapat dipastikan dari kelas YOLO.'),
    Reference(title='TomTom · Flow Segment Data', url='https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data', use='Kecepatan, waktu perjalanan, confidence, dan ruas. Dipakai sebagai konteks ruas; tidak menyediakan jumlah kedatangan atau konfigurasi fase ATCS untuk eksperimen ini.')]


def arrival_schedule(spec):
    generator, observation = random.Random(spec.seed), random.Random(spec.seed ^ 0x51A9)
    result = []
    for direction in DIRECTIONS:
        rate = spec.demand_per_minute[direction]
        if not rate:
            continue
        mix = spec.approach_composition.get(direction)
        classes, turns = (mix.class_mix, mix.turn_mix) if mix else (spec.class_mix, spec.turn_mix)
        at = generator.expovariate(rate/60)
        while at <= spec.warmup_seconds+spec.duration_seconds:
            movement = generator.choices(MOVEMENTS, [turns[m] for m in MOVEMENTS])[0]
            kind = generator.choices(KINDS, [classes[k] for k in KINDS])[0]
            result.append((at, direction, movement, kind))
            at += generator.expovariate(rate/60)
    return [Arrival(i, *v, observation.random()) for i, v in enumerate(sorted(result))]


def metric_summary(runs):
    summaries = []
    for key in METRICS:
        def value(point):
            return point.fuel_cost_rupiah+point.time_cost_rupiah if key == 'cost' else getattr(point, key)
        a, b = [value(r.atcs) for r in runs], [value(r.sigap) for r in runs]
        differences = [y-x if key == 'completed_vehicles' else x-y for x,y in zip(a,b)]
        improvement = mean(differences)
        margin = T95[len(runs)-5]*stdev(differences)/sqrt(len(runs))
        lower, upper = improvement-margin, improvement+margin
        status = 'equal' if all(abs(v) < 1e-8 for v in differences) else 'better' if lower > 0 else 'worse' if upper < 0 else 'inconclusive'
        summaries.append(PairedMetric(key=key, atcs_mean=mean(a), sigap_mean=mean(b), improvement_mean=improvement,
            improvement_percent=improvement/mean(a)*100 if mean(a) else None,
            lower_95=lower, upper_95=upper, result=status))
    return summaries


def simulate(spec: ComparisonInput, config, provenance=None):
    runs, representative, intervals, engine = [], [], [], None
    for index in range(spec.replications):
        run_spec = spec.model_copy(update={'seed':(spec.seed+index) % 2147483648})
        arrivals = arrival_schedule(run_spec)
        digest = sha256(json.dumps([(v.at,v.direction,v.movement,v.kind) for v in arrivals], separators=(',',':')).encode()).hexdigest()
        arms, approaches = [], []
        for strategy in ('ATCS','SIGAP'):
            engine = QueueExperiment(run_spec, config, arrivals, strategy, keep_series=index == 0)
            points, by_approach = engine.run()
            arms.append(points)
            approaches.append(by_approach)
            if index == 0:
                intervals.extend(engine.intervals)
        runs.append(PairedRun(seed=run_spec.seed, arrival_schedule_sha256=digest, atcs=arms[0][-1], sigap=arms[1][-1],
            atcs_by_approach=approaches[0], sigap_by_approach=approaches[1]))
        if index == 0:
            representative = arms
    return ComparisonReport(id=str(uuid4()), intersection_id=config.intersection_id, created_at=datetime.now(timezone.utc),
        title='ATCS waktu tetap vs SIGAP · eksperimen berpasangan', input=spec, method_version='queue-v2', runs=runs,
        metrics=metric_summary(runs), references=REFERENCES, demand_provenance=provenance or DemandProvenance(source='manual_scenario'),
        arrival_schedule_sha256=runs[0].arrival_schedule_sha256, total_scheduled_arrivals=runs[0].atcs.arrivals,
        atcs=representative[0], sigap=representative[1], phase_intervals=intervals,
        baseline_basis=config.provenance.timing_basis, baseline_field_verified=config.provenance.current_field_configuration_verified,
        baseline_green_seconds=config.fixed_time.green_seconds, yellow_seconds=config.fixed_time.yellow_seconds,
        all_red_seconds=config.fixed_time.all_red_min_seconds, adaptive_policy=engine.policy.config, assumptions=[
            'Model FIFO dengan waktu kejadian tepat: luas di bawah antrean diintegrasikan sebelum setiap kedatangan, keberangkatan dan pergantian fase.',
            'Kedua strategi memakai identitas, waktu datang, kelas, arah, belokan, headway dan startup yang sama pada setiap seed. SIGAP memakai AdaptivePolicy aplikasi beserta batas hijau dan guard video.',
            'Warmup memakai kedatangan yang sama. Antrean awal setelah warmup bisa berbeda akibat strategi; seluruh kendaraan awal dan yang datang dalam jendela uji ikut denominator. Waktu sebelum warmup dikecualikan.',
            'Tunggu rata-rata = vehicle-seconds dalam antrean / (antrean awal + kedatangan). Kendaraan belum selesai tetap ikut. Ini rata-rata terbatas pada jendela pengamatan, bukan waktu tunggu penuh hingga semua kendaraan selesai atau seluruh control delay.',
            'Kartu memakai rata-rata semua ulangan. Interval 95% berasal dari selisih pasangan seed menggunakan Student t; hanya variasi keacakan skenario, bukan seluruh ketidakpastian lapangan. Grafik memperlihatkan seed pertama.',
            'Motor berturut-turut dapat berbagi hingga tiga posisi dalam satu baris FIFO. Bus/truk memakai ruang dan headway sesuai profil kelas. Panjang total adalah gabungan lajur; maksimum satu lajur dilaporkan terpisah. Ukuran, headway dan paralel motor merupakan asumsi.',
            'Fraksi deteksi adalah uji sensitivitas, bukan recall YOLO yang sudah diukur. Identitas yang tidak teramati tidak menyumbang count ataupun waktu tunggu tertua.',
            'Profil zona menghitung identitas kendaraan biasa yang baru masuk wilayah kalibrasi setelah frame awal. Laju ini adalah kedatangan teramati; occlusion, perubahan ID dan zona yang memotong arus dapat menimbulkan bias. Pengulangan rekaman tidak menjadi data lapangan independen.',
            'Antrean berada pada area pelayanan; lajur kiri bebas diasumsikan lancar setelah headway. Model belum memuat percepatan, konflik geometris, jaringan, spillback keluar zona, kendaraan bermesin mati, ataupun prioritas EVP.',
            'BBM = jumlah vehicle-seconds per kelas / 3600 × laju idle kelas; CO₂ memakai faktor bensin/diesel. Biaya BBM memakai harga asumsi per bahan bakar; biaya waktu memakai nilai per kendaraan-jam, bukan per penumpang.',
            'Faktor idle AFDC dan faktor pembakaran EPA adalah referensi, belum kalibrasi armada Bandung. Harga BBM dan nilai waktu dapat diubah; bukan harga terkini. Emisi yang dilaporkan hanya estimasi idle, bukan total atau penurunan emisi aktual.',
            'Baseline ATCS adalah waktu tetap proyek dari penelitian Polban, bukan bukti bahwa semua ATCS memakai waktu tetap atau konfigurasi lapangan saat ini. TomTom hanya konteks ruas; tidak diubah menjadi arus kendaraan atau bukti manfaat SIGAP.',
            'Hasil lebih baik, sama, lebih buruk atau belum konsisten tetap ditampilkan tanpa memilih seed yang menguntungkan. Respons EVP dan keselamatan tidak dievaluasi oleh eksperimen dampak ini.'])
