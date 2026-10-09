import { useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import viewSchema from './schemas/AnalyticsView.json'
import reportSchema from './schemas/ComparisonReport.json'
import type { AnalyticsView, ComparisonReport, RoadAnalytics } from './types/AnalyticsView'
import type { SessionView } from './types/SessionView'
import { useService } from './useService'
import { ImpactComparisonPanel } from './ImpactComparisonPanel'
export { impactChange } from './ImpactComparisonPanel'
import { directions, directionNames, localTime, type Direction } from './traffic'
import { SigapLogo } from './SigapLogo'
import { AnalyticsChart, type ChartSeries } from './AnalyticsChart'
import './analytics.css'

const ajv = new Ajv2020(); addFormats(ajv)
const viewShape = ajv.compile<AnalyticsView>(viewSchema), reportShape = ajv.compile<ComparisonReport>(reportSchema)
export function validReport(value: unknown): value is ComparisonReport {
  if (!reportShape(value)) return false
  if (value.method_version === 'queue-v2') {
    const keys = ['average_wait_seconds', 'queue_vehicles', 'queue_meters_estimate', 'maximum_lane_queue_meters', 'co2_kg', 'idle_fuel_liters', 'fuel_cost_rupiah', 'time_cost_rupiah', 'completed_vehicles', 'cost']
    if (value.runs.length !== value.input.replications || !value.demand_provenance
      || new Set(value.runs.map(r => r.seed)).size !== value.runs.length
      || keys.some(k => value.metrics.filter(m => m.key === k).length !== 1)
      || value.metrics.some(m => m.lower_95 > m.upper_95 || m.improvement_mean < m.lower_95 - 1e-8 || m.improvement_mean > m.upper_95 + 1e-8)
      || value.runs[0].arrival_schedule_sha256 !== value.arrival_schedule_sha256
      || JSON.stringify(value.runs[0].atcs) !== JSON.stringify(value.atcs.at(-1))
      || JSON.stringify(value.runs[0].sigap) !== JSON.stringify(value.sigap.at(-1))) return false
    if (value.runs.some(r => r.atcs.arrivals !== r.sigap.arrivals || [r.atcs, r.sigap].some(p => p.queue_vehicles + p.completed_vehicles !== p.arrivals + p.initial_queue_vehicles)
      || directions.some(d => !r.atcs_by_approach[d] || !r.sigap_by_approach[d]))) return false
  }
  return value.atcs.length === value.sigap.length && value.atcs[0].time_seconds === 0
    && value.atcs.at(-1)!.time_seconds === value.input.duration_seconds && value.atcs.at(-1)!.arrivals === value.total_scheduled_arrivals && value.atcs.every((a, i) => {
    const b = value.sigap[i]
    return a.time_seconds === b.time_seconds && a.arrivals === b.arrivals && a.queue_vehicles + a.completed_vehicles === a.arrivals + a.initial_queue_vehicles && b.queue_vehicles + b.completed_vehicles === b.arrivals + b.initial_queue_vehicles
      && (i === 0 || (a.time_seconds > value.atcs[i - 1].time_seconds && a.arrivals >= value.atcs[i - 1].arrivals))
  })
}
function validView(value: unknown): value is AnalyticsView {
  return viewShape(value) && new Set(value.roads.map(r => r.direction)).size === value.roads.length
    && value.roads.every(r => r.history.every((s, i) => s.direction === r.direction && (i === 0 || Date.parse(s.observed_at) > Date.parse(r.history[i - 1].observed_at))))
    && (value.latest_comparison === null || validReport(value.latest_comparison))
}
const number = (n: number, digits = 1) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: digits }).format(n)
const states: Record<RoadAnalytics['state'], string> = { ready: 'Data mutakhir', stale: 'Data lama', no_data: 'Menunggu data', low_confidence: 'Keyakinan rendah', closed: 'Ruas ditutup', error: 'Perlu diperiksa' }
const forecastLabels = { ready: 'Tersedia', collecting: 'Mengumpulkan', stale: 'Ditahan', unavailable: 'Ditahan' }
const providerLabels = { connected: '● TomTom terhubung', partial: '◌ TomTom · sebagian ruas', not_configured: '◌ TomTom belum dikonfigurasi', unavailable: '◌ TomTom · data belum tersedia' }
function current(road?: RoadAnalytics) { return road?.state === 'ready' ? road.latest : null }
export function AnalyticsPage({ session, onLogout, signingOut, logoutError }: { session: SessionView; onLogout: () => void; signingOut: boolean; logoutError: string | null }) {
  const feed = useService('/analytics', validView, true, 15000)
  const [selected, setSelected] = useState<Direction>('T'), [windowMinutes, setWindowMinutes] = useState(60)
  const view = feed.data, road = view?.roads.find(r => r.direction === selected), latest = current(road)
  const ready = view?.roads.filter(r => current(r)) ?? []
  const mean = ready.length ? ready.reduce((sum, r) => sum + r.latest!.congestion_percent, 0) / ready.length : null
  const newest = ready.length ? Math.max(...ready.map(r => Date.parse(r.latest!.observed_at))) : null
  const density: ChartSeries[] = []
  if (road) {
    const end = Date.parse(road.latest?.observed_at ?? view!.generated_at), start = end - windowMinutes * 60000
    const history = road.history.filter(s => Date.parse(s.observed_at) >= start)
    const points = history.map(s => ({ x: Date.parse(s.observed_at), y: s.confidence >= .5 && !s.road_closed && s.point_distance_m <= 250 ? s.congestion_percent : null }))
    const withGaps = points.flatMap((p, i) => i && p.x - points[i - 1].x > 360000 ? [{ x: points[i - 1].x + 1, y: null }, p] : [p])
    density.push({ label: 'Pengamatan TomTom', color: '#216db4', points: withGaps })
    if (road.forecast.state === 'ready' && latest) density.push({ label: 'Prediksi lokal · 30 menit', color: '#8657ce', dashed: true,
      points: [{ x: end, y: latest.congestion_percent }, ...road.forecast.points.map(p => ({ x: Date.parse(p.at), y: p.congestion_percent, lower: p.lower, upper: p.upper }))] })
  }
  return <>
    <a className="skip-link" href="#analytics-content">Lewati ke analitik</a>
    <header className="app-header analytics-header"><a className="brand" href="/monitor" aria-label="SIGAP — kembali ke monitor"><SigapLogo /></a><span className="header-context">Intelijen lalu lintas</span>
      <nav aria-label="Navigasi analitik"><a href="/monitor">Monitor</a><a href="/analytics" aria-current="page">Analitik &amp; dampak</a><a href="/history">Riwayat</a></nav><span className="analytics-operator">{session.operator.display_name}</span><button onClick={onLogout} disabled={signingOut}>Keluar</button></header>
    <main id="analytics-content" className="analytics-page">
      {logoutError && <p className="connection-note" role="alert">{logoutError}</p>}
      <section className="analytics-hero"><div><p className="analytics-kicker">SIGAP / KIRCON, BANDUNG</p><h1>Lihat arusnya.<br /><span>Ukur dampaknya.</span></h1><p>Pengamatan wilayah, prediksi jangka pendek, dan perbandingan kendali dalam satu ruang analitik.</p><div className="analytics-hero-links"><a href="#regional">01 · Kondisi wilayah ↓</a><a href="#impact">02 · Dampak kendali ↓</a></div></div>
        <div className="analytics-hero-status"><span className={`analytics-badge ${view?.provider_status === 'connected' ? 'is-live' : ''}`}>{view ? providerLabels[view.provider_status] : '◌ Memeriksa data TomTom'}</span><strong>{ready.length}<small> / 4</small></strong><p>ruas dengan data mutakhir</p><small>{newest ? `Sampel ${localTime(new Date(newest).toISOString())} WIB` : 'Belum ada pengamatan mutakhir'}<br />Pembaruan sumber setiap {view?.poll_seconds ?? 120} detik</small></div>
      </section>
      {feed.error && <p className="connection-note" role="alert">{feed.error} Grafik kondisi terkini ditahan sampai layanan pulih.</p>}
      <section id="regional" className="analytics-section">
        <div className="analytics-section-heading"><div><p className="analytics-kicker">01 / KONDISI WILAYAH</p><h2>Kepadatan &amp; kelancaran lalu lintas</h2><p>Jalan Ibrahim Adjie × Jalan Soekarno Hatta. Pilih ruas untuk melihat polanya.</p></div><button onClick={feed.refresh}>↻ Periksa data</button></div>
        <p className="analytics-provider-status" role="status">{view?.provider_message ?? 'Memeriksa sumber pengamatan wilayah…'}</p>
        <div className="analytics-stat-row"><div><span>Indeks kemacetan wilayah</span><strong>{mean === null ? '—' : number(mean)}<small>%</small></strong><p>{ready.length ? `Rata-rata ${ready.length} ruas yang valid` : 'Menunggu data sumber'}</p></div><div><span>Kecepatan · {directionNames[selected]}</span><strong>{latest ? number(latest.current_speed_kmh) : '—'}<small>km/jam</small></strong><p>Acuan lancar {latest ? number(latest.free_flow_speed_kmh) : '—'} km/jam</p></div><div><span>Tambahan waktu ruas</span><strong>{latest ? number(latest.delay_seconds) : '—'}<small>dtk</small></strong><p>Waktu ruas dikurangi acuan lancar</p></div><div><span>Prediksi lokal</span><strong className="analytics-word-stat">{road ? forecastLabels[road.forecast.state] : 'Mengumpulkan'}</strong><p>{road?.forecast.training_samples ?? 0} sampel · minimal 12 berurutan</p></div></div>
        <div className="analytics-regional-grid"><section className="analytics-card analytics-flow-card" aria-label="Grafik kondisi wilayah"><div className="analytics-card-heading"><div><h3>Indeks kemacetan · {directionNames[selected]}</h3><p>0% mendekati kecepatan lancar · 100% mendekati berhenti</p></div><label>Riwayat<select aria-label="Jendela riwayat TomTom" value={windowMinutes} onChange={e => setWindowMinutes(Number(e.target.value))}><option value="30">30 menit</option><option value="60">1 jam</option><option value="180">3 jam</option></select></label></div>
          <AnalyticsChart title={`Indeks kemacetan ${directionNames[selected]}`} unit="%" maximum={100} series={density} xLabel={x => new Intl.DateTimeFormat('id-ID', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit' }).format(new Date(x))} />
          <div className="analytics-source-note"><strong>Traffic data © TomTom.</strong> Indeks = 100 × (1 − kecepatan / kecepatan lancar), dibatasi 0–100%. Ini indikator kemacetan, bukan jumlah kendaraan atau kepadatan kendaraan/km. Data wilayah saat ini terpisah dari waktu rekaman CCTV.</div>
        </section><aside className="analytics-card analytics-forecast"><span className="analytics-icon">↗</span><p className="analytics-kicker">PREDIKSI AI / MODEL LOKAL</p><h3>Arah pola berikutnya</h3><p>{road?.forecast.message ?? 'Prediksi menunggu layanan analitik.'}</p><div className="forecast-facts"><span>Metode<strong>{road?.forecast.method === 'ridge_ar2' ? 'Regresi AR(2)' : road?.forecast.method === 'persistence' ? 'Nilai terakhir' : 'Belum tersedia'}</strong></span><span>Galat uji kronologis<strong>{road?.forecast.validation_mae == null ? '—' : `${number(road.forecast.validation_mae)} poin %`}</strong></span></div><p className="analytics-fine-print">Model statistik lokal dibandingkan dengan baseline nilai terakhir. Area berwarna adalah rentang galat heuristik; belum menjadi interval keyakinan 95% atau prediksi yang tervalidasi lapangan.</p></aside></div>
        <div className="analytics-road-grid">{directions.map(d => { const r = view?.roads.find(v => v.direction === d), sample = current(r); return <button key={d} className="analytics-road" aria-pressed={selected === d} onClick={() => setSelected(d)}><span className="analytics-road-code">{d}</span><span><strong>{directionNames[d]}</strong><small>{r?.point.label ?? 'Memeriksa ruas'}</small></span><b>{sample ? `${number(sample.congestion_percent)}%` : '—'}</b><span className={`analytics-road-state ${r?.state === 'ready' ? 'is-live' : ''}`}>{r ? states[r.state] : 'Menunggu data'}</span></button> })}</div>
        {road && <details className="analytics-method"><summary>Posisi ruas &amp; kualitas pengamatan {directionNames[selected]}</summary><p>{road.message} Titik permintaan {road.point.latitude.toFixed(5)}, {road.point.longitude.toFixed(5)}. {road.latest ? `Keyakinan provider ${number(road.latest.confidence * 100)}%; jarak ke ruas terpilih ${number(road.latest.point_distance_m)} m; sampel ${localTime(road.latest.observed_at)} WIB.` : ''}</p><p>Ruas terdekat dapat mencakup jalan layang/ruas lain di simpang. Periksa titik sebelum menafsirkannya sebagai lajur yang dikendalikan. TomTom tidak dipakai untuk mengubah lampu.</p></details>}
      </section>
      <ImpactComparisonPanel view={view} session={session} refresh={feed.refresh} validReport={validReport} />
      <footer className="analytics-footer"><span>SIGAP · Analitik dengan sumber dan asumsi yang terlihat</span><span>Traffic data © TomTom · waktu WIB</span></footer>
    </main>
  </>
}
