import { act, cleanup, fireEvent, render, renderHook, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Monitor } from './Monitor'
import { coherentTraffic, useTraffic } from './useTraffic'
import { config, sessionFixture, statusFixture, respond, runId, secondRunId, pageFixture } from './testFixtures'
import type { TrafficView } from './types/TrafficView'

function fixture(source: TrafficView['source'] = 'experiment'): TrafficView {
  return { decision: null, intersection_id: config.intersection_id, source, run_id: source === 'experiment' ? secondRunId : runId,
    observed_at: '2026-10-03T08:01:00Z', available: true, time_seconds: 0, running: source !== 'experiment', speed: 1,
    strategy: source === 'experiment' ? 'adaptive' : 'fixed_time', phase: 'all_red', active_approach: null,
    signals: { U: 'red', T: 'red', S: 'red', B: 'red' }, remaining_seconds: 2, emergency: false, target_vehicle: null,
    reason: 'Siap', demand: { U: 10, T: 10, S: 10, B: 10 }, blocked_exit: null, events: [], evp_queue: [],
    vehicles: [], queues: { U: 0, T: 0, S: 0, B: 0 }, completed: 0, average_wait: 0, waiting_seconds: 0,
    refused_spawns: 0, conflict: 'clear', traffic_sequence: 0 }
}
const flush = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms) }) }
let simulation: TrafficView
let postBodies: Record<string, unknown>[]
let simulationFailure = false
let atcsSequence = 0
let statusSequence = 30
let postedHeaders: HeadersInit | undefined

beforeEach(() => {
  vi.useFakeTimers()
  simulation = fixture()
  postBodies = []
  simulationFailure = false
  atcsSequence = 0
  statusSequence = 30
  vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
    if (input.endsWith('/configuration')) return respond(config)
    if (input.endsWith('/atcs/status')) return respond(statusFixture({ sequence_number: statusSequence++ }))
    if (input.includes('/atcs/events?')) return respond(pageFixture())
    if (input.endsWith('/atcs/traffic')) return respond({ ...fixture('atcs_synthetic'), traffic_sequence: ++atcsSequence })
    if (input.endsWith('/simulation')) return simulationFailure ? respond({}, 503) : respond(simulation)
    if (input.endsWith('/simulation/commands')) {
      const body = JSON.parse(init!.body as string)
      postBodies.push(body)
      postedHeaders = init?.headers
      if (body.action === 'spawn') simulation = { ...simulation, vehicles: [{ id: 1, kind: body.kind, origin: body.direction, x: 1200, y: 470, heading: 180, movement: 'straight', stopped: false, served: false, distance_to_stop: 657, lane: 'middle', target_lane: 'middle', changing_to: null, stop_reason: null }] }
      if (body.action === 'start' || body.action === 'pause') simulation = { ...simulation, running: body.action === 'start' }
      if (body.action === 'configure') simulation = { ...simulation, ...(body.speed ? { speed: body.speed } : {}) }
      if (body.action === 'reset') simulation = { ...fixture(), run_id: runId }
      return respond(simulation)
    }
    return respond({}, 503)
  }))
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

const App = () => <Monitor session={sessionFixture()} onLogout={() => undefined} signingOut={false} logoutError={null} />
const selectSimulation = () => fireEvent.click(within(screen.getByRole('group', { name: 'Mode ruang kerja' })).getByRole('button', { name: /Simulasi Percobaan/ }))

