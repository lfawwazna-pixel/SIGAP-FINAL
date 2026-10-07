import { expect, it } from 'vitest'
import { freshVideoObservation, videoMapVehicles } from './videoMap'
import type { AdaptiveStatus } from './types/AdaptiveStatus'

it('keeps fresh per-camera tracking when uncalibrated, ready or unavailable, and removes only stale cameras', () => {
  const now = Date.now()
  const pose = { id: 1, origin: 'U' as const, movement: 'straight' as const, kind: 'car' as const,
    x: 470, y: 0, heading: 90, stopped: false, served: false, distance_to_stop: 240,
    lane: 'middle' as const, target_lane: 'middle' as const, changing_to: null, stop_reason: null }
  const data = { enabled: true, source: 'recording', status: 'unavailable', map_vehicles: [pose, {...pose, id:2, origin:'T'}],
    measurements: { intersection_id: 'test', approaches: {
      U: {observed_at: new Date(now).toISOString(), usable:false},
      T: {observed_at: new Date(now-4000).toISOString(), usable:true},
    } } } as unknown as AdaptiveStatus
  expect(videoMapVehicles(data, 'test', now)).toEqual([pose])
  expect(videoMapVehicles({...data, status:'ready'}, 'test', now)).toEqual([pose])
  expect(videoMapVehicles(data, 'another-intersection', now)).toEqual([])
  expect(videoMapVehicles({...data, source:'synthetic'}, 'test', now)).toEqual([])
  expect(videoMapVehicles({...data, measurements:null}, 'test', now)).toEqual([])
  expect(videoMapVehicles({...data, enabled:false}, 'test', now)).toEqual([])
  expect(videoMapVehicles(data, 'test', now+3100)).toEqual([])
  expect(freshVideoObservation('invalid-time', now)).toBe(false)
  expect(freshVideoObservation(new Date(now+1000).toISOString(), now)).toBe(false)
})
