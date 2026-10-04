import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Monitor } from './Monitor'
import { sessionFixture } from './testFixtures'
import { readSnapshot } from './api'
import type { Health } from './types/Health'

const health = (service: 'backend' | 'atcs'): Health => ({
  service, stage: '2B', liveness: 'alive', foundation_ready: service === 'atcs',
  checked_at: '2026-10-03T08:00:00Z', configuration: 'valid',
  database: service === 'atcs' ? { status: 'not_required', schema_status: 'not_required' }
    : { status: 'not_configured', schema_status: 'unknown' },
  capabilities: { phase_engine: service === 'atcs' ? 'running' : 'not_hosted', authentication: 'not_implemented', override: 'not_implemented', ai: 'not_implemented', cctv: 'not_configured' },
})
const App = () => <Monitor session={sessionFixture()} onLogout={() => undefined} signingOut={false} logoutError={null} />
const respond = (data: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(data), { status }))
const fetchHealthy = (url: string) => {
  if (url.endsWith('/atcs/health')) return respond(health('atcs'))
  if (url.endsWith('/health')) return respond(health('backend'), 503)
  return respond({}, 503)
}
const row = (name: string) => within(screen.getByRole('row', { name: new RegExp(name) }))

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('API readiness', () => {
  it('accepts a valid backend 503 while keeping database unready', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchHealthy))
    const result = await readSnapshot(new AbortController().signal)
    expect(result.backend.state).toBe('ready')
    if (result.backend.state === 'ready') expect(result.backend.data.foundation_ready).toBe(false)
    expect(result.atcs.state).toBe('ready')
  })

  it('rejects an incomplete health payload even on HTTP 200', async () => {
    vi.stubGlobal('fetch', vi.fn(() => respond({ liveness: 'alive' })))
    const result = await readSnapshot(new AbortController().signal)
    expect(result.backend.state).toBe('unavailable')
    expect(result.atcs.state).toBe('unavailable')
  })

  it('rejects the wrong service identity', async () => {
    vi.stubGlobal('fetch', vi.fn(() => respond(health('backend'))))
    expect((await readSnapshot(new AbortController().signal)).atcs.state).toBe('unavailable')
  })
})

describe('Readiness screen', () => {
  it('distinguishes API alive, database not configured, and a running phase engine', async () => {
    vi.stubGlobal('fetch', vi.fn(fetchHealthy))
    render(<App />)
    await waitFor(() => expect(row('API aplikasi').getByText('Hidup')).toBeTruthy())
    expect(row('Database').getByText('Belum dikonfigurasi')).toBeTruthy()
    expect(row('Layanan ATCS').getByText('Hidup')).toBeTruthy()
    expect(row('Mesin fase').getByText('Berjalan')).toBeTruthy()
    expect(row('Autentikasi operator').getByText('Belum dibuat')).toBeTruthy()
    expect(screen.queryByText(/\d+ detik tersisa/)).toBeNull()
  })

  it('keeps ATCS API alive while displaying a phase engine fault', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.endsWith('/atcs/health')) return respond({ ...health('atcs'), foundation_ready: false,
        capabilities: { ...health('atcs').capabilities, phase_engine: 'faulted' } }, 503)
      return fetchHealthy(url)
    }))
    render(<App />)
    await waitFor(() => expect(row('Mesin fase').getByText('Gangguan mesin')).toBeTruthy())
    expect(row('Layanan ATCS').getByText('Hidup')).toBeTruthy()
  })

  it('replaces previously healthy statuses after losing connection', async () => {
    const fetch = vi.fn(fetchHealthy)
    vi.stubGlobal('fetch', fetch)
    render(<App />)
    await waitFor(() => expect(row('API aplikasi').getByText('Hidup')).toBeTruthy())
    fetch.mockRejectedValue(new TypeError('Network unavailable'))
    fireEvent.click(screen.getByRole('button', { name: 'Periksa ulang' }))
    await waitFor(() => expect(row('API aplikasi').getByText('Tidak tersedia')).toBeTruthy())
    expect(row('Database').getByText('Tidak tersedia')).toBeTruthy()
    expect(row('Layanan ATCS').getByText('Tidak tersedia')).toBeTruthy()
    expect(screen.getByText(/Konfigurasi simpang belum tersedia/)).toBeTruthy()
  })
})
