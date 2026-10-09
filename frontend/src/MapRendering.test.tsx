import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { IntersectionMap } from './IntersectionMap'
import { interpolatePose } from './VehicleLayer'
import { schematicVehicleLayout } from './schematicVehicleLayout'
import { MapZoom } from './MapZoom'
import { Monitor } from './Monitor'
import { LoginScreen } from './LoginScreen'
import { config, respond, sessionFixture, statusFixture, pageFixture } from './testFixtures'
import type { TrafficView } from './types/TrafficView'

const car: TrafficView['vehicles'][number] = { id: 1, kind: 'car', origin: 'U', movement: 'left',
  x: 500, y: 180, heading: 60, stopped: false, stop_reason: null, distance_to_stop: 120, served: false, lane: 'outer', target_lane: 'outer', changing_to: null }
const props = { selected: 'U' as const, onSelect: () => undefined, signals: null, routes: true }
const flush = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms) }) }
beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(performance, 'now').mockImplementation(() => Date.now())
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => setTimeout(() => callback(performance.now()), 16))
  vi.stubGlobal('cancelAnimationFrame', (identity: number) => clearTimeout(identity))
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('uses a continuous asphalt outline and four separate islands without overlaid road strokes', () => {
  const { container } = render(<IntersectionMap {...props} />)
  expect(container.querySelectorAll('.road')).toHaveLength(1)
  expect(container.querySelectorAll('.slip-road, .slip-edge')).toHaveLength(0)
  expect(container.querySelectorAll('[data-slip-road]')).toHaveLength(4)
  expect(container.querySelectorAll('[data-island]')).toHaveLength(4)
  expect(container.querySelectorAll('[data-incoming-lane]')).toHaveLength(12)
  expect(screen.getByRole('img', { name: 'Rambu Utara lajur kiri: ruas pintas kiri' })).toBeTruthy()
  expect(screen.getByRole('img', { name: 'Rambu Utara lajur tengah: lurus' })).toBeTruthy()
  expect(screen.getByRole('img', { name: 'Rambu Utara lajur kanan: belok kanan' })).toBeTruthy()
})

it('shows the changing lane and turn indicator from the traffic snapshot', () => {
  const { container } = render(<IntersectionMap {...props} vehicles={[{ ...car, lane: 'middle', changing_to: 'outer' }]} />)
  expect(container.querySelector('[data-changing-to="outer"]')).toBeTruthy()
  expect(container.querySelector('.vehicle-indicator')).toBeTruthy()
  expect(container.querySelector('[data-vehicle-id="1"] title')?.textContent).toContain('berpindah ke kiri')
})

it('explores the same road geometry on login without showing live signals or vehicles', () => {
  const main = render(<IntersectionMap {...props} />)
  const outline = main.container.querySelector('.road')?.getAttribute('d')
  const dividers = main.container.querySelector('.lane-divider')?.getAttribute('d')
  main.unmount()
  const login = render(<LoginScreen screen="guest" busy={false} message="" onSubmit={async () => undefined} onRetry={() => undefined} />)
  expect(login.container.querySelector('.road')?.getAttribute('d')).toBe(outline)
  expect(login.container.querySelector('.lane-divider')?.getAttribute('d')).toBe(dividers)
  expect(login.container.querySelectorAll('[data-slip-road]')).toHaveLength(4)
  expect(login.container.querySelectorAll('[data-island]')).toHaveLength(4)
  expect(login.container.querySelectorAll('[data-signal], [data-vehicle-id]')).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: 'B Barat' }))
  expect(login.container.querySelector('.login-selected-route')?.getAttribute('transform')).toBe('rotate(270 400 400)')
  expect(login.container.querySelectorAll('.login-selected-route path')).toHaveLength(3)
  expect(screen.getByRole('img', { name: /Ilustrasi rute dari Barat/ })).toBeTruthy()
})

