import { useEffect, useState } from 'react'
import { readEvents, readSnapshot, readStatus, type Resource, type Snapshot } from './api'
import { coherentStatus, emptyJournal, freshStatus, mergeJournal, type Journal } from './traffic'
import type { AtcsStatus } from './types/AtcsStatus'

const initialSnapshot = (): Snapshot => ({ backend: { state: 'loading' }, atcs: { state: 'loading' }, configuration: { state: 'loading' } })
export function useReadiness(revision: number) {
  const [snapshot, setSnapshot] = useState<Snapshot>(initialSnapshot)
  const [checking, setChecking] = useState(true)
  useEffect(() => {
    const abort = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      setChecking(true)
      const result = await readSnapshot(abort.signal)
      if (abort.signal.aborted) return
      setSnapshot(result)
      setChecking(false)
      timer = setTimeout(() => void poll(), 10000)
    }
    void poll()
    return () => { abort.abort(); clearTimeout(timer) }
  }, [revision])
  return { snapshot, checking }
}

export type Connection = 'loading' | 'live' | 'unavailable' | 'stale' | 'paused'
interface Monitor {
  status: Resource<AtcsStatus>
  connection: Connection
  runId: string | null
  receivedAt: string | null
}
const initialMonitor = (): Monitor => ({ status: { state: 'loading' }, connection: 'loading', runId: null, receivedAt: null })

export function useMonitor(intersectionId: string | undefined, revision: number) {
  const [monitor, setMonitor] = useState<Monitor>(initialMonitor)
  useEffect(() => {
    setMonitor(initialMonitor())
    if (!intersectionId) return
    let controller: AbortController | null = null
    let timer: ReturnType<typeof setTimeout>
    let watchdog: ReturnType<typeof setTimeout>
    let previous: AtcsStatus | null = null
    let progressAt = performance.now()
    let disposed = false
    const invalidate = (connection: Connection) => setMonitor(old => ({ ...old, connection, status: { state: 'unavailable' } }))
    const stop = () => { controller?.abort(); clearTimeout(timer); clearTimeout(watchdog) }
    async function poll() {
      if (disposed || document.hidden) return
      const request = new AbortController()
      controller = request
      const started = performance.now()
      const result = await readStatus(request.signal)
      if (disposed || request.signal.aborted) return
      if (result.state !== 'ready' || !coherentStatus(result.data, intersectionId!)) invalidate('unavailable')
      else {
        const data = result.data
        const now = performance.now()
        const sameRun = previous?.run_id === data.run_id
        const backwards = sameRun && data.availability === 'available' && previous?.sequence_number !== null
          && (data.sequence_number! < previous!.sequence_number! || data.simulation_time_seconds! < previous!.simulation_time_seconds!)
        if (!sameRun || data.sequence_number !== previous?.sequence_number) progressAt = now
        if (backwards || !freshStatus(data, now - started) || (data.availability === 'available' && now - progressAt >= 2000)) invalidate('stale')
        else {
          previous = data
          setMonitor({ status: result, connection: data.availability === 'available' ? 'live' : 'unavailable', runId: data.run_id, receivedAt: data.observed_at })
          clearTimeout(watchdog)
          // This timer only expires data; it never advances a phase or countdown.
          watchdog = setTimeout(() => invalidate('stale'), 2500)
        }
      }
      timer = setTimeout(() => void poll(), 500)
    }
    function resume() {
      stop()
      if (document.hidden) invalidate('paused')
      else { invalidate('loading'); void poll() }
    }
    const offline = () => { stop(); invalidate('unavailable') }
    document.addEventListener('visibilitychange', resume)
    window.addEventListener('online', resume)
    window.addEventListener('offline', offline)
    if (document.hidden) invalidate('paused')
    else void poll()
    return () => {
      disposed = true
      stop()
      document.removeEventListener('visibilitychange', resume)
      window.removeEventListener('online', resume)
      window.removeEventListener('offline', offline)
    }
  }, [intersectionId, revision])
  return monitor
}

export function useJournal(intersectionId: string | undefined, runId: string | null, revision: number) {
  const [journal, setJournal] = useState<Journal>(emptyJournal)
  const [state, setState] = useState<'loading' | 'ready' | 'unavailable'>('loading')
  const [owner, setOwner] = useState<{ intersectionId: string | undefined; runId: string | null }>({ intersectionId, runId })
  useEffect(() => {
    let current = emptyJournal()
    setOwner({ intersectionId, runId })
    setJournal(current)
    setState('loading')
    if (!intersectionId || !runId) return
    const abort = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      const result = await readEvents(abort.signal, runId!, current.cursor)
      if (abort.signal.aborted) return
      const merged = result.state === 'ready' ? mergeJournal(current, result.data, intersectionId!, runId!) : null
      if (merged) { current = merged; setJournal(merged); setState('ready') }
      else setState('unavailable')
      timer = setTimeout(() => void poll(), merged && result.state === 'ready' && result.data.has_more ? 0 : 2000)
    }
    void poll()
    return () => { abort.abort(); clearTimeout(timer) }
  }, [intersectionId, runId, revision])
  // Hide the previous session immediately, including the render before effect cleanup.
  return owner.intersectionId === intersectionId && owner.runId === runId
    ? { journal, state } : { journal: emptyJournal(), state: 'loading' as const }
}
