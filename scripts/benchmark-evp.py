"""Evaluate the exact SIGAP tracking worker on a whole clip (offline, not camera FPS)."""
import argparse,base64,json,subprocess,sys,time
from pathlib import Path
from uuid import uuid4

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--video',required=True);p.add_argument('--output',required=True);p.add_argument('--ffmpeg',required=True)
    args=p.parse_args();root=Path(__file__).resolve().parents[1];out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
    log=(out/'worker.log').open('wb')
    worker=subprocess.Popen([sys.executable,'-u','-m','vision.worker',str(Path(args.model).resolve())],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,**flags)
    decoder=subprocess.Popen([args.ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-threads','1','-filter_threads','1','-i',str(Path(args.video).resolve()),'-an','-vf','fps=5,scale=640:-2','-threads','1','-f','image2pipe','-c:v','mjpeg','-q:v','5','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,**flags)
    session=str(uuid4());buffer=b'';index=0;rows=[];began=time.perf_counter()
    try:
        while True:
            data=decoder.stdout.read(65536)
            if not data:break
            buffer+=data
            while True:
                start=buffer.find(b'\xff\xd8');end=buffer.find(b'\xff\xd9',max(0,start+2))
                if start<0 or end<0:break
                jpeg=buffer[start:end+2];buffer=buffer[end+2:];index+=1
                request=dict(direction='U',session=session,frame_id=index,fps=5,jpeg=base64.b64encode(jpeg).decode(),focus_evp=False)
                worker.stdin.write((json.dumps(request)+'\n').encode());worker.stdin.flush()
                result=json.loads(worker.stdout.readline());assert not result.get('error'),result
                assert (result['direction'],result['session'],result['frame_id'])==('U',session,index)
                rows.append(dict(frame_id=index,seconds=(index-1)/5,processing_ms=result['processing_ms'],tracks=result['tracks'],device=result['device']))
                if index in (301,401,476):
                    (out/f'preview-{(index-1)//5}s.jpg').write_bytes(base64.b64decode(result['jpeg']))
        assert decoder.wait(timeout=10)==0
        assert index>500,'Full clip was not processed'
        with (out/'tracks.jsonl').open('w') as f:
            for r in rows:f.write(json.dumps(r,separators=(',',':'))+'\n')
        warm=[r['processing_ms'] for r in rows[4:]];warm.sort()
        report=dict(frames=index,duration_seconds=index/5,device=rows[-1]['device'],wall_seconds=round(time.perf_counter()-began,3),warm_processing_mean_ms=round(sum(warm)/len(warm),3),warm_processing_p95_ms=round(warm[int((len(warm)-1)*.95)],3),offline_worker_fps=round(1000/(sum(warm)/len(warm)),2),note='One whole clip, exact decoder/worker; offline throughput is not four-camera delivered FPS.')
        (out/'benchmark.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    finally:
        decoder.kill() if decoder.poll() is None else None
        decoder.wait();decoder.stdout.close();worker.stdin.close()
        try:worker.wait(timeout=10)
        except subprocess.TimeoutExpired:worker.kill();worker.wait()
        worker.stdout.close();log.close()
if __name__=='__main__':main()
