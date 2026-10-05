import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Monitor } from './Monitor'
import { config, pageFixture, respond, runId, secondRunId, sessionFixture, statusFixture } from './testFixtures'
import type { AdaptiveStatus } from './types/AdaptiveStatus'
import type { ControlStatus } from './types/ControlStatus'
import type { TrafficView } from './types/TrafficView'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('shows the same video demand, poses and actual SIGAP phase in ATCS and SIGAP, clearing video poses on fallback', async () => {
  vi.useFakeTimers()
  let acquired = true
  let sequence = 1
  const at = new Date().toISOString()
  const video: AdaptiveStatus = { enabled:true, source:'recording', fault:'none', status:'active', message:'SIGAP aktif.',
    auto_resume:true, source_sessions:{U:runId,T:runId,S:runId,B:runId}, issues:{}, decisions:[],
    policy:{minimum_green:10,maximum_green:60,queue_weight:4,wait_weight:1,age_weight:.5,
      service_age_target:120,seconds_per_queued_vehicle:2,data_timeout:3},
    measurements:{intersection_id:config.intersection_id,source:'recording',source_session:secondRunId,sequence:1,
      approaches:Object.fromEntries(['U','T','S','B'].map(d => [d,{observed_at:at,usable:true,controlled_count:2,
        queue_count:1,oldest_wait_seconds:7,slip_count:0,exit_available:true}]))},
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
    if (url.endsWith('/adaptive')) return respond({...video,status:acquired?'active':'unavailable',
      map_vehicles:acquired?video.map_vehicles:[]})
    return respond({},503)
  }))
  const view = render(<Monitor session={sessionFixture()} onLogout={() => undefined} signingOut={false} logoutError={null} />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByTestId('countdown').textContent).toBe('18')
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  expect(screen.getByText(/SIGAP mengambil alih kendali/)).toBeTruthy()
  const switcher = screen.getByRole('group',{name:'Mode ruang kerja'})
  fireEvent.click(within(switcher).getByRole('button',{name:/SIGAP Adaptif/}))
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByTestId('countdown').textContent).toBe('18')
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  acquired = false
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeNull()
  expect(screen.getByText(/ATCS mengendalikan · waktu tetap/)).toBeTruthy()
})
