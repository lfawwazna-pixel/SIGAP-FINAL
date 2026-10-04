import { useEffect, useState } from 'react'
import { authGeneration, rejectSession } from './authEvents'

export const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export function useService<T>(path: string, validate: (data: unknown) => data is T, active = true) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [revision, refresh] = useState(0)
  useEffect(() => {
    if (!active) return
    let disposed = false
    let epoch = 0
    let timer: ReturnType<typeof setTimeout>
    let abort: AbortController | null = null
    async function poll() {
      if (document.hidden || disposed) return
      const attempt = ++epoch
      abort = new AbortController()
      const request = abort
      const generation = authGeneration()
      const timeout = setTimeout(() => request.abort(), 1800)
      try {
        const r = await fetch(apiBase+path, { credentials: 'same-origin', cache: 'no-store', signal: request.signal })
        if (r.status === 401) rejectSession(generation)
        const value: unknown = await r.json()
        if (!r.ok || !validate(value)) throw new Error('Data layanan belum tersedia.')
        if (!disposed && attempt === epoch && !request.signal.aborted && generation === authGeneration()) { setData(value); setError('') }
      } catch {
        if (!disposed && attempt === epoch) { setData(null); setError('Koneksi layanan terputus atau data tidak valid.') }
      } finally {
        clearTimeout(timeout)
        if (!disposed && attempt === epoch && !document.hidden) timer = setTimeout(() => void poll(), 1000)
      }
    }
    const visibility = () => { ++epoch; clearTimeout(timer); abort?.abort(); setData(null); if (!document.hidden) void poll() }
    document.addEventListener('visibilitychange', visibility)
    void poll()
    return () => { disposed = true; abort?.abort(); clearTimeout(timer); document.removeEventListener('visibilitychange', visibility) }
  }, [path, validate, active, revision])
  return { data, error, refresh: () => refresh(v => v+1) }
}

export async function postService(path: string, csrf: string, body: unknown, raw = false) {
  const generation = authGeneration()
  const abort = new AbortController()
  const timeout = setTimeout(() => abort.abort(), raw ? 120000 : 8000)
  try {
  const r = await fetch(apiBase+path, { method: 'POST', credentials: 'same-origin',
    signal: abort.signal,
    headers: { 'Content-Type': raw ? 'application/octet-stream' : 'application/json', 'X-SIGAP-Request': '1', 'X-CSRF-Token': csrf },
    body: raw ? body as Blob : JSON.stringify(body) })
  if (r.status === 401) rejectSession(generation)
  const result = await r.json()
  if (!r.ok) throw new Error(result?.detail?.message || 'Permintaan ditolak.')
  return result
  } finally { clearTimeout(timeout) }
}
