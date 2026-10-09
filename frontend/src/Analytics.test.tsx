import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import fixture from './testData/analytics.json'
import type { AnalyticsView } from './types/AnalyticsView'
import { AnalyticsPage, impactChange, validReport } from './AnalyticsPage'
import { AnalyticsChart } from './AnalyticsChart'
import { App } from './App'
import { directions } from './traffic'
import { respond, sessionFixture } from './testFixtures'

const data = () => structuredClone(fixture) as unknown as AnalyticsView
const session = () => { const s = sessionFixture(); s.operator.permissions.push('control:operate'); return s }
const page = () => <AnalyticsPage session={session()} onLogout={() => undefined} signingOut={false} logoutError={null} />
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState(null, '', '/') })

it('uses the repeated mean in cards and the first seed only in the graph', async () => {
  const view = data(), report = view.latest_comparison!
  vi.stubGlobal('fetch', vi.fn(() => respond(view))); render(page())
  await screen.findByRole('img', { name: /Perbandingan Waktu tunggu/ })
  const card = screen.getByRole('heading', { name: 'Tunggu rata-rata' }).parentElement!
  const mean = report.metrics.find(m => m.key === 'average_wait_seconds')!.sigap_mean
  expect(card.querySelector('strong')!.textContent).toContain(new Intl.NumberFormat('id-ID', { maximumFractionDigits: 1 }).format(mean))
  expect(screen.getByText(/contoh pasangan pertama, bukan rata-rata ulangan/)).toBeTruthy()
  expect(within(screen.getByRole('table', { name: 'Hasil per pendekat' })).getAllByRole('row').length).toBe(5)
})

it('freezes zone fingerprint and sends observed class demand without lamp commands', async () => {
  const view = data(); view.latest_comparison = null
  view.zone_demand = { ready: true, generated_at: view.generated_at, message: 'Profil siap', fingerprint: 'zone-profile-123',
    approaches: directions.map(direction => ({ direction, state: 'ready', message: 'Siap', source: 'recording', observed_seconds: 60, entries: 3, demand_per_minute: 3,
      by_class: { motorcycle: 2, car: 1, bus: 0, truck: 0 }, by_movement: { left: 1, straight: 2, right: 0 }, queue_visibility: 'partial', loop_count: 1 })) }
  const fetcher = vi.fn((_url: string, options?: RequestInit) => respond(options?.method === 'POST' ? fixture.latest_comparison : view))
  vi.stubGlobal('fetch', fetcher); render(page()); await screen.findByText('Profil siap')
  fireEvent.click(screen.getByRole('button', { name: 'Gunakan pengamatan zona' }))
  expect((screen.getByLabelText('Arus Utara (kend/menit)') as HTMLInputElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: /Jalankan perbandingan setara/ }))
  await screen.findByText('Perbandingan selesai dan tersimpan. Lihat hasil di bawah.')
  const input = JSON.parse(String(fetcher.mock.calls.find(c => c[1]?.method === 'POST')![1]!.body))
  expect(input.observation_fingerprint).toBe('zone-profile-123')
  expect(input.demand_source).toBe('zone_observation')
  expect(input.class_mix).toEqual({ motorcycle: 8, car: 4, bus: 0, truck: 0 })
  expect(input.demand_per_minute).toEqual({ U: 3, T: 3, S: 3, B: 3 })
})

it('marks an interval spanning zero as inconclusive and withholds observation without a ready profile', async () => {
  const view = data(), metric = view.latest_comparison!.metrics.find(m => m.key === 'average_wait_seconds')!
  metric.lower_95 = -500; metric.upper_95 = 500; metric.result = 'inconclusive'
  vi.stubGlobal('fetch', vi.fn(() => respond(view))); render(page())
  await screen.findByRole('img', { name: /Perbandingan Waktu tunggu/ })
  expect(within(screen.getByRole('heading', { name: 'Tunggu rata-rata' }).parentElement!).getByText(/Belum konsisten antarulangan/)).toBeTruthy()
  expect((screen.getByRole('button', { name: 'Gunakan pengamatan zona' }) as HTMLButtonElement).disabled).toBe(true)
})

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
  const view = data(), m = view.latest_comparison!.metrics.find(m => m.key === 'average_wait_seconds')!
  m.sigap_mean = m.atcs_mean * 2
  m.improvement_mean = -m.atcs_mean; m.improvement_percent = -100
  m.lower_95 = -m.atcs_mean - 1; m.upper_95 = -m.atcs_mean + 1; m.result = 'worse'
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
  fireEvent.change(screen.getByLabelText('Arus Utara (kend/menit)'), { target: { value: '181' } })
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
