import { describe, expect, it } from 'vitest'
import { coherentStatus, emptyJournal, freshStatus, mergeJournal, supportedGeometry } from './traffic'
import { config, eventFixture, pageFixture, runId, secondRunId, statusFixture } from './testFixtures'

describe('signal integrity', () => {
  it('accepts all approaches only with the agreed left-driving route mapping', () => {
    expect(supportedGeometry(config)).toBe(true)
    const bad = structuredClone(config)
    bad.approaches[0].outer.left = 'B'
    expect(supportedGeometry(bad)).toBe(false)
  })
  it('rejects conflicting lamps, wrong identity, missing countdown, and an all-red active approach', () => {
    const valid = statusFixture()
    expect(coherentStatus(valid, config.intersection_id)).toBe(true)
    expect(coherentStatus(valid, 'another-intersection')).toBe(false)
    expect(coherentStatus({ ...valid, signals: { ...valid.signals, T: 'green' } }, config.intersection_id)).toBe(false)
    expect(coherentStatus({ ...valid, remaining_seconds: null }, config.intersection_id)).toBe(false)
    expect(coherentStatus({ ...valid, phase: 'all_red', clearance_state: 'minimum' }, config.intersection_id)).toBe(false)
  })
  it('accepts indefinite all-red only while waiting for conflict clearance', () => {
    const held = statusFixture({ active_approach: null, phase: 'all_red', signals: { U: 'red', T: 'red', S: 'red', B: 'red' }, clearance_state: 'waiting_conflict', remaining_seconds: null })
    expect(coherentStatus(held, config.intersection_id)).toBe(true)
    expect(coherentStatus({ ...held, clearance_state: 'minimum' }, config.intersection_id)).toBe(false)
    expect(coherentStatus({ ...held, remaining_seconds: 0 }, config.intersection_id)).toBe(false)
  })
  it('uses server observation age plus roundtrip time, independent of the browser clock', () => {
    expect(freshStatus(statusFixture(), 30)).toBe(true)
    expect(freshStatus(statusFixture(), 2100)).toBe(false)
    expect(freshStatus(statusFixture({ updated_at: '2026-10-03T08:00:00Z' }), 20)).toBe(false)
    expect(freshStatus(statusFixture({ updated_at: '2026-10-03T08:00:03Z' }), 20)).toBe(false)
  })
})

describe('event journal', () => {
  it('merges cursor pages once and accepts unchanged empty responses', () => {
    const first = mergeJournal(emptyJournal(), pageFixture(), config.intersection_id, runId)!
    expect(first.events.length).toBe(1)
    expect(mergeJournal(first, pageFixture({ events: [] }), config.intersection_id, runId)).toEqual(first)
    expect(mergeJournal(first, pageFixture(), config.intersection_id, runId)).toBeNull()
  })
  it('rejects mixed sessions, wrong intersections and inconsistent cursors', () => {
    expect(mergeJournal(emptyJournal(), pageFixture({ run_id: secondRunId }), config.intersection_id, runId)).toBeNull()
    expect(mergeJournal(emptyJournal(), pageFixture({ events: [eventFixture({ run_id: secondRunId })] }), config.intersection_id, runId)).toBeNull()
    expect(mergeJournal(emptyJournal(), pageFixture({ intersection_id: 'other' }), config.intersection_id, runId)).toBeNull()
    expect(mergeJournal(emptyJournal(), pageFixture({ next_after: 0 }), config.intersection_id, runId)).toBeNull()
  })
  it('only allows gaps when the API declares a retention truncation', () => {
    const page = pageFixture({ events: [eventFixture({ sequence_number: 8, event_id: `${runId}:8` })], oldest_available_sequence: 8, latest_sequence: 8, next_after: 8 })
    expect(mergeJournal(emptyJournal(), page, config.intersection_id, runId)).toBeNull()
    expect(mergeJournal(emptyJournal(), { ...page, history_truncated: true }, config.intersection_id, runId)?.truncated).toBe(true)
  })
  it('retains the latest 100 events without losing the server cursor', () => {
    const events = Array.from({ length: 130 }, (_, i) => eventFixture({ event_id: `${runId}:${i + 1}`, sequence_number: i + 1 }))
    const merged = mergeJournal(emptyJournal(), pageFixture({ events, latest_sequence: 130, next_after: 130 }), config.intersection_id, runId)!
    expect(merged.events).toHaveLength(100)
    expect(merged.events[0].sequence_number).toBe(31)
    expect(merged.cursor).toBe(130)
    expect(merged.truncated).toBe(true)
  })
})