it('exposes the actual reason for a stopped vehicle in its map tooltip', () => {
  const view = render(<IntersectionMap {...props} vehicles={[{ ...car, stopped: true, stop_reason: 'signal' }]} />)
  expect(view.container.querySelector('[data-vehicle-id] title')?.textContent).toContain('menunggu lampu')
  expect(view.container.querySelector('[data-stop-reason="signal"]')).toBeTruthy()
})

it('keeps vehicle positions in SVG coordinates when viewport size/zoom changes', async () => {
  const show = (width: number, value = car) => <div style={{ width }}><IntersectionMap {...props} vehicles={[value]} vehicleRunId="run-a" /></div>
  const view = render(show(900))
  const position = () => view.container.querySelector('.vehicle-position')!
  expect(position().getAttribute('transform')).toBe('translate(500 180)')
  expect(position().getAttribute('style')).toBeNull()
  view.rerender(show(720))
  act(() => window.dispatchEvent(new Event('resize')))
  expect(position().getAttribute('transform')).toBe('translate(500 180)')
  view.rerender(show(1080, { ...car, x: 510, y: 190 }))
  await flush(120)
  const middle = position().getAttribute('transform')!
  const coordinates = middle.match(/[-\d.]+/g)!.map(Number)
  expect(coordinates[0]).toBeGreaterThan(500)
  expect(coordinates[0]).toBeLessThan(510)
  view.rerender(show(600, { ...car, x: 510, y: 190 }))
  expect(position().getAttribute('transform')).toBe(middle)
  await flush(250)
  expect(position().getAttribute('transform')).toBe('translate(510 190)')
  expect(position().getAttribute('style')).toBeNull()
})

it('does not animate a recycled vehicle ID across a reset or data gap', () => {
  const view = render(<IntersectionMap {...props} vehicles={[car]} vehicleRunId="run-a" />)
  view.rerender(<IntersectionMap {...props} vehicles={[{ ...car, x: 470, y: -100 }]} vehicleRunId="run-b" />)
  expect(view.container.querySelector('.vehicle-position')!.getAttribute('transform')).toBe('translate(470 -100)')
  view.rerender(<IntersectionMap {...props} vehicles={[]} vehicleRunId="run-b" />)
  expect(view.container.querySelector('.vehicle-position')).toBeNull()
})

it('uses the short heading rotation and respects reduced motion', () => {
  expect(interpolatePose({ x: 0, y: 0, heading: 179 }, { x: 10, y: 10, heading: -179 }, .5)).toEqual({ x: 5, y: 5, heading: 180 })
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })))
  const view = render(<IntersectionMap {...props} vehicles={[car]} />)
  view.rerender(<IntersectionMap {...props} vehicles={[{ ...car, x: 520 }]} />)
  expect(view.container.querySelector('.vehicle-position')!.getAttribute('transform')).toBe('translate(520 180)')
})

it('offers consecutive map zoom levels below and above the default', () => {
  const change = vi.fn()
  render(<MapZoom label="Zoom uji" value={1} onChange={change} />)
  const select = screen.getByRole('combobox', { name: 'Zoom uji' }) as HTMLSelectElement
  expect(select.value).toBe('1')
  expect([...select.options].map(option => option.text)).toEqual(Array.from({ length: 16 }, (_, index) => `${50+10*index}%`))
  fireEvent.change(select, { target: { value: '0.5' } })
  expect(change).toHaveBeenCalledWith(.5)
})

it('changes map scale without sending controller commands and starts at 100 percent', async () => {
  vi.stubGlobal('fetch', vi.fn((input: string) => {
    if (input.endsWith('/configuration')) return respond(config)
    if (input.endsWith('/atcs/status')) return respond(statusFixture())
    if (input.includes('/atcs/events?')) return respond(pageFixture())
    return respond({}, 503)
  }))
  render(<Monitor session={sessionFixture()} onLogout={() => undefined} signingOut={false} logoutError={null} />)
  await flush()
  const zoom = screen.getByRole('combobox', { name: 'Zoom peta ATCS' }) as HTMLSelectElement
  expect(zoom.value).toBe('1')
  fireEvent.change(zoom, { target: { value: '0.5' } })
  expect((document.querySelector('.traffic-map-scroll > div') as HTMLElement).style.width).toBe('50%')
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method)).toBe(true)
})

