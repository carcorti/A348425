#!/usr/bin/env python3
"""A348425 missing-derived-file regressions. Carlo Corti.
Finite real checkpoints and hostile copies; not an official enumeration.
"""
import argparse,hashlib,json,os,resource,shutil,signal,subprocess,tempfile,time
from pathlib import Path
import verify
import oper
ROOT=Path(__file__).resolve().parents[1]
def digest_tree(d):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in d.iterdir()if p.is_file()}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--binary',type=Path,default=ROOT/'src/a348425');B=parser.parse_args().binary.resolve();events=[]
    with tempfile.TemporaryDirectory(prefix='a348425-recover-')as td:
        top=Path(td);lo,hi=5624,71159
        bases={}
        for n in [0,1,2,4]:
            d=top/('base'+str(n));verify.invoke(B,'init',d,lo,hi,16384,1,1)
            if n in [1,2]:
                with (top/'progress.log').open('w')as log:
                    p=subprocess.Popen([str(B),'next',str(d)],stdout=log,stderr=log);deadline=time.monotonic()+60;want=lo+n*16384
                    while True:
                        c=oper.cursor(d/'s0000.tsv')
                        if c is not None and c>=want:break
                        verify.need(p.poll()is None and time.monotonic()<deadline,'checkpoint capture deadline');time.sleep(.0002)
                    p.send_signal(signal.SIGSTOP);verify.need(oper.cursor(d/'s0000.tsv')==want,'exact partial checkpoint');p.kill();p.wait(timeout=60)
                verify.need(not(d/'s0000.sha256').exists(),'unsealed partial fixture')
            elif n==4:verify.invoke(B,'next',d)
            bases[n]=d
        complete,_=verify.records(bases[4],B);reference=(bases[4]/'hits.tsv').read_text().splitlines()[2:]
        for n,base in bases.items():
            for absent in [('index.tsv',),('hits.tsv',),('index.tsv','hits.tsv')]:
                d=top/('repair'+str(len(events)));shutil.copytree(base,d)
                before={p.name:p.read_bytes()for p in d.glob('s*.tsv')}
                for f in absent:(d/f).unlink()
                verify.invoke(B,'status',d,ok=2);verify.invoke(B,'verify',d,ok=2)
                for f,raw in before.items():verify.need((d/f).read_bytes()==raw,'read-only commands preserve authority')
                verify.invoke(B,'next',d);verify.invoke(B,'verify',d)
                verify.need((d/'hits.tsv').read_text().splitlines()[2:]==reference,'repair/resume exact ordered hit list')
                verify.records(d,B)
                if n==4:
                    for f,raw in before.items():verify.need((d/f).read_bytes()==raw,'complete sealed authority byte-preserved')
                events.append({'state_completed_blocks':n,'missing':absent,'status':2,'verify_before':2,'next':0,'verify_after':0,'hit_rows':len(reference)})
        # One absent aggregate must never hide a damaged surviving artifact.
        for absent,present in [('hits.tsv','index.tsv'),('index.tsv','hits.tsv')]:
            for kind in ['changed_header','changed_row','empty','extra_row','directory']:
                d=top/('reject'+str(len(events)));shutil.copytree(bases[4],d);(d/absent).unlink();p=d/present;raw=p.read_bytes()
                if kind=='changed_header':p.write_bytes(b'X'+raw[1:])
                elif kind=='changed_row':
                    z=raw.splitlines(True);verify.need(len(z)>2,'row fixture');z[2]=b'X'+z[2][1:];p.write_bytes(b''.join(z))
                elif kind=='empty':p.write_bytes(b'')
                elif kind=='extra_row':p.write_bytes(raw+b'extra\n')
                else:p.unlink();p.mkdir()
                before=digest_tree(d)
                for mode in ['status','verify','next']:verify.invoke(B,mode,d,ok=1)
                verify.need(before==digest_tree(d),'corruption refusal preserves bytes')
                events.append({'missing':absent,'survivor':kind,'all_commands':1})
        for bad in ['run.cfg','s0000.tsv','s0000.sha256']:
            d=top/('authority'+str(len(events)));shutil.copytree(bases[4],d);(d/'hits.tsv').unlink();p=d/bad;raw=p.read_bytes();p.write_bytes(b'X'+raw[1:])
            for mode in ['status','verify','next']:verify.invoke(B,mode,d,ok=1)
            events.append({'authority_corruption':bad,'missing':'hits.tsv','all_commands':1})
        d=top/'io';shutil.copytree(bases[4],d);(d/'hits.tsv').unlink();authority={p.name:p.read_bytes()for p in d.glob('s*')}
        def limit():
            signal.signal(signal.SIGXFSZ,signal.SIG_IGN);resource.setrlimit(resource.RLIMIT_FSIZE,(192,192))
        p=subprocess.run([str(B),'next',str(d)],capture_output=True,text=True,timeout=60,preexec_fn=limit)
        verify.need(p.returncode==1,'rebuild I/O failure');verify.need(all((d/k).read_bytes()==v for k,v in authority.items()),'failed rebuild retains authority')
        verify.invoke(B,'next',d);verify.invoke(B,'verify',d);verify.records(d,B)
        events.append({'rebuild_IO_fault_rc':p.returncode,'recovery':0})
    print(json.dumps({'author':'Carlo Corti','status':'PASS','binary_sha256':hashlib.sha256(B.read_bytes()).hexdigest(),'cases':events},indent=2))
if __name__=='__main__':main()
