import { useEffect, useRef, useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import statusSchema from './schemas/ControlStatus.json'
import receiptSchema from './schemas/CommandReceipt.json'
import type { ControlStatus } from './types/ControlStatus'
import type { CommandReceipt } from './types/CommandReceipt'
import { authGeneration, rejectSession } from './authEvents'

const ajv = new Ajv2020()
addFormats(ajv)
const validStatus = ajv.compile<ControlStatus>(statusSchema)
const validReceipt = ajv.compile<CommandReceipt>(receiptSchema)
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export function useControl(intersection: string | undefined, csrf: string, mayControl: boolean, allowSynthetic = false) {
  const [status, setStatus] = useState<ControlStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<CommandReceipt | null>(null)
  const [commandError, setCommandError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const current = useRef<ControlStatus | null>(null)
  const lastRequest = useRef<{ id: string; run: string; action: string } | null>(null)
  const locked = useRef(false)
  const mounted = useRef(false)
  const post = useRef<AbortController | null>(null)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; post.current?.abort() }
  }, [])

  useEffect(() => {
    current.current = null
    setStatus(null)
    if (!intersection) return
    let disposed = false
    let version = 0
    let timer: ReturnType<typeof setTimeout>
    let watchdog: ReturnType<typeof setTimeout>
    let request: AbortController | null = null
    let previousTime = ''
    let progressAt = performance.now()
    const stop = () => { version++; request?.abort(); clearTimeout(timer); clearTimeout(watchdog) }
    const unavailable = (message: string) => { current.current = null; setStatus(null); setError(message) }
    async function poll() {
      if (disposed || document.hidden) return
      const mine = ++version
      const abort = new AbortController()
      request = abort
      const generation = authGeneration()
      const timeout = setTimeout(() => abort.abort(), 1800)
      try {
        const response = await fetch(`${base}/control`, { signal: abort.signal, cache: 'no-store', credentials: 'same-origin' })
        if (response.status === 401) rejectSession(generation)
        const data: unknown = await response.json()
        if (!response.ok || !validStatus(data) || data.intersection_id !== intersection || !data.available) throw new Error('Status kendali belum dapat diverifikasi.')
        if (disposed || abort.signal.aborted || mine !== version || generation !== authGeneration()) return
        if (previousTime !== data.observed_at) progressAt = performance.now()
        else if (performance.now()-progressAt > 2500) throw new Error('Pembaruan status kendali terhenti.')
        previousTime = data.observed_at
        current.current = data
        setStatus(data)
        setError(null)
        clearTimeout(watchdog)
        watchdog = setTimeout(() => unavailable('Status kendali tidak mutakhir.'), 2500)
        const last = lastRequest.current
        if (last && last.run === data.atcs_run_id) {
          const result = await fetch(`${base}/control/receipts/${last.id}`, { signal: abort.signal, credentials: 'same-origin', cache: 'no-store' })
          if (result.status === 401) rejectSession(generation)
          const value: unknown = await result.json()
          if (!disposed && !abort.signal.aborted && mine === version && generation === authGeneration()
              && result.ok && validReceipt(value) && value.request_id === last.id && value.atcs_run_id === last.run && value.action === last.action) {
            setReceipt(value)
            setCommandError(null)
            if (value.outcome !== 'accepted') lastRequest.current = null
          }
        } else if (last) {
          lastRequest.current = null
          setReceipt(null)
          setCommandError('Sesi ATCS berubah. Permintaan sebelumnya tidak berlaku untuk sesi baru.')
        }
      } catch (cause) {
        if (!disposed && mine === version) unavailable(cause instanceof Error ? cause.message : 'Koneksi kendali terputus.')
      } finally {
        clearTimeout(timeout)
        if (!disposed && mine === version && !document.hidden) timer = setTimeout(() => void poll(), 700)
      }
    }
    const resume = () => { stop(); unavailable(document.hidden ? 'Pemantauan dijeda saat halaman tersembunyi.' : 'Memeriksa kendali…'); if (!document.hidden) void poll() }
    const offline = () => { stop(); unavailable('Koneksi terputus; tindakan kendali dinonaktifkan.') }
    document.addEventListener('visibilitychange', resume)
    window.addEventListener('offline', offline)
    window.addEventListener('online', resume)
    void poll()
    return () => { disposed = true; stop(); document.removeEventListener('visibilitychange', resume); window.removeEventListener('offline', offline); window.removeEventListener('online', resume) }
  }, [intersection])

  async function command(action: 'activate' | 'release') {
    const state = current.current
    if (locked.current || !state || !mayControl || document.hidden) return
    const sourceAllowed = state.source === 'cctv' || (allowSynthetic && state.allow_test_source && state.source === 'integration_test')
    if (action === 'activate' && (!state.ready || !sourceAllowed || state.state !== 'fixed_time')) return
    if (action === 'release' && !state.session_id) return
    locked.current = true
    setPending(true)
    setCommandError(null)
    setReceipt(null)
    const id = crypto.randomUUID()
    lastRequest.current = { id, run: state.atcs_run_id, action }
    const abort = new AbortController()
    post.current = abort
    const timeout = setTimeout(() => abort.abort(), 5000)
    const generation = authGeneration()
    try {
      const response = await fetch(`${base}/control/commands`, { method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
        headers: { 'Content-Type': 'application/json', 'X-SIGAP-Request': '1', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ request_id: id, action, expected_run_id: state.atcs_run_id, expected_revision: state.revision }) })
      if (response.status === 401) rejectSession(generation)
      const value: unknown = await response.json()
      if (!validReceipt(value) || value.request_id !== id || value.atcs_run_id !== state.atcs_run_id || value.action !== action) {
        const failure = value as { detail?: { message?: string } }
        throw new Error(failure?.detail?.message || 'Hasil permintaan belum terkonfirmasi. Memeriksa tanda terima ATCS…')
      }
      if (mounted.current && !abort.signal.aborted && generation === authGeneration()) setReceipt(value)
    } catch (cause) {
      if (mounted.current && generation === authGeneration()) setCommandError(cause instanceof Error && !abort.signal.aborted ? cause.message : 'Konfirmasi terputus. Status kendali dan tanda terima akan diperiksa kembali.')
    } finally {
      clearTimeout(timeout)
      locked.current = false
      if (mounted.current) setPending(false)
    }
  }
  return { status, error, receipt, commandError, pending, command }
}
