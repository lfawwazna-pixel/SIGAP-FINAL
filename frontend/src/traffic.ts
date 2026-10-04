import type { AtcsStatus } from './types/AtcsStatus'
import type { IntersectionConfig } from './types/IntersectionConfig'
import type { TrafficEvent, TrafficEvents } from './types/TrafficEvents'

export const directions = ['U', 'T', 'S', 'B'] as const
export type Direction = typeof directions[number]
export const directionNames: Record<Direction, string> = { U: 'Utara', T: 'Timur', S: 'Selatan', B: 'Barat' }
export const signalNames = { red: 'Merah', yellow: 'Kuning', green: 'Hijau', unknown: 'Belum diketahui' }
export const phaseNames = { green: 'Hijau', yellow: 'Kuning', all_red: 'Semua merah' }
export const modeNames = { fixed_time: 'Waktu tetap', adaptive: 'Adaptif', fallback: 'Fallback' }
export const eventNames: Record<TrafficEvent['event_type'], string> = {
  service_started: 'Sesi dimulai', service_stopped: 'Sesi dihentikan', phase_changed: 'Pergantian fase',
  clearance_held: 'Clearance ditahan', clearance_released: 'Area konflik bebas', control_changed: 'Pengendali berubah',
  fault: 'Gangguan pengendali', recovered: 'Layanan pulih',
}
export const localTime = (value: string) => new Intl.DateTimeFormat('id-ID', {
  timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', second: '2-digit',
}).format(new Date(value))

// JSON Schema validates field types; these checks cover relationships between fields.
export function supportedGeometry(config: IntersectionConfig): boolean {
  return directions.every((code, i) => {
    const arm = config.approaches.find(a => a.code === code)
    return config.geometry.incoming_lanes_per_approach === 3 && config.geometry.outgoing_lanes_per_approach === 3
      && arm?.outer.left === directions[(i + 1) % 4] && arm.middle.straight === directions[(i + 2) % 4]
      && arm.inner.right === directions[(i + 3) % 4]
  })
}

export function coherentStatus(status: AtcsStatus, intersectionId: string): boolean {
  if (status.intersection_id !== intersectionId) return false
  if (status.availability !== 'available') return true
  if (status.engine_state !== 'running' || !status.run_id || !status.controller || !status.mode
    || !status.signals || !status.phase || status.updated_at === null || status.sequence_number === null
    || status.simulation_time_seconds === null || !status.conflict_area) return false
  if (Object.keys(status.signals).length !== 4) return false
  if (status.phase === 'all_red') {
    if (status.active_approach !== null || status.clearance_state === null) return false
    if ((status.remaining_seconds === null) !== (status.clearance_state === 'waiting_conflict')) return false
  } else if (!status.active_approach || status.clearance_state !== null || status.remaining_seconds === null) return false
  return directions.every(code => status.signals?.[code] === (code === status.active_approach ? status.phase : 'red'))
}

export function freshStatus(status: AtcsStatus, requestMs: number): boolean {
  if (status.availability !== 'available') return true
  const age = Date.parse(status.observed_at) - Date.parse(status.updated_at!)
  return age >= 0 && age + requestMs <= 2000
}

export interface Journal {
  events: TrafficEvent[]
  cursor: number
  truncated: boolean
}
export const emptyJournal = (): Journal => ({ events: [], cursor: 0, truncated: false })

export function mergeJournal(previous: Journal, page: TrafficEvents, intersectionId: string, runId: string): Journal | null {
  if (page.intersection_id !== intersectionId || page.run_id !== runId || page.next_after < previous.cursor
    || page.next_after > page.latest_sequence || page.oldest_available_sequence > page.latest_sequence
    || page.has_more !== (page.next_after < page.latest_sequence)) return null
  let cursor = previous.cursor
  const ids = new Set<string>()
  for (const event of page.events) {
    if (event.intersection_id !== intersectionId || event.run_id !== runId || event.sequence_number <= cursor
      || event.sequence_number < page.oldest_available_sequence || event.sequence_number > page.latest_sequence
      || event.event_id !== `${runId}:${event.sequence_number}` || ids.has(event.event_id)) return null
    if (event.sequence_number !== cursor + 1 && !(cursor === previous.cursor && page.history_truncated)) return null
    ids.add(event.event_id)
    cursor = event.sequence_number
  }
  if (page.next_after !== cursor || (page.has_more && cursor === previous.cursor)) return null
  const events = [...previous.events, ...page.events]
  return { events: events.slice(-100), cursor, truncated: previous.truncated || page.history_truncated || events.length > 100 }
}
