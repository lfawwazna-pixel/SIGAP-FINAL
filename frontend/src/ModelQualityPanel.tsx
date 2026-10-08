import { useState } from 'react'
import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import schema from './schemas/ModelQuality.json'
import type { ModelQuality } from './types/ModelQuality'
import { useService } from './useService'
const ajv=new Ajv2020();addFormats(ajv)
const valid=ajv.compile<ModelQuality>(schema)
const names={car:'Mobil',motorcycle:'Motor',bus:'Bus',truck:'Truk',ambulance:'Ambulans',fire_truck:'Pemadam'}
const percent=(v:number|undefined)=>v===undefined?'—':(v*100).toFixed(1)+'%'
export function ModelQualityTable({data}:{data:ModelQuality|null}) {
 const [split,setSplit]=useState<'public'|'clip'>('public')
 const base=data?.reports['baseline_'+split]?.per_class
 const current=data?.reports['candidate_'+split]?.per_class
 return <details className="model-quality-panel"><summary>Mutu model · hasil evaluasi per kelas</summary>
 <div className="model-quality-content"><p className="eyebrow">{data?.model_label??'MEMERIKSA MODEL'}</p>
 <p>{data?.message??'Laporan model belum dapat dibaca. Tidak ada angka akurasi yang diasumsikan.'}</p>
 {data?.available&&<><label>Sumber uji <select value={split} onChange={e=>setSplit(e.target.value as 'public'|'clip')}><option value="public">Validasi publik terpisah</option><option value="clip">Blok waktu video ambulans</option></select></label>
 <p className="small-muted">Inference 640 · recall menunjukkan bagian objek berlabel yang ditemukan. Keyakinan satu deteksi berbeda dari akurasi model. Blok klip menguji rekaman yang sama; belum membuktikan kamera lain.</p>
 <div className="table-scroll"><table className="event-table" aria-label="Evaluasi deteksi per kelas"><thead><tr><th>Kelas</th><th>Precision baru</th><th>Recall baru</th><th>mAP50 lama</th><th>mAP50 baru</th><th>mAP50–95 baru</th></tr></thead><tbody>{Object.entries(names).map(([key,label])=><tr key={key}><th>{label}</th><td>{percent(current?.[key]?.precision)}</td><td>{percent(current?.[key]?.recall)}</td><td>{percent(base?.[key]?.map50)}</td><td>{percent(current?.[key]?.map50)}</td><td>{percent(current?.[key]?.map5095)}</td></tr>)}</tbody></table></div>
 <p className="small-muted">Evaluasi terikat SHA-256 {data.model_sha256?.slice(0,16)}…</p>
 <ul>{data.limitations.map(note=><li key={note}>{note}</li>)}</ul></>}
 </div></details>
}
export function ModelQualityPanel({active}:{active:boolean}) {
 const feed=useService('/model-quality',valid,active,60000)
 return <ModelQualityTable data={feed.data}/>
}
