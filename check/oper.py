#!/usr/bin/env python3
"""Release-executable checkpoint/crash/I/O fixtures. Carlo Corti.
No new indexed claims; finite high-root intervals only.
"""
import argparse,hashlib,json,os,resource,signal,subprocess,tempfile,time
from pathlib import Path
import verify
ROOT=Path(__file__).resolve().parents[1]
def cursor(path):
    if not path.exists():return None
    raw=path.read_bytes()
    if raw[-75:-65]!=b'state_sha\t'or hashlib.sha256(raw[:-75]).hexdigest().encode()!=raw[-65:-1]:return None
    for row in raw.splitlines():
        if row.startswith(b'next\t'):return int(row.split(b'\t')[1])
def main():
    a=argparse.ArgumentParser();a.add_argument('--binary',type=Path,default=ROOT/'src/a348425');binary=a.parse_args().binary.resolve();events=[]
    with tempfile.TemporaryDirectory(prefix='a348425-oper-')as td:
        root=Path(td);lo=10**12-4*65536+1;hi=10**12
        for n in [1,2]:
            out=root/str(n);verify.invoke(binary,'init',out,lo,hi,65536,1,16)
            with (root/'log').open('w')as log:
                p=subprocess.Popen([str(binary),'next',str(out)],stdout=log,stderr=log)
                deadline=time.monotonic()+60;wanted=lo+n*65536
                while True:
                    value=cursor(out/'s0000.tsv')
                    if value is not None and value>=wanted:break
                    verify.need(p.poll()is None and time.monotonic()<deadline,'checkpoint deadline')
                    time.sleep(.0002)
                p.send_signal(signal.SIGSTOP)
                frozen=cursor(out/'s0000.tsv');verify.need(frozen==wanted,'exact checkpoint capture')
                p.kill();p.wait(timeout=60)
            status=verify.invoke(binary,'status',out).stdout
            verify.need(f'committed_next={wanted}'in status,'saved cursor truth')
            verify.invoke(binary,'verify',out,ok=2)
            verify.invoke(binary,'next',out);verify.invoke(binary,'verify',out)
            c,h=verify.records(out,binary)
            events.append({'state':'one block'if n==1 else'multiple blocks','completed_roots':wanted-lo,'killed_returncode':p.returncode,'after_resume':hi+1,'hits':len(h)})
        out=root/'io';verify.invoke(binary,'init',out,lo,lo+65535,65536,1,16)
        def limit():
            signal.signal(signal.SIGXFSZ,signal.SIG_IGN);resource.setrlimit(resource.RLIMIT_FSIZE,(192,192))
        p=subprocess.run([str(binary),'next',str(out)],capture_output=True,text=True,timeout=60,preexec_fn=limit)
        verify.need(p.returncode!=0 and not(out/'s0000.sha256').exists(),'failed write cannot seal')
        verify.need('committed_next='+str(lo)in verify.invoke(binary,'status',out).stdout,'failed checkpoint cannot advance')
        verify.invoke(binary,'next',out);verify.invoke(binary,'verify',out);verify.records(out,binary)
        events.append({'state':'write failure','returncode':p.returncode,'stderr':p.stderr,'resume':'PASS; stale own temporary cleaned under lock'})
    print(json.dumps({'author':'Carlo Corti','status':'PASS','binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'events':events},indent=2))
if __name__=='__main__':main()
