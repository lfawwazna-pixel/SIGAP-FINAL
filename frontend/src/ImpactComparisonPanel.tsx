import { useEffect, useRef, useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import inputSchema from './schemas/ComparisonInput.json'
import type { AnalyticsView, ComparisonInput, ComparisonReport, ImpactPoint, ImpactFactors } from './types/AnalyticsView'
import type { SessionView } from './types/SessionView'
import { apiBase, postService } from './useService'
import { authGeneration } from './authEvents'
import { directions, directionNames, localTime } from './traffic'
import { AnalyticsChart } from './AnalyticsChart'

const ajv = new Ajv2020(); addFormats(ajv)
const inputShape = ajv.compile<ComparisonInput>(inputSchema)
type VehicleKind = 'motorcycle' | 'car' | 'bus' | 'truck'
type Movement = 'left' | 'straight' | 'right'
const kinds: VehicleKind[] = ['motorcycle', 'car', 'bus', 'truck']
const kindNames = { motorcycle: 'Motor', car: 'Mobil', bus: 'Bus', truck: 'Truk' }
const turns: Movement[] = ['left', 'straight', 'right']
const turnNames = { left: 'Kiri bebas', straight: 'Lurus', right: 'Kanan' }
const number = (n: number, digits = 1) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: digits }).format(n)
const minute = (n: number) => `${number(n / 60)} mnt`
const carIdle = .23 * 3.785411784
export const comparisonDefaults: ComparisonInput = {
  duration_seconds: 900, warmup_seconds: 300, replications: 10, seed: 42,
  demand_per_minute: { U: 18, T: 32, S: 14, B: 24 }, detection_fraction: 1, queue_visibility: 'partial',
  discharge_headway_seconds: 2.2, startup_lost_seconds: 2, demand_source: 'manual_scenario', observation_fingerprint: null,
  class_mix: { motorcycle: 45, car: 45, bus: 5, truck: 5 }, turn_mix: { left: 25, straight: 55, right: 20 }, approach_composition: {},
  factors: { idle_liters_per_hour: carIdle, co2_kg_per_liter: 2.35, diesel_co2_kg_per_liter: 2.69,
    fuel_rupiah_per_liter: 10000, diesel_fuel_rupiah_per_liter: 10000, time_rupiah_per_vehicle_hour: 20000, queue_spacing_meters: 6.5 },
  vehicle_factors: {
    motorcycle: { queue_space_multiplier: 3 / 6.5, discharge_multiplier: 1, idle_multiplier: .2 / carIdle, fuel: 'gasoline', parallel_slots: 3 },
    car: { queue_space_multiplier: 1, discharge_multiplier: 1, idle_multiplier: 1, fuel: 'gasoline', parallel_slots: 1 },
    bus: { queue_space_multiplier: 2, discharge_multiplier: 2, idle_multiplier: .8 / .23, fuel: 'diesel', parallel_slots: 1 },
    truck: { queue_space_multiplier: 2, discharge_multiplier: 2, idle_multiplier: .8 / .23, fuel: 'diesel', parallel_slots: 1 },
  },
}
type NumericMetric = 'average_wait_seconds' | 'queue_vehicles' | 'queue_meters_estimate' | 'maximum_lane_queue_meters' | 'co2_kg' | 'idle_fuel_liters' | 'fuel_cost_rupiah' | 'time_cost_rupiah' | 'completed_vehicles'
const metrics: { key: NumericMetric; label: string; unit: string; description: string }[] = [
  { key: 'average_wait_seconds', label: 'Waktu tunggu', unit: 'dtk', description: 'Vehicle-seconds dibagi antrean awal + kedatangan; termasuk yang belum selesai. Terbatas pada jendela uji.' },
  { key: 'queue_vehicles', label: 'Antrean', unit: 'kendaraan', description: 'Kendaraan masih mengantre, digabung dari empat pendekat.' },
  { key: 'queue_meters_estimate', label: 'Panjang antrean', unit: 'm', description: 'Jumlah panjang semua lajur berdasarkan kelas dan baris motor; bukan panjang satu ruas atau hasil ukur kamera.' },
  { key: 'maximum_lane_queue_meters', label: 'Lajur terpanjang', unit: 'm', description: 'Estimasi lajur dengan antrean terpanjang pada waktu yang ditampilkan.' },
  { key: 'co2_kg', label: 'Emisi CO₂', unit: 'kg', description: 'Estimasi idle per kelas dan bahan bakar. Tidak mencakup emisi perjalanan, percepatan atau total emisi aktual.' },
  { key: 'idle_fuel_liters', label: 'BBM idle', unit: 'L', description: 'Vehicle-seconds per kelas × laju idle kelas / 3600.' },
  { key: 'fuel_cost_rupiah', label: 'Biaya BBM', unit: 'Rp', description: 'BBM idle × harga asumsi bensin/diesel, bukan harga terkini.' },
  { key: 'time_cost_rupiah', label: 'Biaya waktu', unit: 'Rp', description: 'Vehicle-seconds / 3600 × nilai waktu per kendaraan-jam; bukan survei ekonomi lapangan.' },
  { key: 'completed_vehicles', label: 'Kendaraan terlayani', unit: 'kendaraan', description: 'Kendaraan keluar antrean selama jendela uji; antrean awal ikut dilaporkan.' },
]
const factors: { key: keyof ImpactFactors; label: string; max: number; step: number; min?: number }[] = [
  { key: 'idle_liters_per_hour', label: 'Acuan idle mobil (L/jam)', max: 10, step: .001 },
  { key: 'co2_kg_per_liter', label: 'CO₂ bensin (kg/L)', max: 5, step: .01 },
  { key: 'diesel_co2_kg_per_liter', label: 'CO₂ diesel (kg/L)', max: 5, step: .01 },
  { key: 'fuel_rupiah_per_liter', label: 'Asumsi harga bensin (Rp/L)', max: 100000, step: 100 },
  { key: 'diesel_fuel_rupiah_per_liter', label: 'Asumsi harga diesel (Rp/L)', max: 100000, step: 100 },
  { key: 'time_rupiah_per_vehicle_hour', label: 'Nilai waktu (Rp/kend/jam)', max: 1000000, step: 1000 },
  { key: 'queue_spacing_meters', label: 'Ruang baris mobil (m)', max: 20, step: .1, min: 1 },
]
const summaries = [
  { key: 'average_wait_seconds', label: 'Tunggu rata-rata', unit: 'dtk', detail: 'Operasional · jendela pengamatan' },
  { key: 'completed_vehicles', label: 'Kendaraan terlayani', unit: 'kendaraan', detail: 'Pelayanan · termasuk antrean awal' },
  { key: 'co2_kg', label: 'Emisi idle', unit: 'kg CO₂', detail: 'Lingkungan · estimasi per kelas' },
  { key: 'cost', label: 'Biaya BBM + waktu', unit: 'Rp', detail: 'Ekonomi · harga dan nilai asumsi' },
] as const
export function impactChange(a: number, b: number, higherBetter = false) { return a === 0 ? null : (higherBetter ? b - a : a - b) / a * 100 }
const pointValue = (point: ImpactPoint, key: NumericMetric | 'cost') => key === 'cost' ? point.fuel_cost_rupiah + point.time_cost_rupiah : point[key]

