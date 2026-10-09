import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Monitor } from './Monitor'
import { config, pageFixture, respond, runId, secondRunId, sessionFixture, statusFixture } from './testFixtures'
import type { AdaptiveStatus } from './types/AdaptiveStatus'
import type { ControlStatus } from './types/ControlStatus'
import type { TrafficView } from './types/TrafficView'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })
const flush = async (ms=0) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
const target = {event_id:'video:T:7',direction:'T' as const,source_session:secondRunId,track_id:7,kind:'ambulance' as const,confidence:.9,distance_to_stop:.4,observed_at:new Date().toISOString()}
const pose: TrafficView['vehicles'][number] = {id:11,origin:'T',movement:'straight',kind:'motorcycle',x:1100,y:470,heading:180,
  stopped:true,served:false,distance_to_stop:200,lane:'middle',target_lane:'middle',changing_to:null,stop_reason:'stationary'}
function setup(waiting=false, unusable=false) {
  vi.useFakeTimers()
  const scenario = {state:'fixed_time' as ControlStatus['state'], stale:false, controlUnavailable:false, phaseUnavailable:false, sequence:1}
  const video: AdaptiveStatus = {emergency:{state:'confirmed',target,candidates:[target],focus:true,message:'EVP terkonfirmasi',events:[]},enabled:true,source:'recording',fault:'none',status:'active',message:'Video tersedia.',
    auto_resume:false,source_sessions:{U:runId,T:runId,S:runId,B:runId},issues:{},decisions:[],
    policy:{video_baseline_floor_ratio:.75,video_maximum_drop_ratio:.2,minimum_green:10,maximum_green:60,queue_weight:4,wait_weight:1,age_weight:.5,
      service_age_target:120,seconds_per_queued_vehicle:2,data_timeout:3},
    measurements:{intersection_id:config.intersection_id,source:'recording',source_session:secondRunId,sequence:1,
      approaches:Object.fromEntries(['U','T','S','B'].map(d=>[d,{observed_at:new Date().toISOString(),usable:!unusable,controlled_count:2,
        queue_count:1,oldest_wait_seconds:7,slip_count:0,exit_available:true,queue_visibility:'partial' as const,occupancy_ratio:0,queue_reaches_boundary:false}]))},
    map_vehicles:[pose,{...pose,id:12}]}
  const control: ControlStatus = {emergency:null,emergency_serving:false,intersection_id:config.intersection_id,atcs_run_id:runId,observed_at:new Date().toISOString(),
    available:true,configured:true,allow_test_source:false,state:'fixed_time',controller:'ATCS',revision:3,sender_id:secondRunId,source:'cctv',ready:true,
    readiness_reason:'Sumber siap.',activation_required:true,session_id:null,heartbeat_remaining_seconds:null,data_remaining_seconds:3,
    pending_request_id:null,active_request_id:null,fallback_code:null,reason:'Kendali terverifikasi.',events:[],
    policy:{heartbeat_timeout_seconds:3,data_timeout_seconds:3,plan_wait_seconds:8,minimum_green_seconds:10,maximum_green_seconds:60,
      maximum_command_ttl_seconds:5,maximum_plan_horizon_seconds:180,clock_skew_seconds:1}}
  const synthetic: TrafficView = {intersection_id:config.intersection_id,source:'atcs_synthetic',run_id:runId,observed_at:new Date().toISOString(),available:true,
    time_seconds:0,running:true,speed:1,strategy:'fixed_time',phase:'green',active_approach:'U',signals:{U:'green',T:'red',S:'red',B:'red'},
    remaining_seconds:99,emergency:false,target_vehicle:null,reason:'Data buatan.',demand:{U:0,T:0,S:0,B:0},blocked_exit:null,events:[],evp_queue:[],
    vehicles:[{...pose,id:99,kind:'car',origin:'U',x:470,y:0,heading:90}],queues:{U:0,T:0,S:0,B:0},completed:0,average_wait:0,waiting_seconds:0,
    refused_spawns:0,conflict:'clear',traffic_sequence:1,decision:null}
  vi.stubGlobal('fetch',vi.fn((url:string) => {
    const acquired = scenario.state==='adaptive'
    if (url.endsWith('/configuration')) return respond(config)
    if (url.endsWith('/atcs/status')) return scenario.phaseUnavailable ? respond({},503) : respond(statusFixture({sequence_number:scenario.sequence++,
      controller:acquired?'SIGAP':'ATCS',mode:acquired?'adaptive':scenario.state==='returning_atcs'?'fallback':'fixed_time',active_approach:'T',
      signals:{U:'red',T:'green',S:'red',B:'red'},remaining_seconds:18}))
    if (url.includes('/atcs/events?')) return respond(pageFixture())
    if (url.endsWith('/atcs/traffic')) return respond({...synthetic,traffic_sequence:scenario.sequence++})
    if (url.endsWith('/control')) return scenario.controlUnavailable ? respond({},503) : respond({...control,state:scenario.state,controller:acquired?'SIGAP':'ATCS',
      session_id:acquired||scenario.state==='activating'?secondRunId:null,observed_at:new Date().toISOString(),emergency:acquired?target:null})
    if (url.endsWith('/adaptive')) return respond({...video,status:acquired&&!waiting?'active':'unavailable',measurements:{...video.measurements,
      approaches:Object.fromEntries(['U','T','S','B'].map(d=>[d,{...video.measurements!.approaches[d],observed_at:new Date(Date.now()-(scenario.stale&&d==='U'?4000:0)).toISOString()}]))}})
    return respond({},503)
  }))
  const view = render(<Monitor session={sessionFixture()} onLogout={()=>undefined} signingOut={false} logoutError={null} />)
  const select = (name:RegExp) => fireEvent.click(within(screen.getByRole('group',{name:'Mode ruang kerja'})).getByRole('button',{name}))
  const trafficRequests = () => vi.mocked(fetch).mock.calls.filter(([url])=>String(url).endsWith('/atcs/traffic')).length
  return {scenario,video,view,select,trafficRequests}
}

