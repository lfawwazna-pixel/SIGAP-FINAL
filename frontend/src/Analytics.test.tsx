import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import fixture from './testData/analytics.json'
import type { AnalyticsView } from './types/AnalyticsView'
import { AnalyticsPage, impactChange, validReport } from './AnalyticsPage'
import { AnalyticsChart } from './AnalyticsChart'
import { App } from './App'
import { respond, sessionFixture } from './testFixtures'

const data = () => structuredClone(fixture) as unknown as AnalyticsView
const session = () => { const s = sessionFixture(); s.operator.permissions.push('control:operate'); return s }
const page = () => <AnalyticsPage session={session()} onLogout={() => undefined} signingOut={false} logoutError={null} />
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState(null, '', '/') })

it('keeps real data unconfigured and forecasts empty rather than inventing traffic', async () => {
  const view = data(); view.latest_comparison = null
  vi.stubGlobal('fetch', vi.fn(() => respond(view)))
  render(page())
  await screen.findByText('API key TomTom belum dikonfigurasi pada backend.')
  expect(screen.queryByRole('img', { name: /Perbandingan/ })).toBeNull()
  expect(screen.queryByText('Prediksi lokal · 30 menit')).toBeNull()
  expect(screen.getByText(/Belum diuji. Waktu respons ambulans/)).toBeTruthy()
})

it('renders two aligned lines, changes metrics, exposes CSV and assumptions', async () => {
  const view = data(); vi.stubGlobal('fetch', vi.fn(() => respond(view)))
  render(page())
  const graph = await screen.findByRole('img', { name: /Perbandingan Waktu tunggu/ })
  expect(graph.querySelectorAll('path').length).toBe(2)
  expect(screen.getByText(/Grafik ini bukan hasil eksperimen jalan nyata/)).toBeTruthy()
  expect(screen.getByRole('link', { name: /Unduh hasil CSV/ }).getAttribute('href')).toBe(`/api/analytics/comparison/${view.latest_comparison!.id}/csv`)
  fireEvent.click(screen.getByRole('button', { name: 'Emisi CO₂' }))
  expect(screen.getByRole('img', { name: /Perbandingan Emisi CO₂/ })).toBeTruthy()
  expect(screen.getByText(/Hash kedatangan/)).toBeTruthy()
})

it('submits edited demand with existing authentication and CSRF, without controller commands', async () => {
  const view = data(); view.latest_comparison = null
  const fetcher = vi.fn((_url: string, options?: RequestInit) => respond(options?.method === 'POST' ? fixture.latest_comparison : view))
  vi.stubGlobal('fetch', fetcher); render(page())
  await screen.findByText('API key TomTom belum dikonfigurasi pada backend.')
  fireEvent.change(screen.getByLabelText('Arus Utara (kend/menit)'), { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: /Jalankan perbandingan setara/ }))
  await screen.findByText('Perbandingan selesai dan tersimpan. Lihat hasil di bawah.')
  const call = fetcher.mock.calls.find(c => c[1]?.method === 'POST')!
  expect(call[0]).toBe('/api/analytics/comparison')
  expect(call[1]?.headers).toMatchObject({ 'X-CSRF-Token': 'a'.repeat(64), 'X-SIGAP-Request': '1' })
  expect(call[1]?.credentials).toBe('same-origin')
  expect(JSON.parse(String(call[1]?.body)).demand_per_minute.U).toBe(30)
  expect(fetcher.mock.calls.every(c => ['/api/analytics', '/api/analytics/comparison'].includes(c[0]))).toBe(true)
})

it('does not hide regressions or compute a percentage against zero', async () => {
  expect(impactChange(100, 120)).toBe(-20)
  expect(impactChange(100, 120, true)).toBe(20)
  expect(impactChange(0, 20)).toBeNull()
  const view = data(), a = view.latest_comparison!.atcs.at(-1)!, b = view.latest_comparison!.sigap.at(-1)!
  b.average_wait_seconds = a.average_wait_seconds * 2
  vi.stubGlobal('fetch', vi.fn(() => respond(view))); render(page())
  const badge = await screen.findByText('100% lebih tinggi dari ATCS')
  expect(badge.className).toBe('delta-bad')
})

