import Ajv2020, { type ValidateFunction } from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import healthSchema from './schemas/Health.json'
import configSchema from './schemas/IntersectionConfig.json'
import statusSchema from './schemas/AtcsStatus.json'
import eventsSchema from './schemas/TrafficEvents.json'
import type { Health } from './types/Health'
import type { IntersectionConfig } from './types/IntersectionConfig'
import type { AtcsStatus } from './types/AtcsStatus'
import type { TrafficEvents } from './types/TrafficEvents'
import { authGeneration, rejectSession } from './authEvents'

const ajv = new Ajv2020()
addFormats(ajv)
const isHealth = ajv.compile<Health>(healthSchema)
const isConfig = ajv.compile<IntersectionConfig>(configSchema)
const isStatus = ajv.compile<AtcsStatus>(statusSchema)
const isEvents = ajv.compile<TrafficEvents>(eventsSchema)
const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export type Resource<T> =
  | { state: 'loading' }
  | { state: 'ready'; data: T }
  | { state: 'unavailable' }

export interface Snapshot {
  backend: Resource<Health>
  atcs: Resource<Health>
  configuration: Resource<IntersectionConfig>
}

async function read<T>(path: string, validate: ValidateFunction<T>, signal: AbortSignal,
  service?: Health['service'], allowUnavailable = false, timeoutMs = 5500): Promise<Resource<T>> {
  const request = new AbortController()
  const generation = authGeneration()
  const cancel = () => request.abort()
  signal.addEventListener('abort', cancel, { once: true })
  if (signal.aborted) request.abort()
  const timeout = setTimeout(cancel, timeoutMs)
  try {
    const response = await fetch(`${base}${path}`, { signal: request.signal, cache: 'no-store', credentials: 'same-origin' })
    if ((response.status === 401 || response.status === 403) && !signal.aborted) rejectSession(generation)
    // A valid 503 health report still proves the service API is alive.
    if (!response.ok && !((service || allowUnavailable) && response.status === 503)) throw new Error('HTTP error')
    const data: unknown = await response.json()
    if (!validate(data)) throw new Error('Invalid contract')
    if (service && (!isHealth(data) || data.service !== service)) throw new Error('Wrong service')
    if (allowUnavailable && response.status === 503 && isStatus(data) && data.availability === 'available') throw new Error('Inconsistent availability')
    return { state: 'ready', data }
  } catch {
    return { state: 'unavailable' }
  } finally {
    clearTimeout(timeout)
    signal.removeEventListener('abort', cancel)
  }
}

export function readStatus(signal: AbortSignal) {
  return read('/atcs/status', isStatus, signal, undefined, true, 1800)
}

export function readEvents(signal: AbortSignal, runId: string, after: number) {
  const query = new URLSearchParams({ run_id: runId, after: String(after), limit: '500' })
  return read(`/atcs/events?${query}`, isEvents, signal, undefined, false, 2500)
}

export async function readSnapshot(signal: AbortSignal): Promise<Snapshot> {
  const [backend, atcs, configuration] = await Promise.all([
    read('/health', isHealth, signal, 'backend'),
    read('/atcs/health', isHealth, signal, 'atcs'),
    read('/configuration', isConfig, signal),
  ])
  return { backend, atcs, configuration }
}
