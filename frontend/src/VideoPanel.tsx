import { useEffect, useRef, useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import schema from './schemas/VideoStatus.json'
import type { VideoStatus, VideoCalibration, Point } from './types/VideoStatus'
import { directions, directionNames, type Direction } from './traffic'
import { apiBase, postService, useService } from './useService'
import { authGeneration, rejectSession } from './authEvents'

const ajv = new Ajv2020(); addFormats(ajv)
const valid = ajv.compile<VideoStatus>(schema)
const stateNames = { empty:'Belum diatur', ready:'Siap', connecting:'Menghubungkan', playing:'Berjalan', paused:'Dijeda', ended:'Selesai', error:'Gangguan', stale:'Frame terlambat' }
type Target = 'outer' | 'middle' | 'inner' | 'stop_line'
const names = { outer: 'Lajur kiri', middle: 'Lajur tengah', inner: 'Lajur kanan', stop_line: 'Garis henti' }
const colors = { outer: '#edc65e', middle: '#57bfe5', inner: '#ed89b0', stop_line: '#ffffff' }
const empty = (): Record<Target, Point[]> => ({ outer: [], middle: [], inner: [], stop_line: [] })
const calibrationPoints = (c: VideoCalibration | null | undefined): Record<Target, Point[]> => c ?
  { outer: c.lanes.outer, middle: c.lanes.middle, inner: c.lanes.inner, stop_line: c.stop_line } : empty()

/** This component stays mounted when ATCS/SIGAP views change. Decoder lives on server. */
export function VideoPanel({ workspace, csrf, mayControl }: { workspace: 'atcs'|'sigap'|'simulation'; csrf: string; mayControl: boolean }) {
  const feed = useService('/video', valid)
  const [direction, setDirection] = useState<Direction>('U')
  const [url, setUrl] = useState('')
  const [frameKey, setFrameKey] = useState('')
  const [frameSeconds, setFrameSeconds] = useState('')
  const [trackedFrame, setTrackedFrame] = useState(false)
  const [frameTrackCount, setFrameTrackCount] = useState<number | null>(null)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const [editing, setEditing] = useState(false)
  const [queueVisible, setQueueVisible] = useState(false)
  const [target, setTarget] = useState<Target>('outer')
  const [points, setPoints] = useState(empty)
  const channel = feed.data?.channels.find(v => v.direction === direction)
  const session = channel?.source_session
  useEffect(() => { setEditing(false); setPoints(empty()) }, [direction, session])
  const playState = channel?.state
  const frameVisible = playState === 'playing' || playState === 'paused'
  const currentUrl = useRef('')
  const overlay = useRef(workspace === 'sigap')
  overlay.current = workspace === 'sigap'
  useEffect(() => {
    setEditing(false); setPoints(empty()); setMessage('')
  }, [direction, session])
  useEffect(() => {
    let disposed = false
    let epoch = 0
    let timer: ReturnType<typeof setTimeout>
    let abort: AbortController | null = null
    const clear = () => { if (currentUrl.current) URL.revokeObjectURL(currentUrl.current); currentUrl.current = ''; setUrl(''); setFrameKey(''); setFrameSeconds(''); setTrackedFrame(false); setFrameTrackCount(null) }
    clear()
    if (!session || !frameVisible) return
    async function frame() {
      if (disposed || document.hidden) return
      const attempt = ++epoch
      abort = new AbortController()
      const request = abort
      const generation = authGeneration()
      const wantOverlay = overlay.current
      const timeout = setTimeout(() => request.abort(), 1800)
      try {
        const r = await fetch(`${apiBase}/video/${direction}/frame?overlay=${wantOverlay}`, { credentials: 'same-origin', cache: 'no-store', signal: request.signal })
        if (r.status === 401) rejectSession(generation)
        if (!r.ok || r.headers.get('X-Source-Session') !== session || !r.headers.get('Content-Type')?.startsWith('image/jpeg')) throw new Error('Frame tidak tersedia')
        const blob = await r.blob()
        if (!disposed && attempt === epoch && !request.signal.aborted && generation === authGeneration() && wantOverlay === overlay.current) {
          const next = URL.createObjectURL(blob)
          if (currentUrl.current) URL.revokeObjectURL(currentUrl.current)
          currentUrl.current = next; setUrl(next); setFrameKey(r.headers.get('X-Frame-Id') || '')
          setFrameSeconds(r.headers.get('X-Media-Seconds') || ''); setTrackedFrame(r.headers.get('X-Tracking') === 'ByteTrack')
          const count = r.headers.get('X-Track-Count')
          setFrameTrackCount(count !== null && /^\d+$/.test(count) ? Number(count) : null)
        }
      } catch { if (!disposed && attempt === epoch) clear() }
      finally { clearTimeout(timeout); if (!disposed && attempt === epoch && !document.hidden) timer = setTimeout(() => void frame(), 200) }
    }
    const visibility = () => { ++epoch; clearTimeout(timer); abort?.abort(); clear(); if (!document.hidden) void frame() }
    document.addEventListener('visibilitychange', visibility)
    void frame()
    return () => { disposed = true; abort?.abort(); clearTimeout(timer); clear(); document.removeEventListener('visibilitychange', visibility) }
  }, [direction, session, frameVisible])

  async function send(action: string, calibration?: VideoCalibration) {
    if (!channel || pending) return
    setPending(true)
    try { await postService(`/video/${direction}/commands`, csrf, { action, expected_session: channel.source_session, ...(calibration ? { calibration } : {}) }); feed.refresh(); setMessage('Pengaturan sumber bersama diperbarui.'); if (calibration) setEditing(false) }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Gagal memperbarui video.') }
    finally { setPending(false) }
  }
  async function upload(file?: File) {
    if (!file || !channel || pending) return
    if (file.size > 256*1024*1024) { setMessage('Ukuran video maksimal 256 MB.'); return }
    setPending(true)
    try { await postService(`/video/${direction}/upload?expected_session=${channel.source_session}`, csrf, file, true); feed.refresh(); setMessage('Rekaman utama tersimpan dan langsung berjalan. Tandai lajur bila diperlukan.') }
    catch (e) { setMessage(e instanceof Error ? e.message : 'Unggah gagal.') }
    finally { setPending(false) }
  }
  const draw = editing ? points : calibrationPoints(channel?.calibration)
  const canSave = (['outer','middle','inner'] as const).every(k => points[k].length >= 3) && points.stop_line.length === 2
  return <section className="video-panel" aria-label="Video bersama ATCS dan SIGAP" hidden={workspace === 'simulation'}>
    <div className="section-toolbar"><div><p className="eyebrow">SUMBER VIDEO BERSAMA</p><h2>CCTV &amp; rekaman</h2><p>Satu sesi video untuk ATCS dan SIGAP. Berpindah tampilan tidak mengulang video.</p></div><span className="environment-tag">{channel?.source === 'live' ? 'CCTV langsung' : channel?.source === 'recording' ? 'Video rekaman' : 'Belum ada sumber'}</span></div>
    <div className="video-layout"><div>
      <div className="video-directions" role="group" aria-label="Pilih kamera">{directions.map(d => <button key={d} aria-pressed={direction === d} onClick={() => setDirection(d)}>{d} {directionNames[d]}<small>{stateNames[feed.data?.channels.find(v => v.direction === d)?.state || 'empty']}</small></button>)}</div>
      <div className={`video-frame${editing ? ' is-editing' : ''}`}>
        {url ? <><img src={url} alt={`Video pendekat ${directionNames[direction]}`} /><svg viewBox="0 0 1000 1000" preserveAspectRatio="none" role="img" aria-label="Area lajur dan garis henti" onClick={e => {
          if (!editing) return
          const bounds = e.currentTarget.getBoundingClientRect()
          const point = { x: Math.max(0, Math.min(1, (e.clientX-bounds.left)/bounds.width)), y: Math.max(0, Math.min(1, (e.clientY-bounds.top)/bounds.height)) }
          setPoints(old => ({ ...old, [target]: [...(target === 'stop_line' && old[target].length === 2 ? [] : old[target]), point].slice(0, target === 'stop_line' ? 2 : 12) }))
        }}>{(Object.keys(draw) as Target[]).map(k => <g key={k}>{k === 'stop_line' ? <polyline points={draw[k].map(p => `${p.x*1000},${p.y*1000}`).join(' ')} fill="none" stroke={colors[k]} strokeWidth="4" /> : <polygon points={draw[k].map(p => `${p.x*1000},${p.y*1000}`).join(' ')} fill={colors[k]} fillOpacity=".13" stroke={colors[k]} strokeWidth="3" />}{draw[k].map((p,i) => <circle key={i} cx={p.x*1000} cy={p.y*1000} r="5" fill={colors[k]} />)}</g>)}</svg></> : <div className="video-empty"><strong>{channel ? stateNames[channel.state] : 'Memeriksa sumber video'}</strong><p>{feed.error || channel?.message || 'Belum menerima status sumber.'}</p></div>}
      </div>
      <div className="video-caption"><span>{channel?.label || 'Belum ada video'} · {channel ? stateNames[channel.state] : 'Belum tersedia'}</span><span>{channel?.source === 'recording' ? `${frameSeconds ? Number(frameSeconds).toFixed(1) : '—'} dtk · ` : ''}Frame {frameKey || '—'}</span></div>
      {workspace === 'sigap' && <div className="video-detection-note" role="status"><strong>{trackedFrame ? `YOLO26s + ByteTrack${frameTrackCount === null ? '' : ` · ${frameTrackCount} kendaraan dalam zona`}` : channel?.tracking?.state === 'disabled' || !channel?.tracking ? 'YOLO belum diaktifkan' : 'Video asli · tracking belum tersedia'}</strong><p>{channel?.tracking?.message || 'Video tampil tanpa deteksi.'}</p>{channel?.detection_ready && <p>Tracking kamera: {channel.tracking?.observed_fps?.toFixed(1) ?? '—'} FPS · Pemrosesan: {channel.tracking?.processing_fps?.toFixed(1) ?? '—'} FPS · {channel.tracking?.device === 'cpu' ? 'CPU' : 'GPU'}</p>}<p>Tracking stabil: kendaraan yang terlewat sesaat ditahan paling lama 1,2 detik; kotak bertanda ~ memakai posisi terakhir. Hanya titik tengah bawah kotak di dalam zona tersimpan yang dihitung dan ditampilkan di peta.</p><p>Pratinjau maksimal 5 FPS. Kalibrasi empat pendekat diperlukan sebelum kendali SIGAP diaktifkan.</p></div>}
    </div><div className="video-settings">
      <h3>Atur sumber {directionNames[direction]}</h3>
      <label>Unggah rekaman MP4<input aria-label="Unggah rekaman MP4" type="file" accept="video/mp4,.mp4" disabled={!channel || pending || !mayControl} onChange={e => { void upload(e.target.files?.[0]); e.target.value = '' }} /></label>
      <p className="small-muted">Maksimal 256 MB. Rekaman berjalan otomatis dan berulang terus; pratinjau 5 FPS tanpa audio. Sumber baru mengganti video serta penandaan pendekat ini.</p>
      <button disabled={!channel?.live_configured || pending || !mayControl} onClick={() => void send('use_live')}>Hubungkan CCTV langsung</button>
      {!channel?.live_configured && <p className="small-muted">Alamat kamera langsung belum tersedia.</p>}
      <p className="small-muted">Sumber tersimpan aktif otomatis setelah restart. ATCS menampilkan video asli; SIGAP menampilkan tracking dari frame yang sama.</p>
      <button disabled={!url || pending || !mayControl} onClick={() => { setPoints(calibrationPoints(channel?.calibration)); setQueueVisible(channel?.calibration?.upstream_queue_visible ?? false); setEditing(v => !v) }}>{editing ? 'Batal penandaan' : 'Tandai lajur & garis henti'}</button>
      {editing && <div className="calibration-tools"><label>Area yang ditandai<select value={target} onChange={e => setTarget(e.target.value as Target)}>{Object.entries(names).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label><p>Klik 3–12 titik mengelilingi tiap lajur masuk sebelum garis henti, tanpa tumpang tindih; garis henti cukup 2 titik. Kiri untuk ruas pintas, tengah lurus, kanan belok kanan. Kalibrasi berlaku untuk seluruh putaran rekaman.</p><label><input type="checkbox" checked={queueVisible} onChange={e => setQueueVisible(e.target.checked)} />Ujung seluruh antrean terlihat di video</label><p className="small-muted">Biarkan tidak dicentang jika kendaraan berlanjut di luar gambar atau tertutup kendaraan di depan.</p><button onClick={() => setPoints(old => ({ ...old, [target]: [] }))}>Hapus titik area ini</button><button disabled={!canSave || pending} onClick={() => void send('calibrate', { upstream_queue_visible:queueVisible, lanes: { outer:points.outer, middle:points.middle, inner:points.inner }, stop_line:[points.stop_line[0], points.stop_line[1]] })}>Simpan penandaan</button><p className="small-muted">Titik bawah kotak kendaraan dipakai untuk menentukan lajur, estimasi antrean, dan posisi skematis pada peta. Kalibrasi tidak mengukur jarak lapangan.</p></div>}
      <p role="status">{pending ? 'Memproses…' : message}</p>
    </div></div>
  </section>
}
