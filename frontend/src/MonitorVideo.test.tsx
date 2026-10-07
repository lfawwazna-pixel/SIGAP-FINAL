import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Monitor } from './Monitor'
import { config, pageFixture, respond, runId, secondRunId, sessionFixture, statusFixture } from './testFixtures'
import type { AdaptiveStatus } from './types/AdaptiveStatus'
import type { ControlStatus } from './types/ControlStatus'
import type { TrafficView } from './types/TrafficView'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it.each([false, true])('shows identical camera counts in both workspaces after takeover, including pending/unavailable adaptive status (%s)', async (waiting) => {
  vi.useFakeTimers()
  let acquired = true
  let sequence = 1
  const at = new Date().toISOString()
  const video: AdaptiveStatus = { enabled:true, source:'recording', fault:'none', status:'active', message:'SIGAP aktif.',
    auto_resume:true, source_sessions:{U:runId,T:runId,S:runId,B:runId}, issues:{}, decisions:[],
    policy:{video_baseline_floor_ratio:.75,video_maximum_drop_ratio:.2,minimum_green:10,maximum_green:60,queue_weight:4,wait_weight:1,age_weight:.5,
      service_age_target:120,seconds_per_queued_vehicle:2,data_timeout:3},
    measurements:{intersection_id:config.intersection_id,source:'recording',source_session:secondRunId,sequence:1,
      approaches:Object.fromEntries(['U','T','S','B'].map(d => [d,{observed_at:at,usable:true,controlled_count:2,
        queue_count:1,oldest_wait_seconds:7,slip_count:0,exit_available:true,queue_visibility:'partial' as const,occupancy_ratio:0,queue_reaches_boundary:false}]))},
    map_vehicles:[{id:11,origin:'T',movement:'straight',kind:'car',x:1100,y:470,heading:180,
      stopped:true,served:false,distance_to_stop:200,lane:'middle',target_lane:'middle',changing_to:null,stop_reason:'stationary'}] }
  const control: ControlStatus = {intersection_id:config.intersection_id,atcs_run_id:runId,observed_at:at,
    available:true,configured:true,allow_test_source:false,state:'adaptive',controller:'SIGAP',revision:3,
    sender_id:secondRunId,source:'cctv',ready:true,readiness_reason:'Sumber siap.',activation_required:false,
    session_id:secondRunId,heartbeat_remaining_seconds:3,data_remaining_seconds:3,pending_request_id:null,
    active_request_id:null,fallback_code:null,reason:'SIGAP aktif.',events:[],
    policy:{heartbeat_timeout_seconds:3,data_timeout_seconds:3,plan_wait_seconds:8,minimum_green_seconds:10,
      maximum_green_seconds:60,maximum_command_ttl_seconds:5,maximum_plan_horizon_seconds:180,clock_skew_seconds:1}}
  const synthetic: TrafficView = {intersection_id:config.intersection_id,source:'atcs_synthetic',run_id:runId,observed_at:at,
    available:true,time_seconds:0,running:true,speed:1,strategy:'fixed_time',phase:'green',active_approach:'U',
    signals:{U:'green',T:'red',S:'red',B:'red'},remaining_seconds:99,emergency:false,target_vehicle:null,reason:'Data buatan.',
    demand:{U:0,T:0,S:0,B:0},blocked_exit:null,events:[],evp_queue:[],vehicles:[],queues:{U:0,T:0,S:0,B:0},
    completed:0,average_wait:0,waiting_seconds:0,refused_spawns:0,conflict:'clear',traffic_sequence:1,decision:null}
  vi.stubGlobal('fetch',vi.fn((url:string) => {
    if (url.endsWith('/configuration')) return respond(config)
    if (url.endsWith('/atcs/status')) return respond(statusFixture({sequence_number:sequence++,
      controller:acquired?'SIGAP':'ATCS',mode:acquired?'adaptive':'fixed_time',active_approach:'T',
      signals:{U:'red',T:'green',S:'red',B:'red'},remaining_seconds:18}))
    if (url.includes('/atcs/events?')) return respond(pageFixture())
    if (url.endsWith('/atcs/traffic')) return respond({...synthetic,traffic_sequence:sequence++})
    if (url.endsWith('/control')) return respond({...control,observed_at:new Date().toISOString(),
      state:acquired?'adaptive':'fixed_time',controller:acquired?'SIGAP':'ATCS'})
    if (url.endsWith('/adaptive')) return respond({...video,status:acquired?(waiting?'unavailable':'active'):'unavailable',
      map_vehicles:video.map_vehicles})
    return respond({},503)
  }))
  const view = render(<Monitor session={sessionFixture()} onLogout={() => undefined} signingOut={false} logoutError={null} />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByTestId('countdown').textContent).toBe('18')
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(1)
  const counts = screen.getByRole('table', {name:'Jumlah kendaraan video dan peta'})
  expect(within(counts).getAllByRole('row').slice(1).map(row => within(row).getAllByRole('cell')[0].textContent)).toEqual(['0','1','0','0'])
  expect(screen.getByText(/SIGAP mengambil alih kendali/)).toBeTruthy()
  const trafficRequests = () => vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/atcs/traffic')).length
  const statusRequests = () => vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/atcs/status')).length
  const beforeTraffic = trafficRequests()
  const beforeStatus = statusRequests()
  await act(async () => { await vi.advanceTimersByTimeAsync(500) })
  expect(trafficRequests()).toBe(beforeTraffic)
  expect(statusRequests()).toBeGreaterThan(beforeStatus)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(1)
  const switcher = screen.getByRole('group',{name:'Mode ruang kerja'})
  fireEvent.click(within(switcher).getByRole('button',{name:/SIGAP Adaptif/}))
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByTestId('countdown').textContent).toBe('18')
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  acquired = false
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  expect(screen.getByText(/ATCS mengendalikan · waktu tetap/)).toBeTruthy()
  fireEvent.click(within(switcher).getByRole('button',{name:/ATCS Fase bersama/}))
  await act(async () => { await vi.advanceTimersByTimeAsync(500) })
  expect(trafficRequests()).toBe(beforeTraffic)
  expect(screen.getByTestId('countdown').textContent).toBe('18')
})

