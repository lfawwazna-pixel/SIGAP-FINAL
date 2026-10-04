import { act, cleanup, fireEvent, render, renderHook, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Monitor } from './Monitor'
import { readStatus } from './api'
import { useJournal, useMonitor } from './useMonitor'
import { config, eventFixture, pageFixture, respond, runId, secondRunId, sessionFixture, statusFixture } from './testFixtures'
import type { AtcsStatus } from './types/AtcsStatus'

let report: AtcsStatus
const App = () => <Monitor session={sessionFixture()} onLogout={() => undefined} signingOut={false} logoutError={null} />
let unavailable: boolean
let frozen: boolean
let requests: string[]
let nextSequence: number
const flush = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms) }) }

beforeEach(() => {
  vi.useFakeTimers()
  report = statusFixture()
  unavailable = false
  frozen = false
  nextSequence = 22
  requests = []
  vi.stubGlobal('fetch', vi.fn((input: string) => {
    requests.push(input)
    if (input.endsWith('/configuration')) return respond(config)
    if (input.endsWith('/atcs/status')) {
      if (unavailable) return Promise.reject(new TypeError('Disconnected'))
      return respond({ ...report, sequence_number: frozen ? report.sequence_number : nextSequence++ }, report.availability === 'available' ? 200 : 503)
    }
    if (input.includes('/atcs/events?')) {
      const after = Number(new URL(input, 'http://localhost').searchParams.get('after'))
      return respond(pageFixture({ events: after ? [] : [eventFixture()] }))
    }
    return respond({}, 503)
  }))
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('ATCS monitoring lifecycle', () => {
  it('reads the countdown without decrementing it in the browser', async () => {
    const { result } = renderHook(() => useMonitor(config.intersection_id, 0))
    await flush()
    expect(result.current.connection).toBe('live')
    await flush(1200)
    expect(result.current.status.state === 'ready' && result.current.status.data.remaining_seconds).toBe(84.9)
    expect(requests.filter(url => url.endsWith('/atcs/status')).length).toBe(3)
  })
  it('clears lamps on disconnect and recovers only from a new valid response', async () => {
    const { result } = renderHook(() => useMonitor(config.intersection_id, 0))
    await flush()
    unavailable = true
    await flush(500)
    expect(result.current.connection).toBe('unavailable')
    expect(result.current.status.state).toBe('unavailable')
    unavailable = false
    await flush(500)
    expect(result.current.connection).toBe('live')
  })
  it('expires a frozen sequence even if HTTP responses continue succeeding', async () => {
    frozen = true
    const { result } = renderHook(() => useMonitor(config.intersection_id, 0))
    await flush()
    await flush(2000)
    expect(result.current.connection).toBe('stale')
    expect(result.current.status.state).toBe('unavailable')
  })
  it('times out hanging requests and never leaves a live status indefinitely', async () => {
    const { result } = renderHook(() => useMonitor(config.intersection_id, 0))
    await flush()
    vi.mocked(fetch).mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new Error('aborted')))
    }))
    await flush(2400)
    expect(result.current.status.state).toBe('unavailable')
  })
  it('clears on tab hiding, fetches on return, and ignores late aborted replies', async () => {
    const { result } = renderHook(() => useMonitor(config.intersection_id, 0))
    await flush()
    let finishOld: (value: Response) => void = () => undefined
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    await flush(500)
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(result.current.connection).toBe('paused')
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    await flush()
    expect(result.current.connection).toBe('live')
    await act(async () => { finishOld(new Response(JSON.stringify(statusFixture({ run_id: secondRunId })))); await Promise.resolve() })
    expect(result.current.runId).toBe(runId)
  })
  it('rejects old server samples and wrong intersection identity', async () => {
    report = statusFixture({ updated_at: '2026-10-03T08:00:00Z' })
    const { result } = renderHook(() => useMonitor(config.intersection_id, 0))
    await flush()
    expect(result.current.connection).toBe('stale')
    report = statusFixture({ intersection_id: 'wrong' })
    await flush(500)
    expect(result.current.connection).toBe('unavailable')
  })
  it('accepts a valid 503 fault report but does not show it as live', async () => {
    report = statusFixture({ availability: 'unavailable', engine_state: 'faulted', remaining_seconds: null })
    expect((await readStatus(new AbortController().signal)).state).toBe('ready')
    const { result } = renderHook(() => useMonitor(config.intersection_id, 0))
    await flush()
    expect(result.current.connection).toBe('unavailable')
  })
})

