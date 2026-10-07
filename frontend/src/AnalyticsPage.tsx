import { useEffect, useRef, useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import viewSchema from './schemas/AnalyticsView.json'
import reportSchema from './schemas/ComparisonReport.json'
import inputSchema from './schemas/ComparisonInput.json'
import type { AnalyticsView, ComparisonInput, ComparisonReport, ImpactPoint, RoadAnalytics } from './types/AnalyticsView'
import type { SessionView } from './types/SessionView'
import { apiBase, postService, useService } from './useService'
import { authGeneration } from './authEvents'
import { directions, directionNames, localTime, type Direction } from './traffic'
import { SigapLogo } from './SigapLogo'
import { AnalyticsChart, type ChartSeries } from './AnalyticsChart'
import './analytics.css'

const ajv = new Ajv2020(); addFormats(ajv)
const viewShape = ajv.compile<AnalyticsView>(viewSchema), reportShape = ajv.compile<ComparisonReport>(reportSchema)
const inputShape = ajv.compile<ComparisonInput>(inputSchema)
export function validReport(value: unknown): value is ComparisonReport {
  return reportShape(value) && value.atcs.length === value.sigap.length && value.atcs[0].time_seconds === 0
    && value.atcs.at(-1)!.time_seconds === value.input.duration_seconds && value.atcs.at(-1)!.arrivals === value.total_scheduled_arrivals && value.atcs.every((a, i) => {
    const b = value.sigap[i]
    return a.time_seconds === b.time_seconds && a.arrivals === b.arrivals && a.queue_vehicles + a.completed_vehicles === a.arrivals && b.queue_vehicles + b.completed_vehicles === b.arrivals
      && (i === 0 || (a.time_seconds > value.atcs[i - 1].time_seconds && a.arrivals >= value.atcs[i - 1].arrivals))
  })
}
function validView(value: unknown): value is AnalyticsView {
  return viewShape(value) && new Set(value.roads.map(r => r.direction)).size === value.roads.length
    && value.roads.every(r => r.history.every((s, i) => s.direction === r.direction && (i === 0 || Date.parse(s.observed_at) > Date.parse(r.history[i - 1].observed_at))))
    && (value.latest_comparison === null || validReport(value.latest_comparison))
}
const defaults: ComparisonInput = { duration_seconds: 900, seed: 42, demand_per_minute: { U: 18, T: 32, S: 14, B: 24 }, detection_fraction: .65, discharge_headway_seconds: 2.2,
  factors: { idle_liters_per_hour: .8, co2_kg_per_liter: 2.35, fuel_rupiah_per_liter: 10000, time_rupiah_per_vehicle_hour: 20000, queue_spacing_meters: 6.5 } }
const metrics: { key: keyof ImpactPoint; label: string; unit: string; description: string }[] = [
  { key: 'average_wait_seconds', label: 'Waktu tunggu', unit: 'dtk', description: 'Waktu antre terakumulasi dibagi seluruh kedatangan, termasuk kendaraan yang masih menunggu.' },
  { key: 'queue_vehicles', label: 'Antrean', unit: 'kendaraan', description: 'Jumlah kendaraan yang sedang menunggu, dijumlahkan dari empat pendekat.' },
  { key: 'queue_meters_estimate', label: 'Panjang antrean', unit: 'm', description: 'Estimasi gabungan seluruh pendekat, bukan panjang satu lajur. Jarak per kendaraan dapat diubah.' },
  { key: 'co2_kg', label: 'Emisi CO₂', unit: 'kg', description: 'Estimasi CO₂ kumulatif selama idle. Tidak mencakup perjalanan, percepatan, atau variasi jenis kendaraan.' },
  { key: 'idle_fuel_liters', label: 'BBM idle', unit: 'L', description: 'Estimasi BBM kumulatif saat mengantre dari vehicle-seconds dan asumsi konsumsi idle.' },
  { key: 'fuel_cost_rupiah', label: 'Biaya BBM', unit: 'Rp', description: 'Estimasi biaya kumulatif dari BBM idle dan harga asumsi per liter.' },
  { key: 'time_cost_rupiah', label: 'Biaya waktu', unit: 'Rp', description: 'Estimasi nilai waktu kendaraan selama mengantre. Bukan kerugian ekonomi yang diukur di lapangan.' },
  { key: 'completed_vehicles', label: 'Kendaraan terlayani', unit: 'kendaraan', description: 'Jumlah kendaraan kumulatif yang telah keluar dari antrean dalam jendela uji.' },
]
const number = (n: number, digits = 1) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: digits }).format(n)
const minute = (n: number) => `${number(n / 60)} mnt`
const states: Record<RoadAnalytics['state'], string> = { ready: 'Data mutakhir', stale: 'Data lama', no_data: 'Menunggu data', low_confidence: 'Keyakinan rendah', closed: 'Ruas ditutup', error: 'Perlu diperiksa' }
const forecastLabels = { ready: 'Tersedia', collecting: 'Mengumpulkan', stale: 'Ditahan', unavailable: 'Ditahan' }
const providerLabels = { connected: '● TomTom terhubung', partial: '◌ TomTom · sebagian ruas', not_configured: '◌ TomTom belum dikonfigurasi', unavailable: '◌ TomTom · data belum tersedia' }
function current(road?: RoadAnalytics) { return road?.state === 'ready' ? road.latest : null }
export function impactChange(a: number, b: number, higherBetter = false) { return a === 0 ? null : (higherBetter ? b - a : a - b) / a * 100 }

