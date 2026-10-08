import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ControlPanel } from './ControlPanel'
import { useControl } from './useControl'
import { config, respond, runId, secondRunId, sessionFixture } from './testFixtures'
import type { ControlStatus } from './types/ControlStatus'
import type { CommandReceipt } from './types/CommandReceipt'

let status: ControlStatus
let receipt: CommandReceipt | null
let body: Record<string, unknown> | null
let headers: HeadersInit | undefined
let disconnected = false
let lostAcknowledgment = false
let frozen = false
let posts = 0
const flush = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms) }) }
function Screen({ mayControl = true, allowSynthetic = false }) {
  const control = useControl(config.intersection_id, sessionFixture().csrf_token, mayControl, allowSynthetic)
  return <ControlPanel control={control} mayControl={mayControl} allowSynthetic={allowSynthetic} />
}
const activate = () => screen.getByRole('button', { name: 'Aktifkan kendali SIGAP' }) as HTMLButtonElement
const release = () => screen.getByRole('button', { name: 'Kembalikan ke ATCS' }) as HTMLButtonElement

beforeEach(() => {
  vi.useFakeTimers()
  status = { emergency:null, emergency_serving:false, intersection_id: config.intersection_id, atcs_run_id: runId, observed_at: new Date().toISOString(),
    available: true, configured: true, allow_test_source: false, state: 'fixed_time', controller: 'ATCS', revision: 3,
    sender_id: secondRunId, source: 'cctv', ready: true, readiness_reason: 'Empat pendekat siap.', activation_required: true,
    session_id: null, heartbeat_remaining_seconds: null, data_remaining_seconds: 3, pending_request_id: null,
    active_request_id: null, fallback_code: null, reason: 'ATCS berjalan.', events: [],
    policy: { heartbeat_timeout_seconds: 3, data_timeout_seconds: 3, plan_wait_seconds: 8, minimum_green_seconds: 10,
      maximum_green_seconds: 60, maximum_command_ttl_seconds: 5, maximum_plan_horizon_seconds: 180, clock_skew_seconds: 1 } }
  receipt = null; body = null; headers = undefined; disconnected = false; lostAcknowledgment = false; frozen = false; posts = 0
  vi.stubGlobal('fetch', vi.fn((input: string, init?: RequestInit) => {
    if (disconnected) return Promise.reject(new Error('Koneksi terputus.'))
    if (input.endsWith('/control')) return respond({ ...status, observed_at: frozen ? status.observed_at : new Date().toISOString() })
    if (input.includes('/control/receipts/')) return respond(receipt || {}, receipt ? 200 : 404)
    if (input.endsWith('/control/commands')) {
      posts++
      body = JSON.parse(init!.body as string)
      headers = init?.headers
      receipt = { request_id: body!.request_id as string, atcs_run_id: runId, action: body!.action as 'activate' | 'release', outcome: 'accepted',
        code: 'ACCEPTED', message: 'Menunggu transisi aman.', session_id: secondRunId, revision: 4,
        received_at: new Date().toISOString(), updated_at: new Date().toISOString(), duplicate: false }
      if (lostAcknowledgment) return Promise.reject(new Error('Konfirmasi terputus.'))
      return respond(receipt)
    }
    return respond({}, 404)
  }))
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('does not manufacture readiness or send heartbeats from the browser', async () => {
  status = { ...status, ready: false, source: null, sender_id: null }
  render(<Screen />)
  await flush(1500)
  expect(activate().disabled).toBe(true)
  expect(release().disabled).toBe(true)
  expect(posts).toBe(0)
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method)).toBe(true)
})

it('does not enable an integration-test source or a monitor-only account', async () => {
  status.source = 'integration_test'; status.allow_test_source = true
  const view = render(<Screen />)
  await flush()
  expect(activate().disabled).toBe(true)
  status.source = 'cctv'
  view.rerender(<Screen mayControl={false} />)
  await flush(700)
  expect(activate().disabled).toBe(true)
})

it('sends the displayed run/revision with CSRF and distinguishes accepted from applied', async () => {
  render(<Screen />)
  await flush()
  expect(activate().disabled).toBe(false)
  fireEvent.click(activate())
  await flush()
  expect(body).toMatchObject({ action: 'activate', expected_run_id: runId, expected_revision: 3 })
  expect(new Headers(headers).get('X-CSRF-Token')).toBe(sessionFixture().csrf_token)
  expect(screen.getByText('Diterima · menunggu penerapan')).toBeTruthy()
  expect(screen.queryByText('Sudah diterapkan')).toBeNull()
  receipt = { ...receipt!, outcome: 'applied', code: 'CONTROL_ACQUIRED', message: 'Transisi selesai.' }
  status = { ...status, state: 'adaptive', controller: 'SIGAP', session_id: secondRunId, activation_required: false, revision: 5 }
  await flush(700)
  expect(screen.getByText('Sudah diterapkan')).toBeTruthy()
  expect(release().disabled).toBe(false)
  expect(activate().disabled).toBe(true)
  expect(posts).toBe(1)
})

it('requires both source gates for explicitly labelled stage five activation', async () => {
  status.source = 'integration_test'
  const view = render(<Screen allowSynthetic />)
  await flush()
  expect(activate().disabled).toBe(true)
  status.allow_test_source = true
  await flush(700)
  const button = screen.getByRole('button', { name: 'Aktifkan SIGAP dengan data buatan' }) as HTMLButtonElement
  expect(button.disabled).toBe(false)
  fireEvent.click(button)
  await flush()
  expect(posts).toBe(1)
  expect(body).toMatchObject({action:'activate'})
  view.unmount()
})

it('recovers a lost acknowledgement using a receipt without resending control', async () => {
  lostAcknowledgment = true
  render(<Screen />)
  await flush()
  fireEvent.click(activate())
  await flush()
  expect(screen.getByRole('alert').textContent).toContain('Konfirmasi terputus')
  await flush(700)
  expect(screen.getByText('Diterima · menunggu penerapan')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
  expect(posts).toBe(1)
})

it('disables actions on disconnect, frozen replies and hidden pages', async () => {
  render(<Screen />)
  await flush()
  disconnected = true
  await flush(700)
  expect(activate().disabled).toBe(true)
  disconnected = false
  frozen = true
  await flush(3500)
  expect(activate().disabled).toBe(true)
  frozen = false
  await flush(700)
  expect(activate().disabled).toBe(false)
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
  act(() => document.dispatchEvent(new Event('visibilitychange')))
  expect(activate().disabled).toBe(true)
})

it('shows rejected and cancelled requests and never automatically reacquires control', async () => {
  render(<Screen />)
  await flush()
  fireEvent.click(activate())
  await flush()
  receipt = { ...receipt!, outcome: 'cancelled', code: 'DATA_UNUSABLE', message: 'Data tidak layak.' }
  status = { ...status, ready: false, state: 'returning_atcs', fallback_code: 'DATA_UNUSABLE' }
  await flush(700)
  expect(screen.getByText('Dibatalkan')).toBeTruthy()
  expect(activate().disabled).toBe(true)
  status = { ...status, state: 'fixed_time', ready: true, revision: 8 }
  await flush(700)
  expect(activate().disabled).toBe(false)
  expect(posts).toBe(1)
})
