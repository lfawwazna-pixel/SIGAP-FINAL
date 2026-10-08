import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { ModelQualityTable } from './ModelQualityPanel'
import type { ModelQuality } from './types/ModelQuality'
afterEach(cleanup)
it('keeps unavailable evaluation distinct from zero accuracy',()=>{
 render(<ModelQualityTable data={null}/>)
 expect(screen.getByText(/Tidak ada angka akurasi/)).toBeTruthy()
 expect(screen.queryByRole('table')).toBeNull()
})
it('compares per-class results and does not claim same-video validation is independent',()=>{
 const score={precision:.8,recall:.7,map50:.6,map5095:.4}
 const data:ModelQuality={available:true,model_label:'evp_v6',model_sha256:'a'.repeat(64),message:'Model valid',limitations:['Same recording'],reports:{baseline_public:{per_class:{ambulance:score}},candidate_public:{per_class:{ambulance:{...score,recall:.9}}},baseline_clip:{per_class:{ambulance:score}},candidate_clip:{per_class:{ambulance:{...score,recall:.95}}}}}
 render(<ModelQualityTable data={data}/>)
 fireEvent.click(screen.getByText('Mutu model · hasil evaluasi per kelas'))
 expect(screen.getByText(/belum membuktikan kamera lain/)).toBeTruthy()
 const row=within(screen.getByRole('table')).getAllByRole('row').find(r=>r.textContent?.includes('Ambulans'))!
 expect(row.textContent).toContain('90.0%')
 fireEvent.change(screen.getByLabelText('Sumber uji'),{target:{value:'clip'}})
 expect(row.textContent).toContain('95.0%')
})