describe('intersection operator screen', () => {
  it('shows four independent slip roads, yield signs and both lane rules per approach', async () => {
    const { container } = render(<App />)
    await flush()
    expect(container.querySelectorAll('[data-slip-road]')).toHaveLength(4)
    expect(container.querySelectorAll('[data-island]')).toHaveLength(4)
    expect(screen.getAllByRole('img', { name: /Beri jalan pada penggabungan/ })).toHaveLength(4)
    expect(screen.getAllByRole('img', { name: /Rambu .* lajur/ })).toHaveLength(8)
    expect(screen.getByRole('img', { name: 'Lampu Utara: Hijau' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Lampu Timur: Merah' })).toBeTruthy()
    expect(screen.getByTestId('countdown').textContent).toBe('85')
    fireEvent.keyDown(screen.getByRole('button', { name: 'Pilih pendekat Timur' }), { key: 'Enter' })
    expect(screen.getByRole('button', { name: 'Detail Timur' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByText('Lurus ke Barat / kiri ke Selatan')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Rute terpilih' }))
    expect(container.querySelector('.selected-routes')).toBeNull()
    expect(container.querySelectorAll('[data-slip-road]')).toHaveLength(4)
    expect(requests.every(url => url.startsWith('/api/'))).toBe(true)
  })
  it('renders yellow and all-red holding from the API, not from a UI timer', async () => {
    render(<App />)
    await flush()
    report = statusFixture({ phase: 'yellow', signals: { U: 'yellow', T: 'red', S: 'red', B: 'red' }, remaining_seconds: 2.4 })
    await flush(500)
    expect(screen.getByRole('img', { name: 'Lampu Utara: Kuning' })).toBeTruthy()
    expect(screen.getByTestId('countdown').textContent).toBe('03')
    report = statusFixture({ phase: 'all_red', active_approach: null, signals: { U: 'red', T: 'red', S: 'red', B: 'red' }, remaining_seconds: null, clearance_state: 'waiting_conflict' })
    await flush(500)
    expect(screen.getAllByRole('img', { name: /Lampu .*: Merah/ })).toHaveLength(4)
    expect(screen.getByTestId('countdown').textContent).toBe('—')
    expect(screen.getByText(/Menunggu area konflik bebas/)).toBeTruthy()
  })
  it('keeps the geometry but removes previously green lamps and countdown on a status outage', async () => {
    render(<App />)
    await flush()
    unavailable = true
    await flush(500)
    expect(screen.queryByRole('img', { name: 'Lampu Utara: Hijau' })).toBeNull()
    expect(screen.getAllByRole('img', { name: /Lampu .*: Belum diketahui/ })).toHaveLength(4)
    expect(screen.getByTestId('countdown').textContent).toBe('—')
    expect(screen.getByText(/belum membuktikan proses ATCS berhenti/)).toBeTruthy()
  })
  it('filters real events without inserting example history', async () => {
    render(<App />)
    await flush()
    const history = within(screen.getByRole('region', { name: 'Riwayat kejadian' }))
    expect(history.getByText('Sesi dimulai dengan semua merah.')).toBeTruthy()
    fireEvent.change(screen.getByRole('combobox', { name: 'Tampilkan' }), { target: { value: 'phase' } })
    expect(history.queryByText('Sesi dimulai dengan semua merah.')).toBeNull()
    expect(history.getByText('Belum ada kejadian untuk pilihan ini.')).toBeTruthy()
  })
  it('does not render an invented map while configuration is invalid', async () => {
    vi.mocked(fetch).mockImplementation(() => respond({}, 200))
    render(<App />)
    await flush()
    expect(screen.queryByRole('group', { name: 'Peta interaktif persimpangan empat arah' })).toBeNull()
    expect(screen.getByText('Peta belum dapat ditampilkan')).toBeTruthy()
    expect(screen.getByTestId('countdown').textContent).toBe('—')
  })
})

describe('journal session isolation', () => {
  it('clears the previous run and resets the cursor on restart', async () => {
    const { result, rerender } = renderHook(({ session }) => useJournal(config.intersection_id, session, 0), { initialProps: { session: runId } })
    await flush()
    expect(result.current.journal.events).toHaveLength(1)
    rerender({ session: secondRunId })
    await flush()
    expect(result.current.journal.events).toHaveLength(0)
    expect(result.current.state).toBe('unavailable')
    expect(requests.at(-1)).toContain(`run_id=${secondRunId}&after=0`)
  })
})