it('extends a crowded CCTV road instead of shrinking or dropping its vehicles', () => {
  const vehicles = Array.from({ length: 180 }, (_, i) => ({ ...car, id: i+1, x: 510,
    y: 81-i*462/179, heading: 90 }))
  const view = render(<IntersectionMap {...props} schematic vehicles={vehicles} />)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(180)
  expect(view.container.querySelectorAll('.vehicle-body rect')).toHaveLength(180)
  const map = view.container.querySelector('.intersection-map') as SVGSVGElement
  const layout = schematicVehicleLayout(vehicles)
  const span = 800 - 2 * layout.roadStart + 220
  expect(map.getAttribute('viewBox')).toBe(`${layout.roadStart-110} ${layout.roadStart-110} ${span} ${span}`)
  expect(parseFloat(map.style.width) / span).toBeCloseTo(100 / 1820)
  expect(view.container.querySelector('.road')?.getAttribute('d')).toContain(`M270 ${layout.roadStart}`)
  for (const body of view.container.querySelectorAll('.vehicle-body')) expect(body.getAttribute('transform')).toBeNull()
  expect(screen.getByLabelText('180 kendaraan pada peta')).toBeTruthy()
  expect(view.container.querySelector('.map-count')?.textContent).toBe('180 terlacak')
  const drawn = layout.vehicles
  for (let i = 1; i < drawn.length; i++) expect(drawn[i-1].y-drawn[i].y).toBeGreaterThan(28)
})

it('updates CCTV slots together without animating across a lane or a new arrival', async () => {
  const view = render(<IntersectionMap {...props} schematic vehicles={[{ ...car, x: 470, y: 238, lane: 'middle' }]} />)
  view.rerender(<IntersectionMap {...props} schematic vehicles={[
    { ...car, x: 430, y: 202, lane: 'inner' }, { ...car, id: 2, x: 430, y: 238, lane: 'inner' },
  ]} />)
  expect(view.container.querySelector('[data-vehicle-id="1"]')?.parentElement?.getAttribute('transform')).toBe('translate(430 238)')
  expect(view.container.querySelector('[data-vehicle-id="2"]')?.parentElement?.getAttribute('transform')).toBe('translate(430 202)')
  await flush(120)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(view.container.querySelector('[data-vehicle-id="1"]')?.parentElement?.getAttribute('transform')).toBe('translate(430 238)')
})