export function ImpactComparisonPanel({ view, session, refresh, validReport }: {
  view: AnalyticsView | null; session: SessionView; refresh: () => void; validReport: (v: unknown) => v is ComparisonReport
}) {
  const [spec, setSpec] = useState<ComparisonInput>(comparisonDefaults), [generated, setGenerated] = useState<ComparisonReport | null>(null)
  const [pending, setPending] = useState(false), [message, setMessage] = useState(''), [invalidInput, setInvalidInput] = useState(false)
  const [metricKey, setMetricKey] = useState<NumericMetric>('average_wait_seconds')
  const mounted = useRef(true), running = useRef(false)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const report = generated ?? view?.latest_comparison, v2 = report?.method_version === 'queue-v2'
  const profile = view?.zone_demand, observed = spec.demand_source === 'zone_observation'
  const metric = metrics.find(m => m.key === metricKey)!, finalA = report?.atcs.at(-1), finalB = report?.sigap.at(-1)
  function capture() {
    if (!profile?.ready || !profile.fingerprint) return
    const classes = Object.fromEntries(kinds.map(k => [k, profile.approaches.reduce((sum, p) => sum + p.by_class[k], 0)]))
    const movements = Object.fromEntries(turns.map(m => [m, profile.approaches.reduce((sum, p) => sum + p.by_movement[m], 0)]))
    setSpec({ ...spec, demand_source: 'zone_observation', observation_fingerprint: profile.fingerprint,
      demand_per_minute: Object.fromEntries(profile.approaches.map(p => [p.direction, p.demand_per_minute])) as ComparisonInput['demand_per_minute'],
      class_mix: Object.values(classes).some(v => v > 0) ? classes : spec.class_mix,
      turn_mix: Object.values(movements).some(v => v > 0) ? movements : spec.turn_mix,
      queue_visibility: profile.approaches.every(p => p.queue_visibility === 'full') ? 'full' : 'partial' })
    setMessage('Profil zona dipilih. Laju, campuran kelas dan belokan akan diverifikasi oleh backend saat uji dimulai.')
  }
  function manual(demand = spec.demand_per_minute) {
    setSpec({ ...spec, demand_source: 'manual_scenario', observation_fingerprint: null, approach_composition: {}, demand_per_minute: demand })
  }
  async function compare() {
    if (running.current) return
    if (!inputShape(spec) || Object.values(spec.class_mix).reduce((a, b) => a + b, 0) <= 0 || Object.values(spec.turn_mix).reduce((a, b) => a + b, 0) <= 0) { setInvalidInput(true); setMessage('Periksa batas angka pada skenario. Durasi, arus, fraksi deteksi, dan faktor harus berada dalam rentang yang ditampilkan; bobot kendaraan dan belokan tidak boleh semuanya nol.'); return }
    setInvalidInput(false); running.current = true; setPending(true); setMessage('')
    const generation = authGeneration()
    try {
      const result: unknown = await postService('/analytics/comparison', session.csrf_token, spec, false, 120000)
      if (!validReport(result)) throw new Error('Hasil perbandingan tidak valid atau kedua arus tidak sama.')
      if (mounted.current && generation === authGeneration()) { setGenerated(result); setMessage('Perbandingan selesai dan tersimpan. Lihat hasil di bawah.'); refresh() }
    } catch (cause) { if (mounted.current && generation === authGeneration()) setMessage(cause instanceof Error ? cause.message : 'Perbandingan gagal.') }
    finally { running.current = false; if (mounted.current && generation === authGeneration()) setPending(false) }
  }
  return <section id="impact" className="analytics-section">
    <div className="analytics-section-heading"><div><p className="analytics-kicker">02 / DAMPAK KENDALI</p><h2>ATCS dan SIGAP, arus yang sama</h2><p>Eksperimen berulang dengan kendaraan campuran. Pengendali yang sedang berjalan tetap terpisah.</p></div><span className="analytics-badge">SIMULASI PERBANDINGAN</span></div>
    <section className="analytics-demand-card analytics-card" aria-label="Sumber masukan eksperimen">
      <div className="analytics-card-heading"><div><h3>Masukan dari kendaraan dalam zona</h3><p>{profile?.message ?? 'Menunggu profil zona dari layanan analitik.'}</p></div><span className="analytics-badge">{observed ? 'PROFIL ZONA DIPILIH' : 'SKENARIO MANUAL'}</span></div>
      <div className="analytics-zone-grid">{directions.map(d => { const p = profile?.approaches.find(p => p.direction === d); return <div key={d}><strong>{directionNames[d]}</strong><b>{p?.state === 'ready' ? number(p.demand_per_minute) : '—'} <small>kend/menit</small></b><span>{p ? `${number(p.observed_seconds, 0)} detik · ${p.entries} identitas baru · ${p.state === 'ready' ? 'siap' : p.state === 'collecting' ? 'mengumpulkan' : 'belum tersedia'}` : 'Belum tersedia'}</span><small>{p && kinds.map(k => `${kindNames[k]} ${p.by_class[k]}`).join(' · ')}</small>{p?.state === 'unavailable' && <small>{p.message}</small>}{p && p.loop_count > 0 && <small>Rekaman sudah berulang {p.loop_count}×; bukan sampel lapangan independen.</small>}</div> })}</div>
      <div className="analytics-demand-actions"><button onClick={capture} disabled={!profile?.ready || pending}>Gunakan pengamatan zona</button><button onClick={() => manual()} disabled={pending || !observed}>Gunakan skenario manual</button><span>{observed ? `Profil dibekukan ${spec.observation_fingerprint?.slice(0, 10)}; ambil ulang jika sumber berubah.` : 'Laju dihitung dari identitas baru selama 60–180 detik; populasi frame awal dan EVP dikecualikan.'}</span></div>
      <p className="analytics-fine-print">Profil zona adalah kedatangan yang teramati, belum arus kendaraan lengkap. YOLO yang terlewat atau pergantian ID bisa memberi bias. TomTom menyediakan kecepatan ruas dan waktu perjalanan, bukan jumlah kedatangan atau fase ATCS.</p>
    </section>
    <details className="analytics-scenario" open={!report || invalidInput}><summary>Atur skenario &amp; asumsi perbandingan <span>Arus · ulangan · kendaraan · BBM</span></summary><div className="analytics-scenario-body">
      <div className="analytics-presets"><span>Skenario manual untuk uji:</span><button disabled={pending} onClick={() => manual({ U: 4, T: 4, S: 4, B: 4 })}>Arus ringan merata</button><button disabled={pending} onClick={() => manual({ U: 4, T: 24, S: 4, B: 20 })}>Arus tidak seimbang</button><button disabled={pending} onClick={() => manual(comparisonDefaults.demand_per_minute)}>Arus padat</button></div>
      <div className="analytics-form-grid">
        <label>Durasi uji<select value={spec.duration_seconds} onChange={e => setSpec({ ...spec, duration_seconds: Number(e.target.value) })}><option value="300">5 menit</option><option value="900">15 menit</option><option value="1800">30 menit</option></select></label>
        <label>Pemanasan sebelum uji<select value={spec.warmup_seconds} onChange={e => setSpec({ ...spec, warmup_seconds: Number(e.target.value) })}><option value="0">Tanpa pemanasan</option><option value="300">5 menit</option><option value="600">10 menit</option><option value="900">15 menit</option></select></label>
        <label>Jumlah ulangan<select value={spec.replications} onChange={e => setSpec({ ...spec, replications: Number(e.target.value) })}>{[5, 10, 20, 30].map(n => <option key={n} value={n}>{n} pasangan seed</option>)}</select></label>
        <label>Seed awal<input type="number" min="0" max="2147483647" value={spec.seed} onChange={e => setSpec({ ...spec, seed: Number(e.target.value) })} /></label>
        {directions.map(d => <label key={d}>Arus {directionNames[d]} (kend/menit)<input type="number" min="0" max="180" step="any" disabled={observed} value={spec.demand_per_minute[d]} onChange={e => setSpec({ ...spec, demand_per_minute: { ...spec.demand_per_minute, [d]: Number(e.target.value) } })} /></label>)}
        <label>Fraksi deteksi untuk sensitivitas<input type="number" min="0.1" max="1" step="0.05" value={spec.detection_fraction} onChange={e => setSpec({ ...spec, detection_fraction: Number(e.target.value) })} /></label>
        <label>Cakupan antrean<select disabled={observed} value={spec.queue_visibility} onChange={e => setSpec({ ...spec, queue_visibility: e.target.value as ComparisonInput['queue_visibility'] })}><option value="partial">Sebagian antrean terlihat</option><option value="full">Antrean penuh terlihat</option></select></label>
        <label>Headway acuan mobil (dtk)<input type="number" min="1" max="5" step="0.1" value={spec.discharge_headway_seconds} onChange={e => setSpec({ ...spec, discharge_headway_seconds: Number(e.target.value) })} /></label>
        <label>Waktu awal bergerak (dtk)<input type="number" min="0" max="5" step="0.1" value={spec.startup_lost_seconds} onChange={e => setSpec({ ...spec, startup_lost_seconds: Number(e.target.value) })} /></label>
      </div>
      <details className="analytics-method"><summary>Campuran armada &amp; asumsi lingkungan / biaya</summary><p>Bobot dinormalisasi menjadi proporsi. Pada profil zona, kelas dan belokan per arah berasal dari pengamatan backend. Kendaraan darurat tidak masuk eksperimen dampak ini.</p>
        <div className="analytics-form-grid">{kinds.map(k => <label key={k}>Bobot {kindNames[k]}<input disabled={observed} type="number" min="0" step="1" value={spec.class_mix[k]} onChange={e => setSpec({ ...spec, class_mix: { ...spec.class_mix, [k]: Number(e.target.value) } })} /></label>)}{turns.map(m => <label key={m}>Bobot {turnNames[m]}<input disabled={observed} type="number" min="0" step="1" value={spec.turn_mix[m]} onChange={e => setSpec({ ...spec, turn_mix: { ...spec.turn_mix, [m]: Number(e.target.value) } })} /></label>)}</div>
        <div className="analytics-form-grid">{factors.map(f => <label key={f.key}>{f.label}<input type="number" min={f.min ?? 0} max={f.max} step={f.step} value={spec.factors[f.key]} onChange={e => setSpec({ ...spec, factors: { ...spec.factors, [f.key]: Number(e.target.value) } })} /></label>)}</div>
        <div className="table-scroll"><table><caption>Profil kendaraan · dapat dikalibrasi dengan data lokal</caption><thead><tr><th>Kelas / bahan bakar</th><th>Ruang × mobil</th><th>Headway × mobil</th><th>Idle × mobil</th><th>Sejajar</th><th>Laju idle (L/jam)</th></tr></thead><tbody>{kinds.map(k => <tr key={k}><th>{kindNames[k]}<select aria-label={`Bahan bakar ${kindNames[k]}`} value={spec.vehicle_factors[k].fuel} onChange={e => setSpec({ ...spec, vehicle_factors: { ...spec.vehicle_factors, [k]: { ...spec.vehicle_factors[k], fuel: e.target.value } } } as ComparisonInput)}><option value="gasoline">Bensin</option><option value="diesel">Diesel</option></select></th>{(['queue_space_multiplier', 'discharge_multiplier', 'idle_multiplier'] as const).map(key => <td key={key}><input aria-label={`${kindNames[k]} ${key}`} type="number" step="any" min={key === 'queue_space_multiplier' ? .1 : key === 'discharge_multiplier' ? .2 : 0} max={key === 'idle_multiplier' ? 10 : 5} value={spec.vehicle_factors[k][key]} onChange={e => setSpec({ ...spec, vehicle_factors: { ...spec.vehicle_factors, [k]: { ...spec.vehicle_factors[k], [key]: Number(e.target.value) } } })} /></td>)}<td>{k === 'motorcycle' ? <select aria-label="Motor per baris" value={spec.vehicle_factors[k].parallel_slots} onChange={e => setSpec({ ...spec, vehicle_factors: { ...spec.vehicle_factors, [k]: { ...spec.vehicle_factors[k], parallel_slots: Number(e.target.value) } } })}>{[1, 2, 3].map(n => <option key={n}>{n}</option>)}</select> : 1}</td><td>{number(spec.factors.idle_liters_per_hour * spec.vehicle_factors[k].idle_multiplier, 3)}</td></tr>)}</tbody></table></div>
      </details>
      <p className="analytics-fine-print">Semua preset adalah asumsi uji, bukan data TomTom. Fraksi deteksi bukan akurasi YOLO yang telah diukur. Hasil dapat menguntungkan atau merugikan; seluruh ulangan masuk ringkasan.</p>
    </div></details>
    <div className="analytics-run-bar"><button className="analytics-primary" onClick={() => void compare()} disabled={pending || !session.operator.permissions.includes('control:operate')}>{pending ? `Menghitung ${spec.replications} pasangan…` : 'Jalankan perbandingan setara'} <span aria-hidden="true">→</span></button><span role="status">{message || 'Kedatangan identik · kuning & semua merah · arsip lokal'}</span>{report && <a className="analytics-export" href={`${apiBase}/analytics/comparison/${report.id}/csv`}>↓ Unduh hasil CSV</a>}</div>
    {report && finalA && finalB ? <>
      {!v2 && <p className="connection-note">Arsip metode sebelumnya: satu seed dan faktor seragam. Jalankan ulang untuk hitungan terbaru; hasil lama tidak menjadi bukti eksperimen berulang.</p>}
      <div className="analytics-report-meta"><span>Hasil {localTime(report.created_at)} WIB</span><span>{minute(report.input.duration_seconds)} · seed awal {report.input.seed}</span><span>{v2 ? `${report.runs.length} ulangan · warmup ${minute(report.input.warmup_seconds)}` : 'Arsip satu seed'}</span><span>{report.demand_provenance?.source === 'zone_observation' ? 'Masukan profil zona teramati' : 'Masukan skenario manual'}</span></div>
      <div className="analytics-impact-grid">{summaries.map(s => {
        const statistic = v2 ? report.metrics.find(m => m.key === s.key) : null
        const a = statistic?.atcs_mean ?? pointValue(finalA, s.key), b = statistic?.sigap_mean ?? pointValue(finalB, s.key)
        const change = statistic ? statistic.improvement_percent : impactChange(a, b, s.key === 'completed_vehicles')
        const result = statistic?.result ?? (change == null || change === 0 ? 'equal' : change > 0 ? 'better' : 'worse')
        const word = s.key === 'completed_vehicles' ? (change !== null && change > 0 ? 'lebih banyak' : 'lebih sedikit') : (change !== null && change > 0 ? 'lebih rendah' : 'lebih tinggi')
        return <div className="analytics-impact-stat" key={s.key}><p>{s.detail}</p><h3>{s.label}</h3><strong>{number(b)}<small>{s.unit}</small></strong><span className={result === 'better' ? 'delta-good' : result === 'worse' ? 'delta-bad' : 'delta-neutral'}>{change === null ? 'Baseline nol · tanpa persentase' : change === 0 ? 'Sama dengan ATCS' : `${number(Math.abs(change))}% ${word} dari ATCS`}</span><small>ATCS {number(a)} {s.unit} → SIGAP {number(b)} {s.unit}</small>{statistic && <small>{result === 'inconclusive' ? 'Belum konsisten antarulangan' : result === 'better' ? 'Selisih konsisten pada skenario ini' : result === 'worse' ? 'SIGAP memburuk pada skenario ini' : 'Tidak ada selisih'}<br />Selisih 95%: {number(statistic.lower_95)} s.d. {number(statistic.upper_95)} {s.unit}</small>}</div>
      })}</div>
      {v2 && <p className="analytics-fine-print">Kartu = rata-rata {report.runs.length} ulangan. Selisih positif berarti manfaat; interval 95% hanya mencakup variasi seed, bukan ketidakpastian model atau bukti lapangan.</p>}
      <section className="analytics-card analytics-impact-chart" aria-label="Grafik perbandingan ATCS dan SIGAP"><div className="analytics-card-heading"><div><h3>{metric.label}: dua kendali, satu eksperimen</h3><p>{metric.description}</p><p>Grafik seed {report.input.seed}{v2 ? ' · contoh pasangan pertama, bukan rata-rata ulangan' : ' · metode sebelumnya'}. {report.total_scheduled_arrivals} kedatangan identik; antrean awal ATCS {finalA.initial_queue_vehicles}, SIGAP {finalB.initial_queue_vehicles}.</p></div></div><div className="analytics-metric-tabs" role="group" aria-label="Indikator dampak">{metrics.map(m => <button key={m.key} aria-pressed={metricKey === m.key} onClick={() => setMetricKey(m.key)}>{m.label}</button>)}</div>
        <AnalyticsChart title={`Perbandingan ${metric.label}`} unit={metric.unit} xLabel={minute} series={[{ label: 'ATCS · waktu tetap', color: '#74889d', dashed: true, points: report.atcs.map(p => ({ x: p.time_seconds, y: p[metricKey] })) }, { label: 'SIGAP · adaptif', color: '#008776', points: report.sigap.map(p => ({ x: p.time_seconds, y: p[metricKey] })) }]} />
        <div className="analytics-source-note">Grafik ini bukan hasil eksperimen jalan nyata dan tidak diturunkan dari TomTom. Baseline hijau berasal dari Tabel 7 penelitian Polban (2025); konfigurasi ATCS terkini belum dikonfirmasi. SIGAP menggunakan kebijakan adaptif aplikasi.</div>
      </section>
      {v2 && <section className="analytics-card analytics-approach-results"><div className="analytics-card-heading"><div><h3>Pelayanan per pendekat</h3><p>Rata-rata semua ulangan. Periksa waktu tunggu dan kendaraan tersisa pada setiap arah.</p></div></div><div className="table-scroll"><table aria-label="Hasil per pendekat"><thead><tr><th>Arah</th><th>Tunggu ATCS / SIGAP (dtk)</th><th>Terlayani ATCS / SIGAP</th><th>Tersisa ATCS / SIGAP</th><th>Peserta ATCS / SIGAP</th></tr></thead><tbody>{directions.map(d => {
        const values = (arm: 'atcs_by_approach' | 'sigap_by_approach', key: 'average_wait_seconds' | 'completed_vehicles' | 'queue_vehicles' | 'participants') => number(report.runs.reduce((sum, run) => sum + run[arm][d][key], 0) / report.runs.length)
        return <tr key={d}><th>{directionNames[d]}</th>{(['average_wait_seconds', 'completed_vehicles', 'queue_vehicles', 'participants'] as const).map(k => <td key={k}>{values('atcs_by_approach', k)} / {values('sigap_by_approach', k)}</td>)}</tr>
      })}</tbody></table></div><p className="analytics-fine-print">Peserta = antrean awal + kedatangan dalam uji. Antrean awal dapat berbeda setelah strategi menjalani warmup yang sama.</p></section>}
      <details className="analytics-method"><summary>Rumus, sumber &amp; hasil lengkap</summary>
        <p>Parameter hasil ini: uji {minute(report.input.duration_seconds)}, warmup {minute(report.input.warmup_seconds)}, {v2 ? report.input.replications : 1} ulangan; headway {number(report.input.discharge_headway_seconds)} detik, startup {number(report.input.startup_lost_seconds)} detik, fraksi deteksi {number(report.input.detection_fraction * 100)}%, cakupan {report.input.queue_visibility === 'full' ? 'penuh' : 'sebagian'}.</p>
        <div className="table-scroll"><table aria-label="Masukan yang digunakan"><thead><tr><th>Arah</th><th>Kend/menit</th><th>Bobot motor / mobil / bus / truk</th><th>Bobot kiri / lurus / kanan</th></tr></thead><tbody>{directions.map(d => <tr key={d}><th>{directionNames[d]}</th><td>{number(report.input.demand_per_minute[d], 4)}</td><td>{kinds.map(k => number((report.input.approach_composition[d]?.class_mix ?? report.input.class_mix)[k], 2)).join(' / ')}</td><td>{turns.map(m => number((report.input.approach_composition[d]?.turn_mix ?? report.input.turn_mix)[m], 2)).join(' / ')}</td></tr>)}</tbody></table></div>
        <p>Tunggu = ∫ antrean(t) dt / peserta. BBM = Σ (vehicle-seconds kelas / 3600 × idle kelas). CO₂ = Σ (liter bahan bakar × faktor CO₂). Biaya total = biaya BBM + vehicle-seconds / 3600 × nilai waktu.</p>
        <div className="table-scroll"><table><thead><tr><th>Indikator akhir</th><th>ATCS</th><th>SIGAP</th><th>Selisih 95% · positif = manfaat</th></tr></thead><tbody>{metrics.map(m => { const stat = v2 ? report.metrics.find(s => s.key === m.key) : null; return <tr key={m.key}><th>{m.label}</th><td>{number(stat?.atcs_mean ?? finalA[m.key])} {m.unit}</td><td>{number(stat?.sigap_mean ?? finalB[m.key])} {m.unit}</td><td>{stat ? `${number(stat.lower_95)} s.d. ${number(stat.upper_95)} ${m.unit}` : '—'}</td></tr> })}</tbody></table></div>
        <ul>{report.assumptions.map(a => <li key={a}>{a}</li>)}</ul>
        <p>Baseline hijau U/T/S/B: {directions.map(d => report.baseline_green_seconds[d]).join(' / ')} detik. Kuning {report.yellow_seconds} detik · semua merah {report.all_red_seconds} detik. Batas hijau SIGAP {report.adaptive_policy.maximum_green} detik.</p>
        <ul>{report.references.map(r => <li key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> — {r.use}</li>)}</ul>
        {report.demand_provenance?.captured_at && <p>Profil zona diambil {localTime(report.demand_provenance.captured_at)} WIB. Fingerprint {report.demand_provenance.fingerprint}.</p>}
        <p className="analytics-hash">Hash kedatangan: {report.arrival_schedule_sha256}</p>
      </details>
    </> : <div className="analytics-empty analytics-impact-empty"><span aria-hidden="true">↔</span><h3>Mulai eksperimen yang bisa diperiksa</h3><p>Pilih profil zona atau skenario manual. Semua pasangan mendapat kedatangan yang sama; seluruh hasil ikut ringkasan.</p></div>}
    <div className="analytics-safety"><span aria-hidden="true">✚</span><div><strong>Keselamatan &amp; respons kendaraan darurat</strong><p>Belum diuji. Waktu respons ambulans/pemadam dan keamanan transisi tidak dinilai oleh eksperimen dampak ini. Gunakan pengujian EVP dan transisi yang terpisah.</p></div><span className="analytics-badge">UJI DAMPAK TANPA EVP</span></div>
  </section>
}