export function AnalyticsPage({ session, onLogout, signingOut, logoutError }: { session: SessionView; onLogout: () => void; signingOut: boolean; logoutError: string | null }) {
  const feed = useService('/analytics', validView, true, 15000)
  const [selected, setSelected] = useState<Direction>('T'), [windowMinutes, setWindowMinutes] = useState(60)
  const [metricKey, setMetricKey] = useState<keyof ImpactPoint>('average_wait_seconds')
  const [spec, setSpec] = useState<ComparisonInput>(defaults), [generated, setGenerated] = useState<ComparisonReport | null>(null)
  const [pending, setPending] = useState(false), [message, setMessage] = useState('')
  const [invalidInput, setInvalidInput] = useState(false)
  const mounted = useRef(true), running = useRef(false)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const view = feed.data, road = view?.roads.find(r => r.direction === selected), latest = current(road)
  const report = generated ?? view?.latest_comparison, metric = metrics.find(m => m.key === metricKey)!
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
  async function compare() {
    if (running.current) return
    if (!inputShape(spec)) { setInvalidInput(true); setMessage('Periksa batas angka pada skenario. Durasi, arus, fraksi deteksi, dan faktor harus berada dalam rentang yang ditampilkan.'); return }
    setInvalidInput(false)
    running.current = true; setPending(true); setMessage('')
    const generation = authGeneration()
    try {
      const result: unknown = await postService('/analytics/comparison', session.csrf_token, spec)
      if (!validReport(result)) throw new Error('Hasil perbandingan tidak valid atau kedua arus tidak sama.')
      if (mounted.current && generation === authGeneration()) { setGenerated(result); setMessage('Perbandingan selesai dan tersimpan. Lihat hasil di bawah.'); feed.refresh() }
    } catch (cause) { if (mounted.current && generation === authGeneration()) setMessage(cause instanceof Error ? cause.message : 'Perbandingan gagal.') }
    finally { running.current = false; if (mounted.current && generation === authGeneration()) setPending(false) }
  }
  const finalA = report?.atcs.at(-1), finalB = report?.sigap.at(-1)
  const summaries = [
    { label: 'Tunggu rata-rata', key: 'average_wait_seconds', unit: 'dtk', detail: 'Operasional · seluruh kedatangan' },
    { label: 'Antrean akhir', key: 'queue_vehicles', unit: 'kendaraan', detail: 'Sosial · empat pendekat' },
    { label: 'Emisi idle', key: 'co2_kg', unit: 'kg CO₂', detail: 'Lingkungan · estimasi kumulatif' },
    { label: 'Biaya BBM + waktu', key: 'cost', unit: 'Rp', detail: 'Ekonomi · asumsi yang dapat diubah' },
  ] as const
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
      <section id="impact" className="analytics-section">
        <div className="analytics-section-heading"><div><p className="analytics-kicker">02 / DAMPAK KENDALI</p><h2>ATCS dan SIGAP, arus yang sama</h2><p>Bandingkan waktu tunggu, antrean, lingkungan, dan biaya tanpa mengubah pengendali yang sedang berjalan.</p></div><span className="analytics-badge">SIMULASI PERBANDINGAN</span></div>
        <details className="analytics-scenario" open={!report || invalidInput}><summary>Atur skenario &amp; asumsi perbandingan <span>Arus · cakupan deteksi · BBM · biaya</span></summary><div className="analytics-scenario-body">
          <div className="analytics-form-grid"><label>Durasi uji<select value={spec.duration_seconds} onChange={e => setSpec({ ...spec, duration_seconds: Number(e.target.value) })}><option value="300">5 menit</option><option value="900">15 menit</option><option value="1800">30 menit</option></select></label><label>Seed kedatangan<input type="number" min="0" max="2147483647" value={spec.seed} onChange={e => setSpec({ ...spec, seed: Number(e.target.value) })} /></label>{directions.map(d => <label key={d}>Arus {directionNames[d]} (kend/menit)<input type="number" min="0" max="60" step="1" value={spec.demand_per_minute[d]} onChange={e => setSpec({ ...spec, demand_per_minute: { ...spec.demand_per_minute, [d]: Number(e.target.value) } })} /></label>)}</div>
          <div className="analytics-form-grid"><label>Fraksi kendaraan terlihat<input type="number" min="0.1" max="1" step="0.05" value={spec.detection_fraction} onChange={e => setSpec({ ...spec, detection_fraction: Number(e.target.value) })} /></label><label>Headway pelayanan (dtk)<input type="number" min="1" max="5" step="0.1" value={spec.discharge_headway_seconds} onChange={e => setSpec({ ...spec, discharge_headway_seconds: Number(e.target.value) })} /></label>
          {([{ key: 'idle_liters_per_hour', label: 'Idle (L/kendaraan/jam)', max: 10, step: .1 }, { key: 'co2_kg_per_liter', label: 'CO₂ (kg/L)', max: 5, step: .01 }, { key: 'fuel_rupiah_per_liter', label: 'Asumsi harga BBM (Rp/L)', max: 100000, step: 100 }, { key: 'time_rupiah_per_vehicle_hour', label: 'Nilai waktu (Rp/kend/jam)', max: 1000000, step: 1000 }, { key: 'queue_spacing_meters', label: 'Jarak per kendaraan (m)', max: 20, step: .5 }] as const).map(f => <label key={f.key}>{f.label}<input type="number" min={f.key === 'queue_spacing_meters' ? 1 : 0} max={f.max} step={f.step} value={spec.factors[f.key]} onChange={e => setSpec({ ...spec, factors: { ...spec.factors, [f.key]: Number(e.target.value) } })} /></label>)}</div>
          <p className="analytics-fine-print">Angka input adalah asumsi eksperimen, termasuk fraksi deteksi dan harga BBM. Model antrean ini tidak meniru seluruh gerak kendaraan di peta dan tidak mengukur dampak nyata di lapangan.</p></div></details>
        <div className="analytics-run-bar"><button className="analytics-primary" onClick={() => void compare()} disabled={pending || !session.operator.permissions.includes('control:operate')}>{pending ? 'Menghitung dua skenario…' : 'Jalankan perbandingan setara'} <span aria-hidden="true">→</span></button><span role="status">{message || 'Kedatangan identik · kuning & semua merah · arsip lokal'}</span>{report && <a className="analytics-export" href={`${apiBase}/analytics/comparison/${report.id}/csv`}>↓ Unduh hasil CSV</a>}</div>
        {report && finalA && finalB ? <>
          <div className="analytics-report-meta"><span>Hasil {localTime(report.created_at)} WIB</span><span>{minute(report.input.duration_seconds)} · seed {report.input.seed}</span><span>{report.total_scheduled_arrivals} kedatangan identik</span><span>{number(report.input.detection_fraction * 100)}% fraksi deteksi</span></div>
          <div className="analytics-impact-grid">{summaries.map(s => { const a = s.key === 'cost' ? finalA.fuel_cost_rupiah + finalA.time_cost_rupiah : finalA[s.key], b = s.key === 'cost' ? finalB.fuel_cost_rupiah + finalB.time_cost_rupiah : finalB[s.key], change = impactChange(a, b); return <div className="analytics-impact-stat" key={s.key}><p>{s.detail}</p><h3>{s.label}</h3><strong>{number(b)}<small>{s.unit}</small></strong><span className={change === null || change === 0 ? 'delta-neutral' : change > 0 ? 'delta-good' : 'delta-bad'}>{change === null ? 'Baseline nol · tanpa persentase' : change === 0 ? 'Sama dengan ATCS' : `${number(Math.abs(change))}% ${change > 0 ? 'lebih rendah' : 'lebih tinggi'} dari ATCS`}</span><small>ATCS {number(a)} {s.unit} → SIGAP {number(b)} {s.unit}</small></div> })}</div>
          <section className="analytics-card analytics-impact-chart" aria-label="Grafik perbandingan ATCS dan SIGAP"><div className="analytics-card-heading"><div><h3>{metric.label}: dua kendali, satu eksperimen</h3><p>{metric.description}</p></div></div><div className="analytics-metric-tabs" role="group" aria-label="Indikator dampak">{metrics.map(m => <button key={m.key} aria-pressed={metricKey === m.key} onClick={() => setMetricKey(m.key)}>{m.label}</button>)}</div>
            <AnalyticsChart title={`Perbandingan ${metric.label}`} unit={metric.unit} xLabel={minute} series={[{ label: 'ATCS · waktu tetap', color: '#74889d', dashed: true, points: report.atcs.map(p => ({ x: p.time_seconds, y: p[metricKey] })) }, { label: 'SIGAP · adaptif', color: '#008776', points: report.sigap.map(p => ({ x: p.time_seconds, y: p[metricKey] })) }]} />
            <div className="analytics-source-note">Hasil model antrean FIFO dengan input identik. SIGAP dapat lebih baik, sama, atau lebih buruk tergantung arus dan cakupan deteksi. Grafik ini bukan hasil eksperimen jalan nyata dan tidak diturunkan dari TomTom.</div>
          </section>
          <details className="analytics-method"><summary>Metode, asumsi &amp; hasil lengkap</summary><div className="table-scroll"><table><thead><tr><th>Indikator akhir</th><th>ATCS</th><th>SIGAP</th></tr></thead><tbody>{metrics.map(m => <tr key={m.key}><th>{m.label}</th><td>{number(finalA[m.key])} {m.unit}</td><td>{number(finalB[m.key])} {m.unit}</td></tr>)}</tbody></table></div><ul>{report.assumptions.map(a => <li key={a}>{a}</li>)}</ul><p>Baseline hijau U/T/S/B: {directions.map(d => report.baseline_green_seconds[d]).join(' / ')} detik. Kuning {report.yellow_seconds} detik · semua merah {report.all_red_seconds} detik. Batas hijau SIGAP {report.adaptive_policy.maximum_green} detik.</p><p className="analytics-hash">Hash kedatangan: {report.arrival_schedule_sha256}</p></details>
        </> : <div className="analytics-empty analytics-impact-empty"><span aria-hidden="true">↔</span><h3>Mulai satu eksperimen yang bisa dibandingkan</h3><p>Atur arus tiap pendekat, lalu jalankan perbandingan. Dua garis akan muncul dari hasil perhitungan yang sama, tanpa mengarang angka penghematan.</p></div>}
        <div className="analytics-safety"><span aria-hidden="true">✚</span><div><strong>Keselamatan &amp; respons kendaraan darurat</strong><p>Belum diuji. Waktu respons ambulans/pemadam dan keamanan transisi perlu pengujian klip serta skenario terpisah sebelum ditampilkan sebagai hasil.</p></div><span className="analytics-badge">MENUNGGU VALIDASI</span></div>
      </section>
      <footer className="analytics-footer"><span>SIGAP · Analitik dengan sumber dan asumsi yang terlihat</span><span>Traffic data © TomTom · waktu WIB</span></footer>
    </main>
  </>
}
