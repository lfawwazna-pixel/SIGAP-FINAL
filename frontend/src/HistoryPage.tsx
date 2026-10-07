import { useEffect, useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import schema from './schemas/EventArchivePage.json'
import type { EventArchivePage } from './types/EventArchivePage'
import type { SessionView } from './types/SessionView'
import { apiBase } from './useService'
import { authGeneration, rejectSession } from './authEvents'
import { eventNames, localTime, phaseNames } from './traffic'
import { SigapLogo } from './SigapLogo'

const ajv = new Ajv2020(); addFormats(ajv)
const valid = ajv.compile<EventArchivePage>(schema)
export function HistoryPage({session,onLogout,signingOut,logoutError}:{session:SessionView;onLogout:()=>void;signingOut?:boolean;logoutError?:string|null}) {
  const [page,setPage] = useState<EventArchivePage|null>(null)
  const [before,setBefore] = useState<number|null>(null)
  const [filter,setFilter] = useState('all')
  const [error,setError] = useState('')
  const [loading,setLoading] = useState(true)
  useEffect(() => {
    const abort = new AbortController(), generation = authGeneration()
    let disposed = false
    setLoading(true); setError(''); setPage(null)
    const timeout = setTimeout(() => abort.abort(),8000)
    async function load() {
      try {
        const query = new URLSearchParams({limit:'50',event_filter:filter})
        if (before !== null) query.set('before',String(before))
        const response = await fetch(`${apiBase}/history?${query}`,{credentials:'same-origin',cache:'no-store',signal:abort.signal})
        if (response.status === 401) rejectSession(generation)
        const data:unknown = await response.json()
        if (!response.ok || !valid(data) || data.filter !== filter || data.has_more !== (data.next_before !== null)) throw new Error('Arsip belum dapat dimuat atau diverifikasi.')
        if (!disposed && !abort.signal.aborted && generation === authGeneration()) setPage(data)
      } catch (cause) { if (!disposed && generation === authGeneration()) setError(cause instanceof Error && !abort.signal.aborted ? cause.message : 'Koneksi arsip terputus.') }
      finally { clearTimeout(timeout); if (!disposed && generation === authGeneration()) setLoading(false) }
    }
    void load()
    return () => { disposed = true; abort.abort(); clearTimeout(timeout) }
  },[before,filter])
  return <><header className="app-header"><a className="brand" href="/monitor" aria-label="SIGAP — kembali ke monitor"><SigapLogo /></a><span className="header-context">Arsip riwayat kejadian</span><nav><a href="/monitor">Kembali ke monitor</a></nav><span>{session.operator.display_name}</span><button onClick={onLogout} disabled={signingOut}>{signingOut ? 'Mengakhiri sesi…' : 'Keluar'}</button></header>
    <main>{logoutError && <p className="connection-note" role="alert">{logoutError}</p>}<div className="page-heading"><div><h1>Riwayat kejadian lengkap</h1><p>Arsip lokal dari semua sesi ATCS sejak pencatatan arsip diaktifkan. Riwayat tetap tersedia setelah aplikasi dimulai ulang.</p></div></div>
    <section className="history-panel" aria-label="Arsip riwayat"><div className="section-toolbar"><label className="history-filter">Tampilkan<select value={filter} onChange={e => {setFilter(e.target.value);setBefore(null)}}><option value="all">Semua kejadian</option><option value="phase">Pergantian fase</option><option value="incident">Gangguan &amp; penahanan</option></select></label><button disabled={loading || before===null} onClick={()=>setBefore(null)}>Kembali ke terbaru</button></div>
      {error && <p className="history-note" role="alert">{error}</p>}{loading ? <p className="map-rule">Memuat arsip…</p> : page?.events.length ? <div className="table-scroll"><table className="event-table"><thead><tr><th>Tanggal / waktu WIB</th><th>Kejadian</th><th>Fase / arah</th><th>Keterangan</th><th>Sesi</th></tr></thead><tbody>{page.events.map(event=><tr key={event.event_id}><td>{new Intl.DateTimeFormat('id-ID',{timeZone:'Asia/Jakarta',dateStyle:'medium'}).format(new Date(event.occurred_at))} · {localTime(event.occurred_at)}</td><th>{eventNames[event.event_type]}</th><td>{phaseNames[event.phase]} {event.active_approach}</td><td>{event.reason}</td><td>{event.run_id.slice(0,8)}</td></tr>)}</tbody></table></div> : !error && <p className="empty-history">Belum ada kejadian dalam arsip untuk pilihan ini.</p>}
      <div className="history-actions"><button disabled={loading || !page?.has_more} onClick={()=>setBefore(page!.next_before)}>Kejadian lebih lama</button><span>50 kejadian per halaman. Monitor hanya menampilkan 20 kejadian terakhir.</span></div>
    </section></main></>
}