it.each([false,true])('follows acquired control through activation and release, independent of open workspace and adaptive readiness (%s)',async waiting=>{
  const {scenario,view,select,trafficRequests}=setup(waiting)
  await flush()
  expect(view.container.querySelector('[data-vehicle-id="99"]')).toBeTruthy()
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeNull()
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
  select(/SIGAP Adaptif/);await flush()
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
  select(/ATCS Fase bersama/);await flush(300)
  expect(view.container.querySelector('[data-vehicle-id="99"]')).toBeTruthy()
  scenario.state='activating';await flush(1000)
  expect(view.container.querySelector('[data-vehicle-id="99"]')).toBeTruthy()
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
  scenario.state='adaptive';await flush(1000)
  expect(view.container.querySelector('[data-vehicle-id="99"]')).toBeNull()
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(screen.getByTestId('countdown').textContent).toBe('18')
  expect(screen.getByRole('status',{name:'Prioritas kendaraan darurat'})).toBeTruthy()
  const counts=screen.getByRole('table',{name:'Jumlah kendaraan video dan peta'})
  expect(within(counts).getAllByRole('row').slice(1).map(row=>within(row).getAllByRole('cell')[0].textContent)).toEqual(['0','2','0','0'])
  const before=trafficRequests()
  select(/SIGAP Adaptif/);await flush(500)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(trafficRequests()).toBe(before)
  scenario.state='returning_atcs';await flush(1000)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
  select(/ATCS Fase bersama/);await flush(500)
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  expect(view.container.querySelector('[data-vehicle-id="99"]')).toBeNull()
  expect(trafficRequests()).toBe(before)
  scenario.state='fixed_time';await flush(1000)
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeNull()
  expect(view.container.querySelector('[data-vehicle-id="99"]')).toBeTruthy()
  expect(screen.getByTestId('countdown').textContent).toBe('99')
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
  select(/SIGAP Adaptif/);await flush()
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
  expect(vi.mocked(fetch).mock.calls.every(([,init])=>!init?.method)).toBe(true)
})

it('keeps zone tracking available in SIGAP preview before acquisition, including unusable measurements and per-camera staleness',async()=>{
  const {scenario,video,view,select}=setup(false,true)
  video.map_vehicles=[{...pose,id:11,origin:'U'}, {...pose,id:12}, {...pose,id:13}]
  await flush()
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(1)
  expect(view.container.querySelector('[data-vehicle-id="99"]')).toBeTruthy()
  select(/SIGAP Adaptif/);await flush()
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(3)
  expect(screen.getByText(/3 kendaraan dalam zona ditampilkan di peta/)).toBeTruthy()
  const rows=within(screen.getByRole('table',{name:'Jumlah kendaraan video dan peta'})).getAllByRole('row').slice(1)
  expect(rows.map(row=>within(row).getAllByRole('cell')[0].textContent)).toEqual(['1','2','0','0'])
  expect(rows.map(row=>within(row).getAllByRole('cell')[1].textContent)).toEqual(['—','—','—','—'])
  scenario.stale=true;await flush(1000)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeNull()
})

it('uses verified phase ownership when control polling fails and hides EVP when authority cannot be verified',async()=>{
  const {scenario,view,select}=setup()
  scenario.state='adaptive';await flush()
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  scenario.controlUnavailable=true;await flush(1000)
  expect(view.container.querySelector('[data-vehicle-id="11"]')).toBeTruthy()
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
  scenario.phaseUnavailable=true;await flush(1000)
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(0)
  select(/SIGAP Adaptif/);await flush()
  expect(view.container.querySelectorAll('.map-vehicle')).toHaveLength(2)
  expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
})