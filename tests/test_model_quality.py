import hashlib,json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.app.model_quality import ModelQualityReader

def evidence(tmp_path):
 model=tmp_path/'best.pt';model.write_bytes(b'fixture-model-weights')
 metrics={'precision':.8,'recall':.7,'map50':.75,'map5095':.5}
 reports={k:{'per_class':{'ambulance':metrics},'overall':{}} for k in ('baseline_public','candidate_public','baseline_clip','candidate_clip')}
 reports['limitations']=['Same-clip temporal validation']
 (tmp_path/'evaluation.json').write_text(json.dumps(reports))
 (tmp_path/'model-card.json').write_text(json.dumps({'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest()}))
 return model

def test_reports_are_bound_to_model_and_missing_corrupt_or_nan_never_become_scores(tmp_path):
 path=tmp_path/'best.pt';reader=ModelQualityReader(path)
 assert not reader.snapshot().available
 evidence(tmp_path)
 assert reader.snapshot().reports['candidate_clip'].per_class['ambulance'].recall==.7
 first=reader.snapshot();first.reports.clear()
 assert reader.snapshot().reports # Cached result is not mutated by a caller.
 path.write_bytes(b'different-model')
 assert not reader.snapshot().available
 evidence(tmp_path)
 raw=json.loads((tmp_path/'evaluation.json').read_text());raw['candidate_clip']['per_class']['ambulance']['recall']=float('nan')
 (tmp_path/'evaluation.json').write_text(json.dumps(raw))
 assert not reader.snapshot().available
 (tmp_path/'evaluation.json').write_text('{broken')
 assert not reader.snapshot().available

def test_model_evaluation_requires_operator_session():
 app=create_app(Settings(_env_file=None))
 with TestClient(app) as client:
  assert client.get('/api/model-quality').status_code==401
