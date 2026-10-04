import { useEffect, useState } from 'react'
import { IntersectionMap } from './IntersectionMap'
import { useTraffic } from './useTraffic'
import { directions, directionNames, phaseNames, type Direction } from './traffic'
import type { TrafficView } from './types/TrafficView'
import { MapZoom } from './MapZoom'

export function TrafficMetrics({ data }: { data: TrafficView }) {
  return <div className="traffic-metrics" aria-label="Statistik kendaraan sintetis">
    <div><span>Di peta</span><strong>{data.vehicles.length}<small> kendaraan</small></strong></div>
    <div><span>Selesai melintas</span><strong>{data.completed}</strong></div>
    <div><span>Rata-rata tunggu selesai</span><strong>{data.average_wait.toFixed(1)}<small> dtk</small></strong></div>
    <div><span>Antrean U / T / S / B</span><strong className="queue-summary">{directions.map(d => data.queues[d]).join(' / ')}</strong></div>
  </div>
}

export function SimulationWorkspace({ intersection, csrf, active }: { intersection: string | undefined; csrf: string; active: boolean }) {
  const feed = useTraffic('experiment', intersection, active, csrf)
  const [selected, setSelected] = useState<Direction>('U')
  const [spawnDirection, setSpawnDirection] = useState<Direction>('U')
  const [distance, setDistance] = useState(100)
  const [zoom, setZoom] = useState(1)
  const [resetting, setResetting] = useState(false)
  const [notice, setNotice] = useState('')
  const [rates, setRates] = useState<Record<Direction, number>>({ U: 10, T: 10, S: 10, B: 10 })
  const data = feed.data
  const experimentId = data?.run_id
  useEffect(() => {
    if (experimentId && data) setRates({ U: data.demand.U, T: data.demand.T, S: data.demand.S, B: data.demand.B })
    // Refresh the form when attaching to an experiment, not during each poll.
  }, [experimentId])
  const send = async (value: Record<string, unknown>, message?: string) => {
    if (await feed.command(value)) setNotice(message || 'Pengaturan diterapkan pada percobaan.')
    else setNotice('Perintah belum terkonfirmasi. Periksa pesan layanan.')
  }
  if (!active) return null
  return <section className="experiment-workspace" aria-label="Ruang simulasi terpisah">
    <div className="experiment-heading"><div><p className="eyebrow">RUANG PERCOBAAN</p><h2>Simulasi arus dan prioritas darurat</h2><p>Semua kendaraan di sini sintetis. ATCS utama terus berjalan dengan jamnya sendiri.</p></div><span className="experiment-state">{data ? data.running ? 'Berjalan' : 'Dijeda' : 'Menghubungkan'} · {data ? `${data.time_seconds.toFixed(1)} dtk` : '—'}</span></div>
    {feed.error && <p role="alert" className="connection-note">{feed.error}</p>}
    <div className="experiment-controls">
      <button className="primary-control" disabled={!data || feed.pending} onClick={() => void send({ action: data?.running ? 'pause' : 'start' }, data?.running ? 'Percobaan dijeda.' : 'Percobaan berjalan.')}>{data?.running ? 'Jeda' : 'Mulai'}</button>
      <button disabled={!data || feed.pending} onClick={() => setResetting(true)}>Reset percobaan</button>
      <label>Kecepatan<select aria-label="Kecepatan simulasi" value={data?.speed ?? 1} disabled={!data || feed.pending} onChange={e => void send({ action: 'configure', speed: Number(e.target.value) })}><option value={1}>1×</option><option value={2}>2×</option><option value={3}>3×</option></select></label>
      <label>Strategi percobaan<select value={data?.strategy ?? 'adaptive'} disabled={!data || feed.pending} onChange={e => void send({ action: 'configure', strategy: e.target.value })}><option value="adaptive">Adaptif sintetis</option><option value="fixed_time">Fixed-time</option></select></label>
      <MapZoom label="Zoom peta Simulasi" value={zoom} onChange={setZoom} />
    </div>
    {resetting && <div className="reset-confirm" role="group" aria-label="Konfirmasi reset percobaan"><p>Hapus kendaraan dan riwayat percobaan ini, lalu mulai dari keadaan dijeda? ATCS utama tidak berubah.</p><button onClick={() => setResetting(false)}>Batal</button><button disabled={feed.pending} onClick={() => { setResetting(false); void send({ action: 'reset' }, 'Percobaan direset dan dijeda.') }}>Ya, reset percobaan</button></div>}
    <p className="control-feedback" role="status">{notice || 'Spawn kendaraan saat jeda untuk menyusun skenario serentak, lalu tekan Mulai.'}</p>
    <div className="operator-workspace">
      <section className="map-panel"><div className="section-toolbar"><div><h3>Persimpangan percobaan</h3><p>Jarak ditulis dalam unit skema, bukan meter lapangan.</p></div><span className={`phase-tag phase-tag--${data?.phase ?? 'unknown'}`}>{data?.phase ? `${phaseNames[data.phase]}${data.active_approach ? ` · ${data.active_approach}` : ''}` : 'Belum diketahui'}</span></div>
        <div className="experiment-map-scroll"><div style={{ width: `${zoom*100}%` }}><IntersectionMap selected={selected} onSelect={setSelected} signals={data?.signals ?? null} routes={false} vehicles={data?.vehicles ?? []} markerId="experiment-route" vehicleRunId={data?.run_id} /></div></div>
        {data && <TrafficMetrics data={data} />}
      </section>
      <aside className="operations-panel experiment-operations">
        <section className="experiment-decision"><p className="eyebrow">KEPUTUSAN PERCOBAAN</p><h3>{data?.emergency ? 'Emergency override' : data?.strategy === 'fixed_time' ? 'ATCS percobaan' : 'Adaptif sintetis'}</h3><p>{data?.reason || 'Menunggu pengendali percobaan.'}</p><strong className="experiment-time">{data?.remaining_seconds != null ? `${Math.ceil(data.remaining_seconds)} dtk` : data?.emergency ? 'Sampai EVP selesai' : '—'}</strong><p className="small-muted">Area konflik: {data?.conflict === 'occupied' ? 'terisi' : data?.conflict === 'clear' ? 'kosong' : 'belum diketahui'}</p></section>
        <section className="spawn-panel"><h3>Tambah kendaraan darurat</h3><div className="spawn-fields"><label>Dari arah<select value={spawnDirection} onChange={e => setSpawnDirection(e.target.value as Direction)}>{directions.map(d => <option key={d} value={d}>{d} · {directionNames[d]}</option>)}</select></label><label>Jarak awal<select value={distance} onChange={e => setDistance(Number(e.target.value))}><option value={60}>Dekat · 60 unit</option><option value={180}>Sedang · 180 unit</option><option value={350}>Jauh · 350 unit</option><option value={100}>100 unit</option></select></label></div><div className="spawn-actions"><button disabled={!data || feed.pending} onClick={() => void send({ action: 'spawn', kind: 'ambulance', direction: spawnDirection, distance }, `Ambulans ditambahkan dari ${spawnDirection}.`)}><span aria-hidden="true">✚</span> Spawn ambulans</button><button disabled={!data || feed.pending} onClick={() => void send({ action: 'spawn', kind: 'fire_engine', direction: spawnDirection, distance }, `Pemadam ditambahkan dari ${spawnDirection}.`)}>Spawn pemadam</button></div><p>Ambulans → pemadam. Sesama jenis: terdekat ke garis henti; seri memakai urutan kedatangan. Posisi spawn bergeser ke belakang jika ruang terisi.</p></section>
        <section className="demand-panel"><h3>Arus masuk</h3><p>Kendaraan per menit, tiap pendekat.</p><div className="demand-inputs">{directions.map(d => <label key={d}>{d}<input aria-label={`Arus ${directionNames[d]}`} type="number" min={0} max={60} step={1} value={rates[d]} onChange={e => setRates(old => ({ ...old, [d]: Number(e.target.value) }))} /></label>)}</div><button disabled={!data || feed.pending || Object.values(rates).some(v => !Number.isInteger(v) || v < 0 || v > 60)} onClick={() => void send({ action: 'configure', demand: rates })}>Terapkan arus</button><label className="blocked-control">Uji keluaran terblokir<select disabled={!data || feed.pending} value={data?.blocked_exit ?? 'none'} onChange={e => void send({ action: 'configure', blocked_exit: e.target.value })}><option value="none">Semua terbuka</option>{directions.map(d => <option key={d} value={d}>Keluar ke {directionNames[d]}</option>)}</select></label><p className="small-muted">Aktual: {data ? directions.map(d => `${d} ${data.demand[d]}`).join(' · ') : '—'}. Spawn tertahan: {data?.refused_spawns ?? '—'}.</p></section>
      </aside>
    </div>
    <section className="experiment-history"><div className="section-toolbar"><div><h3>Antrean EVP &amp; riwayat percobaan</h3><p>{data?.evp_queue.length ? `Urutan kandidat: ${data.evp_queue.map(id => `#${id}`).join(' → ')}` : 'Tidak ada EVP menunggu.'} {data?.target_vehicle ? `Sedang dilayani: #${data.target_vehicle}.` : ''}</p></div></div><div className="table-scroll"><table className="event-table"><thead><tr><th>Waktu percobaan</th><th>Keputusan dan kejadian</th></tr></thead><tbody>{data?.events.slice().reverse().map((event, index) => <tr key={`${data.run_id}-${index}`}><td>{event.time.toFixed(1)} dtk</td><td>{event.message}</td></tr>)}</tbody></table></div></section>
  </section>
}
