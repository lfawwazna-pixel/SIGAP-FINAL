import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { EmergencyPanel } from './EmergencyPanel'
import type { AdaptiveStatus } from './types/AdaptiveStatus'
import type { ControlStatus } from './types/ControlStatus'
const target={event_id:'U:source:tracker:7',direction:'U' as const,source_session:'00000000-0000-4000-8000-000000000001',track_id:7,kind:'ambulance' as const,confidence:.84,distance_to_stop:.2,observed_at:'2026-10-07T19:00:00Z'}
const emergency:AdaptiveStatus['emergency']={state:'confirmed',target,candidates:[target],focus:true,message:'EVP terkonfirmasi',events:[]}
const owned={available:true,state:'adaptive',controller:'SIGAP',session_id:'active-session',emergency:null,emergency_serving:false} as ControlStatus

afterEach(cleanup)
it.each(['fixed_time','activating','returning_atcs'])('hides retained EVP evidence while control is %s',state=>{
 render(<EmergencyPanel emergency={emergency} control={{...owned,state:state as ControlStatus['state'],controller:'ATCS',emergency:target,emergency_serving:true}} />)
 expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
})
it('hides EVP when control is unavailable or not supplied',()=>{
 const view=render(<EmergencyPanel emergency={emergency} />)
 expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
 view.rerender(<EmergencyPanel emergency={emergency} control={{...owned,available:false}} />)
 expect(screen.queryByRole('status',{name:'Prioritas kendaraan darurat'})).toBeNull()
})
it('shows confirmed EVP only after acquisition, before priority green',()=>{
 render(<EmergencyPanel emergency={emergency} control={owned} />)
 expect(screen.getByText('EVP terkonfirmasi')).toBeTruthy()
 expect(screen.getByText(/Lampu mengikuti transisi aman/)).toBeTruthy()
 expect(screen.queryByText('Prioritas EVP aktif')).toBeNull()
 expect(screen.getByText(/Ambulans.*Utara.*84%/)).toBeTruthy()
})
it('shows actual controller service and recovery after the vision target is gone',()=>{
 const control={...owned,emergency:target,emergency_serving:true}
 const view=render(<EmergencyPanel emergency={emergency} control={control}/>)
 expect(screen.getByText('Prioritas EVP aktif')).toBeTruthy()
 expect(screen.getByText(/Keputusan antrean ditangguhkan/)).toBeTruthy()
 view.rerender(<EmergencyPanel emergency={{...emergency,state:'recovering',target:null,focus:false}} control={{...control,emergency:null}}/>)
 expect(screen.getByText('Prioritas EVP aktif')).toBeTruthy()
 view.rerender(<EmergencyPanel emergency={{...emergency,state:'recovering',target:null,focus:false}} control={{...control,emergency:null,emergency_serving:false}}/>)
 expect(screen.getByText('Pemulihan kendali')).toBeTruthy()
})
it('does not imply EVP priority from a single prediction',()=>{
 render(<EmergencyPanel emergency={{...emergency,state:'confirming',target:null,focus:false,message:'Memverifikasi EVP'}} control={owned}/>)
 expect(screen.getByText(/satu prediksi belum cukup/)).toBeTruthy()
 expect(screen.queryByText('Prioritas EVP aktif')).toBeNull()
})
it('describes clearance while recovering instead of claiming normal control resumed',()=>{
 render(<EmergencyPanel emergency={{...emergency,state:'recovering',target:null,focus:false}} control={owned}/>)
 expect(screen.getByText(/Pengendali menyelesaikan kuning dan clearance/)).toBeTruthy()
 expect(screen.queryByText(/Kendali normal berjalan/)).toBeNull()
})