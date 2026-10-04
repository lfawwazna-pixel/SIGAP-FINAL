import configuration from '../../configs/intersection.json'
import type { AtcsStatus } from './types/AtcsStatus'
import type { IntersectionConfig } from './types/IntersectionConfig'
import type { TrafficEvent, TrafficEvents } from './types/TrafficEvents'
import type { SessionView } from './types/SessionView'

export const sessionFixture = (): SessionView => ({ operator: {
  id: '21435872-7333-4123-8333-000000000003', username: 'operator.test', display_name: 'Operator Pengujian', role: 'operator', permissions: ['monitor:read'],
}, expires_at: '2026-10-03T20:00:00Z', remaining_seconds: 28800, csrf_token: 'a'.repeat(64) })

export const config = configuration as unknown as IntersectionConfig
export const runId = '21435872-7333-4123-8333-000000000001'
export const secondRunId = '21435872-7333-4123-8333-000000000002'
export const timestamp = '2026-10-03T08:00:02.100Z'
export const statusFixture = (overrides: Partial<AtcsStatus> = {}): AtcsStatus => ({
  schema_version: '2.0', intersection_id: config.intersection_id, operating_context: 'simulation',
  availability: 'available', run_id: runId, engine_state: 'running', controller: 'ATCS', mode: 'fixed_time',
  active_approach: 'U', phase: 'green', signals: { U: 'green', T: 'red', S: 'red', B: 'red' },
  clearance_state: null, conflict_area: { state: 'clear', source: 'assumed_clear', checked_at: timestamp },
  remaining_seconds: 84.9, simulation_time_seconds: 2.1, sequence_number: 22, updated_at: timestamp,
  observed_at: timestamp, reason: 'Fase hijau U sesuai konfigurasi fixed-time.', ...overrides,
})
export const eventFixture = (overrides: Partial<TrafficEvent> = {}): TrafficEvent => ({
  event_id: `${runId}:1`, intersection_id: config.intersection_id, run_id: runId, event_type: 'service_started',
  source: 'atcs', sequence_number: 1, occurred_at: timestamp, simulation_time_seconds: 0,
  reason: 'Sesi dimulai dengan semua merah.', previous_phase: null, previous_approach: null,
  phase: 'all_red', active_approach: null, ...overrides,
})
export const pageFixture = (overrides: Partial<TrafficEvents> = {}): TrafficEvents => ({
  intersection_id: config.intersection_id, run_id: runId, events: [eventFixture()], oldest_available_sequence: 1,
  latest_sequence: 1, next_after: 1, has_more: false, history_truncated: false, run_changed: false, generated_at: timestamp, ...overrides,
})
export const respond = (data: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(data), { status }))
