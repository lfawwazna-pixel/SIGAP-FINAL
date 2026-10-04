import type { Resource, Snapshot } from './api'
import type { Health } from './types/Health'
type Tone = 'good' | 'attention' | 'quiet' | 'unavailable'
interface Row { name: string; description: string; label: string; tone: Tone }

function missing(resource: Resource<Health>): Pick<Row, 'label' | 'tone'> {
  return resource.state === 'loading'
    ? { label: 'Memeriksa…', tone: 'quiet' }
    : { label: 'Tidak tersedia', tone: 'unavailable' }
}

function rowsFor(snapshot: Snapshot): Row[] {
  const { backend, atcs } = snapshot
  const database = backend.state === 'ready' ? backend.data.database : null
  let dbStatus: Pick<Row, 'label' | 'tone'> = missing(backend)
  if (database) {
    if (database.status === 'reachable') dbStatus = database.schema_status === 'current'
      ? { label: 'Terhubung · skema siap', tone: 'good' }
      : { label: 'Terhubung · perlu migrasi', tone: 'attention' }
    else if (database.status === 'not_configured') dbStatus = { label: 'Belum dikonfigurasi', tone: 'attention' }
    else dbStatus = { label: 'Tidak terhubung', tone: 'unavailable' }
  }
  const capability = (resource: Resource<Health>, key: keyof Health['capabilities']): Pick<Row, 'label' | 'tone'> => {
    if (resource.state !== 'ready') return missing(resource)
    const value = resource.data.capabilities[key]
    if (value === 'available') return { label: key === 'authentication' ? 'Tersedia · sesi operator' : 'Tersedia', tone: 'good' }
    if (value === 'unavailable') return { label: 'Belum tersedia', tone: 'unavailable' }
    if (value === 'running') return { label: 'Berjalan', tone: 'good' }
    if (value === 'faulted') return { label: 'Gangguan mesin', tone: 'unavailable' }
    if (value === 'stalled') return { label: 'Pembaruan terhenti', tone: 'unavailable' }
    if (value === 'stopped') return { label: 'Berhenti', tone: 'attention' }
    if (value === 'not_hosted') return { label: 'Dijalankan di ATCS', tone: 'quiet' }
    return { label: value === 'not_configured' ? 'Belum dikonfigurasi' : 'Belum dibuat', tone: 'quiet' }
  }
  return [
    { name: 'API aplikasi', description: 'Koneksi ke backend SIGAP', ...(backend.state === 'ready' ? { label: 'Hidup', tone: 'good' as const } : missing(backend)) },
    { name: 'Database', description: 'PostgreSQL dan migrasi akun operator', ...dbStatus },
    { name: 'Layanan ATCS', description: 'Proses terpisah; diperiksa melalui backend', ...(atcs.state === 'ready' ? { label: 'Hidup', tone: 'good' as const } : missing(atcs)) },
    { name: 'Mesin fase', description: 'Urutan lampu dan timer ATCS', ...capability(atcs, 'phase_engine') },
    { name: 'Override & fallback', description: 'Protokol kendali dan pengawas gangguan pada ATCS', ...capability(atcs, 'override') },
    { name: 'Autentikasi operator', description: 'Login dan sesi pengguna', ...capability(backend, 'authentication') },
    { name: 'Deteksi kendaraan', description: 'Pemrosesan model YOLO', ...capability(backend, 'ai') },
    { name: 'Sumber CCTV', description: 'Koneksi video persimpangan', ...capability(backend, 'cctv') },
  ]
}

export function Readiness({ snapshot }: { snapshot: Snapshot }) {
  return <details className="readiness" id="services">
    <summary>Kesiapan layanan <span>Diperiksa otomatis setiap 10 detik</span></summary>
    <div className="table-scroll"><table>
      <thead><tr><th scope="col">Komponen</th><th scope="col">Cakupan</th><th scope="col">Status dari layanan</th></tr></thead>
      <tbody>{rowsFor(snapshot).map(row => <tr key={row.name}><th scope="row">{row.name}</th><td>{row.description}</td><td><span className={`status status--${row.tone}`}><span aria-hidden="true" />{row.label}</span></td></tr>)}</tbody>
    </table></div>
  </details>
}
