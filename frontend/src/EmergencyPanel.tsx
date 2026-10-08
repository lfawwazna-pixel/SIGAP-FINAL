import type { AdaptiveStatus } from './types/AdaptiveStatus'
import type { ControlStatus } from './types/ControlStatus'
import { directionNames } from './traffic'
const stages = { idle: 'Pemantauan normal', confirming: 'Memverifikasi EVP', confirmed: 'EVP terkonfirmasi', servicing: 'Prioritas EVP aktif', recovering: 'Pemulihan kendali', unavailable: 'EVP belum siap' }
export function EmergencyPanel({ emergency, control }: { emergency?: AdaptiveStatus['emergency']; control?: ControlStatus | null }) {
  if (!emergency || emergency.state === 'idle' && !control?.emergency_serving && !control?.emergency) return null
  const target = control?.emergency ?? emergency.target
  const serving = control?.emergency_serving === true
  const active = Boolean(control?.session_id && target)
  const recovering = emergency.state === 'recovering'
  return <section className={'evp-panel '+(active ? 'evp-panel--active' : '')} aria-label="Prioritas kendaraan darurat" role="status">
    <div className="evp-symbol" aria-hidden="true">✚</div>
    <div className="evp-copy"><p className="eyebrow">EMERGENCY VEHICLE PRIORITY</p>
      <h2>{serving ? stages.servicing : stages[emergency.state]}</h2>
      <p>{target ? (target.kind === 'ambulance' ? 'Ambulans' : 'Pemadam')+' · dari '+directionNames[target.direction]+' · ID '+target.track_id+' · keyakinan '+Math.round(target.confidence*100)+'%' : emergency.message}</p>
      <p className="small-muted">{recovering ? 'EVP selesai atau bukti hilang. Pengendali menyelesaikan kuning dan clearance sebelum prioritas berikutnya; keputusan adaptif normal dipulihkan melalui transisi ini.' : active ? 'Keputusan antrean ditangguhkan. Fokus kotak deteksi beralih ke EVP; pengamatan latar tetap tersedia. Lampu mengikuti transisi aman pengendali ATCS.' : target ? 'Aktifkan kendali SIGAP setelah keempat pendekat terkalibrasi. Deteksi saja belum memberikan prioritas lampu.' : 'Kendali normal berjalan; satu prediksi belum cukup untuk memicu prioritas.'}</p>
    </div>
    <ol className="evp-steps" aria-label="Urutan prioritas">
      <li data-current={!serving && active && !recovering}>Konfirmasi</li><li data-current={active && !serving && !recovering}>Kuning &amp; semua merah</li><li data-current={serving}>Layani EVP</li><li data-current={emergency.state === 'recovering'}>Pulihkan adaptif</li>
    </ol>
  </section>
}