describe('isolated simulator UI', () => {
  it('keeps ATCS polling while experimenting and does not reset it on return', async () => {
    render(<App />)
    await flush()
    expect(screen.queryByRole('button', { name: 'Mulai' })).toBeNull()
    selectSimulation()
    await flush()
    fireEvent.click(screen.getByRole('button', { name: 'Mulai' }))
    await flush()
    expect(screen.getByRole('button', { name: 'Jeda' })).toBeTruthy()
    const previous = statusSequence
    const previousTraffic = atcsSequence
    await flush(550)
    expect(statusSequence).toBeGreaterThan(previous)
    expect(atcsSequence).toBe(previousTraffic)
    fireEvent.click(within(screen.getByRole('group', { name: 'Mode ruang kerja' })).getByRole('button', { name: /ATCS Fase bersama/ }))
    await flush()
    expect(atcsSequence).toBeGreaterThan(previousTraffic)
    expect(screen.queryByRole('button', { name: 'Jeda' })).toBeNull()
    expect(postBodies.map(x => x.action)).toEqual(['start'])
  })
  it('adds an ambulance from the rear of a selected approach with session CSRF', async () => {
    render(<App />)
    await flush()
    selectSimulation()
    await flush()
    fireEvent.change(screen.getByLabelText('Dari arah'), { target: { value: 'T' } })
    expect(screen.queryByLabelText('Jarak awal')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Spawn ambulans/ }))
    await flush()
    expect(postBodies[0]).toEqual({ action: 'spawn', direction: 'T', kind: 'ambulance', expected_run_id: secondRunId })
    expect(new Headers(postedHeaders).get('X-CSRF-Token')).toBe(sessionFixture().csrf_token)
    expect(document.querySelectorAll('[data-vehicle-id="1"]').length).toBe(1)
  })
  it('confirms resets and sends speed only to the experiment endpoint', async () => {
    render(<App />)
    await flush()
    selectSimulation()
    await flush()
    fireEvent.change(screen.getByLabelText('Kecepatan simulasi'), { target: { value: '3' } })
    await flush()
    expect(postBodies[0].speed).toBe(3)
    fireEvent.click(screen.getByRole('button', { name: 'Reset percobaan' }))
    expect(postBodies).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Ya, reset percobaan' }))
    await flush()
    expect(postBodies[1].action).toBe('reset')
    expect(screen.getByRole('button', { name: 'Mulai' })).toBeTruthy()
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST').every(([url]) => String(url).endsWith('/simulation/commands'))).toBe(true)
  })
  it('shows SIGAP as unavailable without any operational activation request', async () => {
    render(<App />)
    await flush()
    fireEvent.click(within(screen.getByRole('group', { name: 'Mode ruang kerja' })).getByRole('button', { name: /SIGAP Adaptif/ }))
    expect((screen.getByRole('button', { name: 'Aktifkan kendali SIGAP' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('heading', { name: 'Pengaturan kendali' })).toBeTruthy()
    expect(postBodies).toHaveLength(0)
  })
  it('clears vehicles on disconnect and accepts paused snapshots without expiring the experiment clock', async () => {
    const { result } = renderHook(() => useTraffic('experiment', config.intersection_id, true, sessionFixture().csrf_token))
    await flush(3000)
    expect(result.current.data?.time_seconds).toBe(0)
    simulationFailure = true
    await flush(300)
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBeTruthy()
  })
  it('hides vehicle positions on tab hiding and reads a fresh snapshot on return', async () => {
    const { result } = renderHook(() => useTraffic('experiment', config.intersection_id, true, sessionFixture().csrf_token))
    await flush()
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    act(() => document.dispatchEvent(new Event('visibilitychange')))
    expect(result.current.data).toBeNull()
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
    act(() => document.dispatchEvent(new Event('visibilitychange')))
    await flush()
    expect(result.current.data?.run_id).toBe(secondRunId)
  })
  it('rejects mixed sources, wrong intersections and conflicting signal sets', () => {
    expect(coherentTraffic(fixture(), 'atcs_synthetic', config.intersection_id)).toBe(false)
    expect(coherentTraffic(fixture(), 'experiment', 'wrong')).toBe(false)
    expect(coherentTraffic({ ...fixture(), signals: { U: 'green', T: 'green', S: 'red', B: 'red' } }, 'experiment', config.intersection_id)).toBe(false)
  })
})

it('renders all four ordinary classes with physical body proportions and keeps emergency spawn manual', async () => {
  const kinds = ['motorcycle','car','bus','truck'] as const
  simulation.vehicles = kinds.map((kind,index)=>({id:index+10,kind,origin:'U',movement:'straight',x:470,y:-350+index*70,heading:90,
    stopped:false,served:false,distance_to_stop:607-index*70,lane:'middle',target_lane:'middle',changing_to:null,stop_reason:null}))
  render(<App />)
  await flush()
  selectSimulation()
  await flush()
  const sandbox = screen.getByRole('region',{name:'Ruang simulasi terpisah'})
  for (const kind of kinds) expect(sandbox.querySelector(`.map-vehicle--${kind}`)).toBeTruthy()
  expect(sandbox.querySelector('.map-vehicle--ambulance')).toBeNull()
  expect(sandbox.querySelector('.map-vehicle--fire_engine')).toBeNull()
  expect(within(sandbox).getByText(/Motor, mobil, bus, dan truk muncul otomatis secara acak/)).toBeTruthy()
  expect(within(sandbox).getByText(/Hingga tiga motor dapat berbagi lebar satu lajur/)).toBeTruthy()
  expect(within(sandbox).getByText('Kendaraan simulasi')).toBeTruthy()
  expect(within(sandbox).queryByText('Kelas dari YOLO')).toBeNull()
  expect(within(sandbox).getByRole('button',{name:/Spawn ambulans/})).toBeTruthy()
  expect(within(sandbox).getByRole('button',{name:'Spawn pemadam'})).toBeTruthy()
  expect(postBodies).toHaveLength(0)
  fireEvent.click(within(sandbox).getByRole('button',{name:'Mulai'}))
  await flush()
  expect(postBodies.map(body=>body.action)).toEqual(['start'])
  expect(sandbox.querySelectorAll('.map-vehicle')).toHaveLength(4)
})