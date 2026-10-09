import geometry from './geometry/map-geometry.json'
import { directions } from './traffic'
import type { TrafficView } from './types/TrafficView'
import { vehicleDimensions } from './vehicleAppearance'

type Vehicle = TrafficView['vehicles'][number]
const rowGap = 10
const stopClearance = 6
const roadMargin = 20

/** Reflow presence icons only. Never synthesize, discard or change a track's class.
 * Detector order remains stable within each lane; motorcycles share rows of up
 * to three, including when other classes occur between their tracking IDs.
 * These are schematic slots, not inferred camera positions or vehicle motion. */
export function schematicVehicleLayout(vehicles: TrafficView['vehicles']) {
  const lanes = new Map<string, Vehicle[]>()
  for (const vehicle of vehicles) {
    const key = `${vehicle.origin}:${vehicle.lane}`
    const group = lanes.get(key) ?? []
    group.push(vehicle)
    lanes.set(key, group)
  }
  const poses = new Map<number, Vehicle>()
  let requiredStart = geometry.start
  for (const group of lanes.values()) {
    const { origin, lane } = group[0]
    const rotation = directions.indexOf(origin)
    let frontEdge = (lane === 'outer' ? geometry.slip.start[1] : geometry.stop_line) - stopClearance
    const placed = new Set<number>()
    for (let index = 0; index < group.length; index++) {
      const vehicle = group[index]
      if (placed.has(vehicle.id)) continue
      const row = vehicle.kind === 'motorcycle'
        ? group.slice(index).filter(item => item.kind === 'motorcycle' && !placed.has(item.id)).slice(0, 3)
        : [vehicle]
      const length = vehicleDimensions[vehicle.kind].length
      const center = frontEdge - length / 2
      row.forEach((item, column) => {
        // A centered singleton, a centered pair, or three distinct narrow slots.
        let x = geometry.lane_centers[lane] + (column - (row.length - 1) / 2) * 12
        let y = center
        for (let turn = 0; turn < rotation; turn++) [x, y] = [2 * geometry.center - y, x]
        poses.set(item.id, { ...item, x, y, heading: (90 + rotation * 90 + 180) % 360 - 180 })
        placed.add(item.id)
      })
      requiredStart = Math.min(requiredStart, frontEdge - length - roadMargin)
      frontEdge -= length + rowGap
    }
  }
  // Extend in chunks to keep the map bounds steady as detections fluctuate.
  const roadStart = Math.floor(requiredStart / 200) * 200
  return { vehicles: vehicles.map(vehicle => poses.get(vehicle.id)!), roadStart }
}