it('rejects malformed or misaligned pairs before drawing a comparison', async () => {
  const view = data(); view.latest_comparison!.sigap[1].arrivals += 1
  expect(validReport(view.latest_comparison)).toBe(false)
  vi.stubGlobal('fetch', vi.fn(() => respond(view))); render(page())
  await screen.findByRole('alert')
  expect(screen.queryByRole('img', { name: /Perbandingan/ })).toBeNull()
})

it('rejects invalid scenario bounds before a request is sent', async () => {
  const view = data(); view.latest_comparison = null
  const fetcher = vi.fn(() => respond(view)); vi.stubGlobal('fetch', fetcher)
  render(page()); await screen.findByText('API key TomTom belum dikonfigurasi pada backend.')
  fireEvent.change(screen.getByLabelText('Arus Utara (kend/menit)'), { target: { value: '61' } })
  fireEvent.click(screen.getByRole('button', { name: /Jalankan perbandingan setara/ }))
  expect(screen.getByText(/Periksa batas angka pada skenario/)).toBeTruthy()
  expect(fetcher.mock.calls.length).toBe(1)
})

it('renders observed traffic and holds forecasts until enough samples are available', async () => {
  const view = data(); view.provider_status = 'partial'
  const road = view.roads.find(r => r.direction === 'T')!
  road.state = 'ready'; road.latest = { observed_at: view.generated_at, direction: 'T', current_speed_kmh: 20, free_flow_speed_kmh: 40, current_travel_seconds: 90, free_flow_travel_seconds: 45, confidence: .9, road_closed: false, congestion_percent: 50, delay_seconds: 45, segment_latitude: road.point.latitude, segment_longitude: road.point.longitude, point_distance_m: 10 }
  road.history = [road.latest]; road.forecast.training_samples = 1
  vi.stubGlobal('fetch', vi.fn(() => respond(view))); render(page())
  const graph = await screen.findByRole('img', { name: 'Indeks kemacetan Timur' })
  expect(graph.querySelectorAll('path').length).toBe(1)
  expect(screen.queryByText('Prediksi lokal · 30 menit')).toBeNull()
  expect(screen.getByText(/bukan jumlah kendaraan atau kepadatan/)).toBeTruthy()
  expect(screen.getByText('50%')).toBeTruthy()
})

it('keeps graph gaps, offers keyboard inspection and a data table', () => {
  render(<AnalyticsChart title="Antrean uji" unit="kend" xLabel={String} series={[{ label: 'Observed', color: '#123456', points: [{ x: 1, y: 1 }, { x: 2, y: null }, { x: 3, y: 3 }] }]} />)
  const graph = screen.getByRole('img'), path = graph.querySelector('path')!
  expect(path.getAttribute('d')?.match(/M/g)?.length).toBe(2)
  fireEvent.change(screen.getByRole('slider'), { target: { value: '0' } })
  expect(screen.getByRole('slider').getAttribute('aria-valuetext')).toBe('1')
  expect(within(screen.getByRole('table', { hidden: true })).getAllByRole('row', { hidden: true }).length).toBe(4)
})

it('allows authenticated analytics navigation and denies anonymous users', async () => {
  window.history.replaceState(null, '', '/analytics')
  vi.stubGlobal('fetch', vi.fn((url: string) => respond(url.endsWith('/auth/session') ? session() : data())))
  render(<App />)
  await screen.findByRole('heading', { name: /Lihat arusnya/ })
  expect(window.location.pathname).toBe('/analytics')
  cleanup()
  const fetcher = vi.fn(() => respond({}, 401)); vi.stubGlobal('fetch', fetcher)
  render(<App />)
  await screen.findByRole('form', { name: 'Masuk operator' })
  expect(window.location.pathname).toBe('/login')
  expect(fetcher.mock.calls.length).toBe(1)
})