it('keeps emergency markers readable and lights above vehicles in the video map', () => {
  const view = render(<IntersectionMap {...props} schematic vehicles={[{ ...car, id: 273827058732600, kind: 'ambulance', served: true }]} />)
  expect(view.container.querySelector('.ambulance-cross')).toBeTruthy()
  expect(view.container.querySelector('.evp-number')).toBeNull()
  expect(view.container.querySelector('.map-vehicle title')?.textContent).toContain('sudah melewati garis henti di video')
  expect(view.container.querySelector('.map-vehicle title')?.textContent).not.toContain('273827058732600')
  const layer = view.container.querySelector('.vehicle-layer')!
  const light = view.container.querySelector('[data-signal]')!
  expect(layer.compareDocumentPosition(light) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

it('renders six detector classes as distinct glyphs with one stable map identity each', () => {
  const kinds: TrafficView['vehicles'][number]['kind'][] = ['motorcycle','car','bus','truck','ambulance','fire_engine']
  const vehicles = kinds.map((kind,i) => ({...car, id:i+1, kind, x:470, y:200-i*36, heading:90}))
  const view = render(<IntersectionMap {...props} schematic vehicles={vehicles} />)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(6)
  for (const [i,kind] of kinds.entries()) {
    const glyph = view.container.querySelector(`[data-vehicle-id="${i+1}"]`)!
    expect(glyph.querySelector(`.vehicle-glyph--${kind}`)).toBeTruthy()
  }
  expect(view.container.querySelector('.motorcycle-rider')).toBeTruthy()
  expect(view.container.querySelector('.bus-windows')).toBeTruthy()
  expect(view.container.querySelector('.truck-cargo')).toBeTruthy()
  expect(view.container.querySelector('.ambulance-cross')).toBeTruthy()
  expect(view.container.querySelector('.fire-ladder')).toBeTruthy()
  expect(view.container.querySelector('.map-vehicle--motorcycle title')?.textContent).toContain('Motor terlacak')
  expect(view.container.querySelector('.evp-number')).toBeNull()
  const first = view.container.querySelector('[data-vehicle-id="1"]')
  view.rerender(<IntersectionMap {...props} schematic vehicles={vehicles.map(v => v.id===1 ? {...v,kind:'truck'} : v)} />)
  expect(view.container.querySelector('[data-vehicle-id="1"]')).toBe(first)
  expect(first?.classList.contains('map-vehicle--truck')).toBe(true)
})

it('renders full length buses and trucks alongside the smaller motorcycle bodies', () => {
  const kinds: TrafficView['vehicles'][number]['kind'][] = ['car','bus','truck','motorcycle']
  const vehicles = kinds.map((kind,i) => ({...car,id:i+1,kind}))
  const { container } = render(<IntersectionMap {...props} schematic vehicles={vehicles} />)
  expect(container.querySelector('.vehicle-glyph--car rect')?.getAttribute('width')).toBe('26')
  expect(container.querySelector('.vehicle-glyph--bus rect')?.getAttribute('width')).toBe('52')
  expect(Number(container.querySelector('.truck-cargo')?.getAttribute('width')) + Number(container.querySelector('.truck-cab')?.getAttribute('width'))).toBe(52)
  expect(container.querySelector('.vehicle-glyph--motorcycle rect')?.getAttribute('width')).toBe('14')
})

it('holds road extent during a run and preserves the current view when it expands', () => {
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function(this: Element) {
    const span = Number(this.getAttribute('viewBox')?.split(' ')[2] ?? 1820)
    return { width: span / 1820 * 900 } as DOMRect
  })
  const show = (vehicles: TrafficView['vehicles'], run = 'a', schematic = true) => <div className="map-canvas"><IntersectionMap {...props} schematic={schematic} vehicleRunId={run} vehicles={vehicles} /></div>
  const view = render(show([car]))
  const canvas = view.container.querySelector('.map-canvas') as HTMLElement
  const original = view.container.querySelector('svg')!.getAttribute('viewBox')
  const centerBefore = 910 * 900 / 1820
  const crowded = Array.from({length:100},(_,i) => ({...car,id:i+1}))
  view.rerender(show(crowded))
  const expanded = view.container.querySelector('svg')!.getAttribute('viewBox')!
  const start = Number(expanded.split(' ')[0])
  expect(expanded).not.toBe(original)
  expect((400-start) * 900 / 1820 - canvas.scrollLeft).toBeCloseTo(centerBefore)
  expect(canvas.scrollTop).toBe(canvas.scrollLeft)
  view.rerender(show([car]))
  expect(view.container.querySelector('svg')!.getAttribute('viewBox')).toBe(expanded)
  view.rerender(show([car], 'b'))
  expect(view.container.querySelector('svg')!.getAttribute('viewBox')).toBe(original)
  expect(canvas.scrollLeft).toBeCloseTo(0)
  view.rerender(show(crowded, 'b', false))
  expect(view.container.querySelector('svg')!.getAttribute('viewBox')).toBe(original)
})
