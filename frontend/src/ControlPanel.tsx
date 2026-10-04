import { localTime } from './traffic'
import type { useControl } from './useControl'

const states = { fixed_time: 'ATCS · fixed-time', activating: 'Pengambilalihan menunggu transisi', adaptive: 'SIGAP mengendalikan fase', returning_atcs: 'Kembali ke ATCS' }
const outcomes = { accepted: 'Diterima · menunggu penerapan', applied: 'Sudah diterapkan', rejected: 'Ditolak', cancelled: 'Dibatalkan' }
const eventLabels: Record<string, string> = { SOURCE_READY: 'Sumber siap', SOURCE_UNREADY: 'Sumber tidak siap',
  DATA_UNUSABLE: 'Data tidak layak', HEARTBEAT_LOST: 'Komunikasi SIGAP terputus', PLAN_EXPIRED: 'Keputusan kedaluwarsa',
  PLAN_MISSING: 'Keputusan belum tersedia', SOURCE_RESTART: 'Sumber dimulai ulang', OPERATOR_RELEASE: 'Pelepasan oleh operator',
  FIXED_TIME_RESUMED: 'ATCS kembali aktif', ACCEPTED: 'Permintaan diterima', PLAN_APPLIED: 'Fase diterapkan',
  CONTROL_ACQUIRED: 'SIGAP memperoleh kendali', RELEASED: 'Kendali dilepas', SUPERSEDED: 'Rencana diganti',
  ENGINE_STOPPED: 'Pengendali berhenti' }
const seconds = (value: number | null | undefined) => value == null ? 'Belum ada' : `${value.toFixed(1)} dtk`

export function ControlPanel({ control, mayControl }: { control: ReturnType<typeof useControl>; mayControl: boolean }) {
  const { status, error, receipt, commandError, pending, command } = control
  const canActivate = Boolean(status?.ready && status.source === 'cctv' && status.state === 'fixed_time' && mayControl && !pending)
  const canRelease = Boolean(status?.session_id && mayControl && !pending)
  return <section className="control-panel" aria-labelledby="control-title">
    <div className="section-toolbar"><div><p className="eyebrow">INTEGRASI SIGAP / ATCS</p><h2 id="control-title">Pengaturan kendali</h2><p>Pengendali ATCS memeriksa setiap permintaan sebelum mengubah lampu.</p></div>
      <span className={`phase-tag phase-tag--${status?.state === 'adaptive' ? 'green' : 'unknown'}`}>{status ? states[status.state] : 'Belum terverifikasi'}</span></div>
    <div className="control-body">
      <div className="control-summary"><h3>{status?.state === 'returning_atcs' ? 'ATCS mengambil alih secara aman' : status?.session_id ? 'Sesi SIGAP sedang diawasi' : 'ATCS tetap menjadi pengendali dasar'}</h3>
        <p>{error || status?.reason || 'Menghubungkan ke pengawas ATCS…'}</p>
        <p className="control-readiness">{status?.readiness_reason || 'Kesiapan sumber belum terverifikasi.'}</p>
        <div className="control-actions"><button disabled={!canActivate} onClick={() => void command('activate')}>Aktifkan kendali SIGAP</button><button className="secondary" disabled={!canRelease} onClick={() => void command('release')}>Kembalikan ke ATCS</button></div>
        {!mayControl && <p>Akun ini hanya memiliki akses pemantauan.</p>}
        <p className="control-caption">Setelah gangguan, sumber harus pulih dan operator mengaktifkan SIGAP kembali. Berpindah tab tidak mengubah kendali.</p>
      </div>
      <dl className="control-facts"><div><dt>Sumber keputusan</dt><dd>{status?.source === 'integration_test' ? 'Pengirim uji integrasi' : status?.source === 'cctv' ? 'Layanan CCTV' : 'Belum terhubung'}</dd></div>
        <div><dt>Heartbeat tersisa</dt><dd>{seconds(status?.heartbeat_remaining_seconds)}</dd></div><div><dt>Kesegaran data tersisa</dt><dd>{seconds(status?.data_remaining_seconds)}</dd></div>
        <div><dt>Perintah menunggu</dt><dd>{status?.pending_request_id ? 'Menunggu transisi aman' : 'Tidak ada'}</dd></div><div><dt>Gangguan / pelepasan terakhir</dt><dd>{status?.fallback_code ? eventLabels[status.fallback_code] || status.fallback_code : 'Tidak ada'}</dd></div></dl>
    </div>
    {pending && <p className="control-feedback" role="status">Mengirim permintaan ke ATCS…</p>}
    {commandError && <p className="control-feedback" role="alert">{commandError}</p>}
    {receipt && <div className="control-feedback" role="status"><strong>{outcomes[receipt.outcome]}</strong><p>{receipt.message}</p><small>Permintaan {receipt.request_id.slice(0, 8)} · {localTime(receipt.updated_at)} WIB</small></div>}
    <p className="control-scope">Tahap 3–4 menyediakan komunikasi, override, dan fallback. CCTV/YOLO serta pengambilan keputusan adaptif dari video belum terpasang. Pengujian memakai instance terpisah dengan data uji.</p>
    <div className="section-toolbar"><h3>Riwayat pengendalian</h3><span className="small-muted">100 kejadian terakhir · sesi ATCS saat ini</span></div>
    {status?.events.length ? <div className="table-scroll"><table className="event-table"><thead><tr><th scope="col">Waktu (WIB)</th><th scope="col">Kejadian</th><th scope="col">Keterangan</th></tr></thead><tbody>{[...status.events].reverse().map(event => <tr key={event.sequence}><td>{localTime(event.occurred_at)}</td><th scope="row">{eventLabels[event.code] || 'Permintaan diperiksa'}</th><td>{event.message}</td></tr>)}</tbody></table></div>
      : <p className="empty-history">{error ? 'Riwayat kendali belum dapat diverifikasi.' : 'Belum ada permintaan atau perubahan kesiapan pada sesi ini.'}</p>}
  </section>
}
