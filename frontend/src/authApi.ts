import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import sessionSchema from './schemas/SessionView.json'
import type { SessionView } from './types/SessionView'

const ajv = new Ajv2020()
addFormats(ajv)
const validSession = ajv.compile<SessionView>(sessionSchema)
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
export type AuthResult = { kind: 'authenticated'; session: SessionView } | { kind: 'guest'; message: string } | { kind: 'error'; message: string }

async function request(path: string, signal: AbortSignal, init?: RequestInit): Promise<Response> {
  const abort = new AbortController()
  const cancel = () => abort.abort()
  signal.addEventListener('abort', cancel, { once: true })
  if (signal.aborted) abort.abort()
  const timer = setTimeout(cancel, 7000)
  try {
    const response = await fetch(`${base}/auth${path}`, { ...init, signal: abort.signal, credentials: 'same-origin', cache: 'no-store' })
    // Include body receipt in the timeout, not just response headers.
    const body = await response.text()
    return new Response(body || null, { status: response.status, headers: response.headers })
  } finally { clearTimeout(timer); signal.removeEventListener('abort', cancel) }
}

async function sessionResult(response: Response, isLogin = false): Promise<AuthResult> {
  if (response.status === 401) return { kind: 'guest', message: isLogin ? 'Nama pengguna atau kata sandi salah.' : '' }
  if (response.status === 429) return { kind: 'error', message: 'Percobaan masuk dibatasi sementara. Tunggu satu menit lalu coba lagi.' }
  if (response.status === 403) return { kind: 'error', message: 'Halaman ini belum diizinkan untuk masuk. Hubungi pengelola sistem.' }
  if (response.status === 422) return { kind: 'error', message: 'Periksa nama pengguna dan kata sandi, lalu coba lagi.' }
  if (!response.ok) return { kind: 'error', message: 'Layanan akun belum tersedia. Coba lagi setelah layanan pulih.' }
  const data: unknown = await response.json()
  if (!validSession(data)) return { kind: 'error', message: 'Sesi belum dapat diverifikasi. Coba masuk kembali.' }
  return { kind: 'authenticated', session: data }
}

export async function restoreSession(signal: AbortSignal): Promise<AuthResult> {
  try { return await sessionResult(await request('/session', signal)) }
  catch { return { kind: 'error', message: 'Koneksi ke layanan akun terputus. Periksa koneksi dan coba lagi.' } }
}
export async function login(username: string, password: string, signal: AbortSignal): Promise<AuthResult> {
  try {
    return await sessionResult(await request('/login', signal, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-SIGAP-Request': '1' }, body: JSON.stringify({ username, password }) }), true)
  } catch { return { kind: 'error', message: 'Koneksi terputus saat masuk. Coba lagi setelah layanan pulih.' } }
}
export async function logout(csrf: string, signal: AbortSignal): Promise<string | null> {
  try {
    const response = await request('/logout', signal, { method: 'POST', headers: { 'X-SIGAP-Request': '1', 'X-CSRF-Token': csrf } })
    if (response.status === 204 || response.status === 401) return null
    if (response.status === 403) return 'Sesi halaman berubah. Muat ulang halaman sebelum keluar.'
    return 'Sesi belum berhasil diakhiri. Coba keluar kembali setelah layanan pulih.'
  } catch { return 'Koneksi terputus. Pengakhiran sesi belum terkonfirmasi; coba keluar kembali.' }
}
