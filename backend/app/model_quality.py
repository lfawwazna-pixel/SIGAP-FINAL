"""Read a bounded, model-bound local report without importing Torch in the API."""
import hashlib, json
from pathlib import Path
from contracts.model_quality import ModelQuality, EvaluationSplit

class ModelQualityReader:
    def __init__(self,path):
        self.path=Path(path).resolve()
        self.cached_key,self.cached=None,None
    def snapshot(self):
        report=self.path.parent/'evaluation.json'
        card=self.path.parent/'model-card.json'
        try:
            paths=(self.path,report,card)
            key=tuple((p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
            if key==self.cached_key:return self.cached.model_copy(deep=True)
            if report.stat().st_size>2000000 or card.stat().st_size>50000:raise ValueError('report too large')
            raw=json.loads(report.read_text(encoding='utf-8'))
            meta=json.loads(card.read_text(encoding='utf-8'))
            checksum=hashlib.sha256(self.path.read_bytes()).hexdigest()
            if checksum!=meta.get('model_sha256'):raise ValueError('report does not match weights')
            names={'car','motorcycle','bus','truck','ambulance','fire_truck'}
            reports={}
            for name in ('baseline_public','candidate_public','baseline_clip','candidate_clip'):
                scores=raw[name]['per_class']
                if not scores or not set(scores)<=names:raise ValueError('class mismatch')
                reports[name]=EvaluationSplit(per_class=scores)
            value=ModelQuality(available=True,model_label=self.path.parent.name,model_sha256=checksum,
                reports=reports,limitations=raw.get('limitations',[]),
                message='Evaluasi tersimpan untuk bobot model yang sedang dikonfigurasi. Uji klip berasal dari rekaman yang sama dengan data tambahan.')
            self.cached_key,self.cached=key,value
            return value.model_copy(deep=True)
        except (OSError,ValueError,KeyError,TypeError):
            return ModelQuality(available=False,model_label=self.path.parent.name,
                message='Evaluasi yang cocok dengan bobot ini belum tersedia atau belum valid. Akurasi tidak ditampilkan sebagai nol.')
