import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { EmergencyPanel } from './EmergencyPanel'
import type { AdaptiveStatus } from './types/AdaptiveStatus'
import type { ControlStatus } from './types/ControlStatus'
const target={event_id:'U:source:tracker:7',direction:'U' as const,source_session:'00000000-0000-4000-8000-000000000001',track_id:7,kind:'ambulance' as const,confidence:.84,distance_to_stop:.2,observed_at:'2026-10-07T19:00:00Z'}
const emergency:AdaptiveStatus['emergency']={state:'confirmed',target,candidates:[target],focus:true,message:'EVP terkonfirmasi',events:[]}
afterEach(cleanup)
it('keeps confirmation separate from lamp priority until operator acquires control',()=>{
 render(<EmergencyPanel emergency={emergency} />)
 expect(screen.getByText('EVP terkonfirmasi')).toBeTruthy()
 expect(screen.getByText(/Aktifkan kendali SIGAP/)).toBeTruthy()
 expect(screen.getByText(/Ambulans.*Utara.*84%/)).toBeTruthy()
})
it('shows actual controller service and recovery even after the vision target is gone',()=>{
 const control={session_id:'active-session',emergency:target,emergency_serving:true} as ControlStatus
 const view=render(<EmergencyPanel emergency={emergency} control={control}/>)
 expect(screen.getByText('Prioritas EVP aktif')).toBeTruthy()
 expect(screen.getByText(/Keputusan antrean ditangguhkan/)).toBeTruthy()
 view.rerender(<EmergencyPanel emergency={{...emergency,state:'recovering',target:null,focus:false}} control={{...control,emergency:null}}/>)
 expect(screen.getByText('Prioritas EVP aktif')).toBeTruthy()
 view.rerender(<EmergencyPanel emergency={{...emergency,state:'recovering',target:null,focus:false}} control={{...control,emergency:null,emergency_serving:false}}/>)
 expect(screen.getByText('Pemulihan kendali')).toBeTruthy()
})
it('does not imply EVP priority from a single prediction',()=>{
 render(<EmergencyPanel emergency={{...emergency,state:'confirming',target:null,focus:false,message:'Memverifikasi EVP'}}/>)
 expect(screen.getByText(/satu prediksi belum cukup/)).toBeTruthy()
 expect(screen.queryByText('Prioritas EVP aktif')).toBeNull()
})

it('describes clearance while recovering instead of claiming normal control already resumed',()=>{
 render(<EmergencyPanel emergency={{...emergency,state:'recovering',target:null,focus:false}}/>)
 expect(screen.getByText(/Pengendali menyelesaikan kuning dan clearance/)).toBeTruthy()
 expect(screen.queryByText(/Kendali normal berjalan/)).toBeNull()
})
