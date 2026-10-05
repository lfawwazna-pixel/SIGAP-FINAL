import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { VideoPanel } from './VideoPanel'
import type { VideoStatus } from './types/VideoStatus'
import { respond, runId, secondRunId } from './testFixtures'

let state: VideoStatus
let frameSession: string
let posts: Record<string, unknown>[]
const flush = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms) }) }
const panel = (workspace: 'atcs'|'sigap'|'simulation', mayControl = true) => <VideoPanel workspace={workspace} csrf={'a'.repeat(64)} mayControl={mayControl} />

beforeEach(() => {
  vi.useFakeTimers()
  Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(() => 'blob:shared-preview')})
  Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
  frameSession = runId
  posts = []
  state = {preview_fps:5,channels:(['U','T','S','B'] as const).map(direction => ({direction,source:'recording',
    source_session:runId,state:'playing',label:`Rekaman ${direction}`,frame_id:12,loop_count:0,media_seconds:2.4,
    frame_age_seconds:0,live_configured:false,detection_ready:false,tracking:null,calibration:null,message:'Video rekaman, YOLO belum tersedia.'})) as VideoStatus['channels']}
  vi.stubGlobal('fetch',vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') {
      const body = JSON.parse(init.body as string); posts.push(body)
      return respond(state.channels[0])
    }
    if (url.endsWith('/video')) return respond(state)
    return new Response(new Blob(['jpeg'],{type:'image/jpeg'}),{headers:{'Content-Type':'image/jpeg','X-Source-Session':frameSession,'X-Frame-Id':'12','X-Media-Seconds':'2.4','X-Tracking':url.includes('overlay=true') && state.channels[0].detection_ready ? 'ByteTrack' : 'none'}})
  }))
})
afterEach(() => {cleanup();vi.useRealTimers();vi.unstubAllGlobals();vi.restoreAllMocks()})

it('keeps the same video element/session across ATCS SIGAP and simulation without control commands',async () => {
  const view = render(panel('atcs'))
  await flush()
  const video = screen.getByAltText('Video pendekat Utara')
  expect(screen.queryByText(/YOLO belum diaktifkan/)).toBeNull()
  view.rerender(panel('sigap')); await flush(250)
  expect(screen.getByAltText('Video pendekat Utara')).toBe(video)
  expect(screen.getByText(/YOLO belum diaktifkan/)).toBeTruthy()
  expect(screen.getByText('Frame 12',{exact:false})).toBeTruthy()
  view.rerender(panel('simulation')); await flush(250)
  view.rerender(panel('atcs')); await flush(250)
  expect(screen.getByAltText('Video pendekat Utara')).toBe(video)
  expect(posts).toHaveLength(0)
})

it('requests tracked frames only in SIGAP, displays measured FPS and retains the shared session', async () => {
  state.channels[0].detection_ready = true
  state.channels[0].tracking = {state:'tracking',source_session:runId,frame_id:12,age_seconds:0,
    processing_fps:8.5,observed_fps:4.8,device:'cpu',message:'YOLO + ByteTrack berjalan.',
    tracks:[{track_id:1,class_name:'car',confidence:.8,bbox:[.1,.1,.4,.4]}]}
  const view = render(panel('sigap')); await flush()
  const img = screen.getByAltText('Video pendekat Utara')
  expect(screen.getByText(/ByteTrack · 1 kendaraan/)).toBeTruthy()
  expect(screen.getByText(/4.8 FPS · Pemrosesan: 8.5 FPS · CPU/)).toBeTruthy()
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith('frame?overlay=true'))).toBe(true)
  view.rerender(panel('atcs')); await flush(250)
  expect(screen.getByAltText('Video pendekat Utara')).toBe(img)
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith('frame?overlay=false'))).toBe(true)
  expect(posts).toHaveLength(0)
})

it('discards a frame from an old source and clears stale video', async () => {
  const view = render(panel('sigap'))
  await flush()
  expect(screen.getByAltText('Video pendekat Utara')).toBeTruthy()
  frameSession = secondRunId
  await flush(200)
  expect(screen.queryByAltText('Video pendekat Utara')).toBeNull()
  frameSession = runId
  await flush(200)
  expect(screen.getByAltText('Video pendekat Utara')).toBeTruthy()
  state.channels[0].state = 'stale'
  await flush(1000)
  expect(screen.queryByAltText('Video pendekat Utara')).toBeNull()
  view.unmount()
  expect(URL.revokeObjectURL).toHaveBeenCalled()
})

it('uses guarded commands and locks mutations for monitor-only accounts', async () => {
  const view = render(panel('atcs',false)); await flush()
  expect(screen.queryByRole('button',{name:'Jeda rekaman'})).toBeNull()
  expect(screen.queryByRole('button',{name:'Ulang rekaman'})).toBeNull()
  expect(screen.queryByRole('button',{name:'Jalankan video'})).toBeNull()
  expect((screen.getByLabelText('Unggah rekaman MP4') as HTMLInputElement).disabled).toBe(true)
  view.rerender(panel('atcs'))
  expect((screen.getByLabelText('Unggah rekaman MP4') as HTMLInputElement).disabled).toBe(false)
  fireEvent.click(screen.getByRole('button',{name:'Tandai lajur & garis henti'})); await flush()
  expect(screen.getByRole('button',{name:'Simpan penandaan'})).toBeTruthy()
  expect(posts).toEqual([])
})