it('shows all tracked vehicles upon selecting SIGAP before controller activation, without valid calibration', async () => {
  vi.useFakeTimers()
  let sequence = 1
  let stale = false
  const at = new Date().toISOString()
  const pose = {id:11,origin:'U' as const,movement:'straight' as const,kind:'car' as const,x:470,y:0,heading:90,
    stopped:false,served:false,distance_to_stop:240,lane:'middle' as const,target_lane:'middle' as const,
    changing_to:null,stop_reason:null}
  const video: AdaptiveStatus = {enabled:true,source:'recording',fault:'none',status:'unavailable',message:'Periksa kalibrasi.',
    auto_resume:false,source_sessions:{},issues:{U:'Kalibrasi belum sesuai.'},decisions:[],
    policy:{video_baseline_floor_ratio:.75,video_maximum_drop_ratio:.2,minimum_green:10,maximum_green:60,queue_weight:4,wait_weight:1,age_weight:.5,
      service_age_target:120,seconds_per_queued_vehicle:2,data_timeout:3},
    measurements:{intersection_id:config.intersection_id,source:'recording',source_session:secondRunId,sequence:1,
      approaches:Object.fromEntries(['U','T','S','B'].map(d => [d,{observed_at:at,usable:false,controlled_count:0,
        queue_count:0,oldest_wait_seconds:0,slip_count:0,exit_available:true,queue_visibility:'partial' as const,occupancy_ratio:0,queue_reaches_boundary:false}]))},
    map_vehicles:[pose,{...pose,id:12,origin:'T',x:800,y:470,heading:180},{...pose,id:13,origin:'T',x:830,y:470,heading:180}]}
  vi.stubGlobal('fetch',vi.fn((url:string) => {
    if (url.endsWith('/configuration')) return respond(config)
    if (url.endsWith('/atcs/status')) return respond(statusFixture({sequence_number:sequence++}))
    if (url.includes('/atcs/events?')) return respond(pageFixture())
    if (url.endsWith('/adaptive')) return respond({...video, measurements:{...video.measurements,
      approaches:Object.fromEntries(['U','T','S','B'].map(d => [d,{...video.measurements!.approaches[d],
        observed_at:new Date(Date.now()-(stale && d==='U'?4000:0)).toISOString()}]))}})
    return respond({},503)
  }))
  const view = render(<Monitor session={sessionFixture()} onLogout={() => undefined} signingOut={false} logoutError={null} />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(3)
  fireEvent.click(within(screen.getByRole('group',{name:'Mode ruang kerja'})).getByRole('button',{name:/SIGAP Adaptif/}))
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(3)
  expect(screen.getByText(/3 kendaraan terlacak ditampilkan di peta/)).toBeTruthy()
  const rows = within(screen.getByRole('table',{name:'Jumlah kendaraan video dan peta'})).getAllByRole('row').slice(1)
  expect(rows.map(row => within(row).getAllByRole('cell')[0].textContent)).toEqual(['1','2','0','0'])
  expect(rows.map(row => within(row).getAllByRole('cell')[1].textContent)).toEqual(['—','—','—','—'])
  expect(screen.getByText(/ATCS mengendalikan · waktu tetap/)).toBeTruthy()
  stale = true
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeNull()
})
