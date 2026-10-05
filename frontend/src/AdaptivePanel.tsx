import { useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import schema from './schemas/AdaptiveStatus.json'
import type { AdaptiveStatus, AdaptiveDecision } from './types/AdaptiveStatus'
import { directions, directionNames, localTime } from './traffic'
import { useService, postService } from './useService'

const ajv = new Ajv2020(); addFormats(ajv)
const valid = ajv.compile<AdaptiveStatus>(schema)
export const useAdaptive = (active: boolean) => useService('/adaptive', valid, active)

export function DecisionTable({ decision, dataTimeout = 3 }: { decision: AdaptiveDecision | null | undefined; dataTimeout?: number }) {
  if (!decision) return <p className="map-rule">Belum ada pengukuran untuk keputusan adaptif.</p>
  return <div className="decision-data"><p><strong>{decision.approach ? `${directionNames[decision.approach]} · ${decision.green_seconds} detik` : 'Keputusan ditahan'}</strong> — {decision.reason}</p>
    <div className="table-scroll"><table className="event-table"><thead><tr><th>Pendekat</th><th>Kendaraan terkontrol</th><th>Antrean</th><th>Tunggu terlama</th><th>Ruas pintas</th><th>Skor</th><th>Data / keluaran</th></tr></thead>
      <tbody>{directions.map(d => { const v = decision.inputs[d]; const age = (Date.parse(decision.decided_at)-Date.parse(v.observed_at))/1000; const quality = !v.usable ? 'Tidak valid' : age > dataTimeout ? 'Kedaluwarsa' : age < -.5 ? 'Waktu tidak valid' : 'Valid'; return <tr key={d}><th>{directionNames[d]}</th><td>{v.controlled_count}</td><td>{v.queue_count}</td><td>{v.oldest_wait_seconds.toFixed(1)} dtk</td><td>{v.slip_count}</td><td>{decision.scores[d].toFixed(1)}</td><td>{quality} / {v.exit_available ? 'terbuka' : 'penuh'}</td></tr> })}</tbody></table></div>
  </div>
}

export function AdaptivePanel({ feed, csrf, mayControl }: { feed: ReturnType<typeof useAdaptive>; csrf: string; mayControl: boolean }) {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const value = feed.data
  async function fault(next: string) {
    setPending(true)
    try { await postService('/adaptive/fault', csrf, { fault: next }); feed.refresh(); setMessage('Kondisi pengujian diterapkan. Pemulihan kendali tetap memerlukan aktivasi operator.') }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Permintaan gagal.') }
    finally { setPending(false) }
  }
  async function hold() {
    setPending(true)
    try { await postService('/adaptive/hold', csrf, {}); feed.refresh(); setMessage('Pemulihan otomatis dibatalkan; ATCS memeriksa transisi pelepasan kendali.') }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Permintaan gagal.') }
    finally { setPending(false) }
  }
  const video = value?.source !== 'synthetic'
  return <section className="adaptive-panel" aria-label="Keputusan adaptif">
    <div className="section-toolbar"><div><p className="eyebrow">{video ? 'YOLO + BYTETRACK / KENDALI ADAPTIF' : 'TAHAP 5 / DATA BUATAN'}</p><h2>Dasar keputusan adaptif</h2><p>{feed.error || value?.message || 'Memeriksa layanan keputusan…'}</p></div><span className="environment-tag">{value?.source === 'cctv' ? 'CCTV langsung' : video ? 'Video rekaman' : 'Sumber sintetis'}</span></div>
    {video && value && <><p className="map-rule">{value.status === 'active' ? 'SIGAP aktif: ATCS mengikuti keputusan video.' : 'SIGAP belum mengambil alih; ATCS menjalankan fase dasarnya.'} Antrean dan waktu tunggu merupakan estimasi gerak di gambar. Keluaran diasumsikan terbuka; klip EVP belum diverifikasi.</p>{Object.entries(value.issues).map(([d, issue]) => <p className="history-note" key={d}>{directionNames[d as keyof typeof directionNames]}: {issue}</p>)}</>}
    {video && value?.auto_resume && <div className="control-actions"><button disabled={pending || !mayControl} onClick={() => void hold()}>Batalkan pemulihan otomatis</button><p role="status">{message}</p></div>}
    <DecisionTable decision={value?.decisions.find(d => d.outcome === 'preview')} dataTimeout={value?.policy.data_timeout} />
    {value && <p className="map-rule">Hijau {value.policy.minimum_green}–{value.policy.maximum_green} detik. Target usia pelayanan {value.policy.service_age_target} detik; dapat tertunda oleh konflik, keluaran penuh, atau EVP. Ruas pintas tidak menambah kebutuhan hijau.</p>}
    {!video && <div className="adaptive-fault"><label>Uji kesehatan pengirim<select value={value?.fault ?? 'none'} disabled={!value?.enabled || pending || !mayControl} onChange={e => void fault(e.target.value)}>
      <option value="none">Normal</option><option value="frozen_data">Data membeku, heartbeat hidup</option><option value="invalid_data">Data Utara tidak valid</option><option value="sender_stopped">Pengirim berhenti</option>
    </select></label><p role="status">{message}</p></div>}
    <details className="decision-history"><summary>Riwayat keputusan ({value?.decisions.filter(d => d.outcome !== 'preview').length ?? 0})</summary>
      <div className="table-scroll"><table className="event-table"><thead><tr><th>Waktu</th><th>Arah / durasi</th><th>Status</th><th>Alasan</th></tr></thead><tbody>{value?.decisions.filter(d => d.outcome !== 'preview').map(d => <tr key={d.request_id}><td>{localTime(d.decided_at)}</td><td>{d.approach} / {d.green_seconds} dtk</td><td>{({accepted:'Menunggu',applied:'Diterapkan',rejected:'Ditolak',cancelled:'Dibatalkan',preview:'Pratinjau'})[d.outcome]}</td><td>{d.reason}</td></tr>)}</tbody></table></div>
    </details>
  </section>
}
