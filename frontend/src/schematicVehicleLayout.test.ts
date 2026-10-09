import { expect, it } from 'vitest'
import { schematicVehicleLayout } from './schematicVehicleLayout'
import { vehicleDimensions } from './vehicleAppearance'
import geometry from './geometry/map-geometry.json'
import { directions } from './traffic'
import type { TrafficView } from './types/TrafficView'

type Vehicle = TrafficView['vehicles'][number]
const vehicle = (id: number, kind: Vehicle['kind'] = 'motorcycle', lane: Vehicle['lane'] = 'middle', origin: Vehicle['origin'] = 'U'): Vehicle => ({
  id, kind, lane, origin, x: 470, y: 238-id*36, heading: 90, movement: 'straight', stopped: true,
  stop_reason: 'stationary', distance_to_stop: id*10, served: false, target_lane: lane, changing_to: null,
})
const northPose = (v: Vehicle) => {
  let { x, y } = v
  for (let turn = 0; turn < directions.indexOf(v.origin); turn++) [x, y] = [y, 800-x]
  return { x, y }
}

it.each([
  [0, []], [1, [1]], [2, [2]], [3, [3]], [4, [3,1]], [5, [3,2]], [7, [3,3,1]], [10, [3,3,3,1]],
])('shows exactly %i detected motorcycles, centered in rows of at most three', (count, expectedRows) => {
  const input = Array.from({length:count},(_,i) => vehicle(i+1))
  const original = structuredClone(input)
  const { vehicles } = schematicVehicleLayout(input)
  expect(input).toEqual(original)
  expect(vehicles.map(v => v.id)).toEqual(input.map(v => v.id))
  const rows = new Map<number, Vehicle[]>()
  for (const v of vehicles) rows.set(v.y, [...(rows.get(v.y) ?? []), v])
  expect([...rows.values()].map(row => row.length)).toEqual(expectedRows)
  for (const row of rows.values()) {
    expect(new Set(row.map(v => v.x)).size).toBe(row.length)
    expect(row.reduce((sum,v) => sum+v.x,0) / row.length).toBe(470)
  }
})

it('packs motorcycles across intervening track classes without duplicating or relabeling any vehicle', () => {
  const input = [vehicle(1),vehicle(2,'car'),vehicle(3),vehicle(4,'bus'),vehicle(5),vehicle(6),vehicle(7,'truck'),vehicle(8)]
  const result = schematicVehicleLayout(input).vehicles
  expect(result.map(v => [v.id,v.kind,v.lane,v.origin,v.stopped,v.served,v.distance_to_stop])).toEqual(input.map(v => [v.id,v.kind,v.lane,v.origin,v.stopped,v.served,v.distance_to_stop]))
  const motorRows = new Map<number, number>()
  for (const v of result.filter(v => v.kind === 'motorcycle')) motorRows.set(v.y, (motorRows.get(v.y) ?? 0)+1)
  expect([...motorRows.values()]).toEqual([3,2])
})

it('fits every class in all twelve lanes without overlap, spillover, or crossing the stop line', () => {
  const kinds: Vehicle['kind'][] = ['motorcycle','car','motorcycle','bus','truck','motorcycle','ambulance','fire_engine']
  const input: Vehicle[] = []
  for (const origin of directions) for (const lane of ['outer','middle','inner'] as const) {
    for (let i=0;i<40;i++) input.push(vehicle(input.length+1,kinds[i%kinds.length],lane,origin))
  }
  const { vehicles, roadStart } = schematicVehicleLayout(input)
  expect(new Set(vehicles.map(v => v.id)).size).toBe(input.length)
  expect(vehicles).toHaveLength(input.length)
  expect(roadStart).toBeLessThan(geometry.start)
  for (const origin of directions) for (const lane of ['outer','middle','inner'] as const) {
    const group = vehicles.filter(v => v.origin===origin && v.lane===lane)
    for (const v of group) {
      const { x,y } = northPose(v)
      const size = vehicleDimensions[v.kind]
      expect(Math.abs(x-geometry.lane_centers[lane])+size.width/2+1).toBeLessThan(20)
      expect(y-size.length/2-1).toBeGreaterThan(roadStart)
      expect(y+size.length/2+1).toBeLessThan(lane==='outer' ? geometry.slip.start[1] : geometry.stop_line)
      expect(v.heading).toBe((90+directions.indexOf(origin)*90+180)%360-180)
    }
    for (let i=0;i<group.length;i++) for (let j=i+1;j<group.length;j++) {
      const a=northPose(group[i]), b=northPose(group[j])
      const sa=vehicleDimensions[group[i].kind], sb=vehicleDimensions[group[j].kind]
      // Include body outlines, not just distinct centers.
      expect(Math.abs(a.x-b.x)>(sa.width+sb.width)/2+1 || Math.abs(a.y-b.y)>(sa.length+sb.length)/2+1).toBe(true)
    }
  }
})

it('resizes a changed class and reflows arrivals without changing the source measurements', () => {
  const initial = [vehicle(1,'car'),vehicle(2,'truck'),vehicle(3)]
  const before = schematicVehicleLayout(initial).vehicles
  const next = [vehicle(1,'bus'),vehicle(2,'truck'),vehicle(3),vehicle(4),vehicle(5)]
  const after = schematicVehicleLayout(next).vehicles
  expect(after.map(v => v.id)).toEqual([1,2,3,4,5])
  expect(after[1].y).toBeLessThan(before[1].y)
  expect(new Set(after.slice(2).map(v => v.y)).size).toBe(1)
  expect(initial[0].kind).toBe('car')
  expect(next[0].distance_to_stop).toBe(10)
  expect(schematicVehicleLayout([])).toEqual({ vehicles: [], roadStart: geometry.start })
})
