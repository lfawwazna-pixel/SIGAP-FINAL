import type { AdaptiveStatus } from './types/AdaptiveStatus'

export function freshVideoObservation(observedAt: string, now = Date.now()) {
  const age = (now-Date.parse(observedAt))/1000
  return Number.isFinite(age) && age >= -.5 && age <= 3
}

/** Display every fresh tracked object, even when its lane is not calibrated.
 * Calibration determines control demand; it must not hide detected vehicles. */
export function videoMapVehicles(data: AdaptiveStatus | null, intersection: string | undefined, now = Date.now()) {
  if (!data?.enabled || data.source === 'synthetic' || !data.measurements
      || data.measurements.intersection_id !== intersection) return []
  return data.map_vehicles.filter(vehicle => {
    const observation = data.measurements!.approaches[vehicle.origin]
    return observation && freshVideoObservation(observation.observed_at, now)
  })
}
