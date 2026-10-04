import { useCallback, useEffect, useRef, useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import schema from './schemas/TrafficView.json'
import type { TrafficView } from './types/TrafficView'
import { authGeneration, rejectSession } from './authEvents'

const ajv = new Ajv2020()
addFormats(ajv)
const valid = ajv.compile<TrafficView>(schema)
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
type Source = 'atcs_synthetic' | 'experiment'

export function coherentTraffic(data: TrafficView, source: Source, intersection: string) {
  if (data.source !== source || data.intersection_id !== intersection || !data.available || !data.signals) return false
  const directions = ['U', 'T', 'S', 'B']
  if (Object.keys(data.signals).length !== 4 || directions.some(d => data.signals![d as 'U'] !== (d === data.active_approach ? data.phase : 'red'))) return false
  if ((data.phase === 'all_red') !== (data.active_approach === null)) return false
  return source !== 'atcs_synthetic' || (data.speed === 1 && !data.emergency)
}

export function useTraffic(source: Source, intersection: string | undefined, enabled: boolean, csrf: string) {
  const [data, setData] = useState<TrafficView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [commandError, setCommandError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [revision, setRevision] = useState(0)
  const current = useRef<TrafficView | null>(null)
  const commandAbort = useRef<AbortController | null>(null)
  const locked = useRef(false)
  const generation = useRef(0)
  useEffect(() => {
    const owner = ++generation.current
    current.current = null
    setData(null)
    if (!enabled || !intersection) return
    let disposed = false
    let timer: ReturnType<typeof setTimeout>
    let watchdog: ReturnType<typeof setTimeout>
    let controller: AbortController | null = null
    let previous: TrafficView | null = null
    let progressAt = performance.now()
    let requestVersion = 0
    const stop = () => { requestVersion++; controller?.abort(); clearTimeout(timer); clearTimeout(watchdog) }
    const unavailable = (message: string) => { current.current = null; setData(null); setError(message) }
    async function poll() {
      if (disposed || document.hidden) return
      const version = ++requestVersion
      const request = new AbortController()
      controller = request
      const token = authGeneration()
      const timeout = setTimeout(() => request.abort(), 1800)
      const began = performance.now()
      try {
        const response = await fetch(`${base}/${source === 'experiment' ? 'simulation' : 'atcs/traffic'}`, { signal: request.signal, credentials: 'same-origin', cache: 'no-store' })
        if (response.status === 401 || response.status === 403) rejectSession(token)
        if (!response.ok) throw new Error('Layanan kendaraan belum tersedia.')
        const value: unknown = await response.json()
        if (!valid(value) || !coherentTraffic(value, source, intersection!)) throw new Error('Data kendaraan belum dapat diverifikasi.')
        if (disposed || request.signal.aborted || generation.current !== owner || version !== requestVersion) return
        const now = performance.now()
        if (now-began > 1800) throw new Error('Data kendaraan terlambat.')
        if (previous?.run_id === value.run_id && value.traffic_sequence < previous.traffic_sequence) throw new Error('Urutan kendaraan mundur.')
        if (previous?.run_id !== value.run_id || previous.traffic_sequence !== value.traffic_sequence || !value.running) progressAt = now
        if (value.running && now-progressAt > 2500) throw new Error('Mesin kendaraan tidak memperbarui data.')
        previous = value
        current.current = value
        setData(value)
        setError(null)
        clearTimeout(watchdog)
        watchdog = setTimeout(() => unavailable('Data kendaraan tidak mutakhir.'), 2500)
      } catch (cause) {
        if (!disposed && generation.current === owner && version === requestVersion && !document.hidden) unavailable(cause instanceof Error ? cause.message : 'Koneksi kendaraan terputus.')
      } finally {
        clearTimeout(timeout)
        if (!disposed && version === requestVersion && !document.hidden) timer = setTimeout(() => void poll(), 250)
      }
    }
    const resume = () => { stop(); unavailable(document.hidden ? 'Pemantauan kendaraan dijeda saat tab tersembunyi.' : 'Membaca keadaan terbaru…'); if (!document.hidden) void poll() }
    const offline = () => { stop(); unavailable('Koneksi terputus; posisi kendaraan disembunyikan.') }
    document.addEventListener('visibilitychange', resume)
    window.addEventListener('offline', offline)
    window.addEventListener('online', resume)
    void poll()
    return () => { disposed = true; stop(); document.removeEventListener('visibilitychange', resume); window.removeEventListener('offline', offline); window.removeEventListener('online', resume) }
  }, [source, intersection, enabled, revision])
  useEffect(() => () => commandAbort.current?.abort(), [])

  const command = useCallback(async (payload: Record<string, unknown>) => {
    if (locked.current || source !== 'experiment' || !current.current) return false
    locked.current = true
    setPending(true)
    setCommandError(null)
    const request = new AbortController()
    commandAbort.current = request
    const timeout = setTimeout(() => request.abort(), 5000)
    const token = authGeneration()
    try {
      const response = await fetch(`${base}/simulation/commands`, { method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: request.signal,
        headers: { 'Content-Type': 'application/json', 'X-SIGAP-Request': '1', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ ...payload, expected_run_id: current.current.run_id }) })
      if (response.status === 401 || response.status === 403) rejectSession(token)
      if (!response.ok) {
        const failure = await response.json().catch(() => null)
        throw new Error(failure?.detail?.message || 'Perintah tidak diterima.')
      }
      const value: unknown = await response.json()
      if (!valid(value) || !coherentTraffic(value, source, intersection!)) throw new Error('Balasan perintah tidak valid; periksa keadaan terbaru.')
      if (!request.signal.aborted) { current.current = value; setData(value); setError(null); setRevision(v => v+1) }
      return true
    } catch (cause) {
      if (!request.signal.aborted) setCommandError(cause instanceof Error ? cause.message : 'Perintah gagal.')
      else setCommandError('Konfirmasi perintah terputus; periksa keadaan terbaru sebelum mengulang.')
      return false
    } finally { clearTimeout(timeout); locked.current = false; setPending(false) }
  }, [source, csrf, intersection])
  return { data, error: commandError || error, pending, command }
}
