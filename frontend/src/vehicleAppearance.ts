import type { TrafficView } from './types/TrafficView'
import dimensions from './geometry/vehicle-dimensions.json'

export type VehicleKind = TrafficView['vehicles'][number]['kind']
export const vehicleKindNames: Record<VehicleKind, string> = {
  motorcycle: 'Motor', car: 'Mobil', bus: 'Bus', truck: 'Truk', ambulance: 'Ambulans', fire_engine: 'Pemadam',
}

/** Schematic body dimensions, in SVG units, with the front facing +x. */
export const vehicleDimensions: Record<VehicleKind, { length: number; width: number }> = dimensions
