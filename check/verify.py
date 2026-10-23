#!/usr/bin/env python3
"""A348425 independent arithmetic/state verifier and bounded regression runner.
Carlo Corti. Python standard library plus exactly tested SymPy 1.12.
No production-source import. Whole-run negative coverage is not re-enumerated.
"""
import argparse
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import select
import subprocess
import tempfile
import time
import sympy
ROOT=Path(__file__).resolve().parents[1]
CAP=10**12
PREFIX=[0,1,4,49,529,2209,6241,27889,28561,35344,49729,128881,192721,250000,431649,528529,703921,1181569,1495729,1610361,1868689,3411409,4870849,5755201,9138529,11390625,12250000,13830961,13845841,15737089,22648081,25391521,31618129,31640625,35129329]
BASE_SHA='76b36903020df4d889f3ce649de05c8eda9414e5be85afbbc87fcc4f7f0861b3'

def need(test,msg):
    if not test:raise ValueError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def num(s,bits=64):
    need(s.isascii()and s.isdecimal(),'integer grammar')
    v=int(s);need(v<2**bits,'integer width');return v
def lines(raw):
    need(raw.endswith(b'\n')and b'\r'not in raw and b'\0'not in raw,'framing')
    a=raw.decode('ascii').splitlines();need(all(len(x)<=255 for x in a),'record length');return a

def deriv(n,trial=False):
    if n<2:return 0
    if trial:
        rem=n;total=0;p=2
        while p<=rem//p:
            while rem%p==0:total+=n//p;rem//=p
            p=3 if p==2 else p+2
        return total+(n//rem if rem>1 else 0)
    fac=sympy.factorint(n)
    need(all(1<int(p)<2**64 and sympy.isprime(p)and e>0 for p,e in fac.items()),'uncertified factor domain')
    need(math.prod(int(p)**int(e)for p,e in fac.items())==n,'factor product')
    return sum(int(e)*(n//int(p))for p,e in fac.items())
def witness(r,trial=False):
    n=r*r;x=deriv(n,trial);y=deriv(x,trial);R=math.isqrt(y)
    return (r,n,x,y,R)if R*R==y else None

def config(run,binary):
    raw=(run/'run.cfg').read_bytes();a=lines(raw)
    keys=['start','end','block','group','threads','source_sha','makefile_sha','binary_sha']
    need(len(a)==9 and a[0]=='A348425-CFG-1','config schema')
    c={}
    for i,(k,line)in enumerate(zip(keys,a[1:],strict=True)):
        z=line.split('\t');need(len(z)==2 and z[0]==k,'config field')
        if i<5:c[k]=num(z[1])
        else:
            need(len(z[1])==64 and all(x in '0123456789abcdef'for x in z[1]),'hash grammar');c[k]=z[1]
    need(0<=c['start']<=c['end']<=CAP and c['block']in [16384,32768,65536]and 1<=c['threads']<=16,'config domain')
    K=(c['end']-c['start'])//c['block']+1
    need(1<=c['group']<=min(512,K),'segment domain')
    for path,key in [(binary,'binary_sha'),(binary.parent/'a348425.c','source_sha'),(binary.parent/'Makefile','makefile_sha')]:
        need(sha(path.read_bytes())==c[key],'bound artifact identity')
    return c,sha(raw)
def bounds(c,j):
    K=(c['end']-c['start'])//c['block']+1;S=c['group'];rest=K-S;den=S*(5*S+1)
    def first(k):return k+rest*k*(6*S+1-k)//den
    return c['start']+first(j)*c['block'],min(c['end'],c['start']+first(j+1)*c['block']-1)

def records(run,binary,complete=True,positive=True):
    c,cfgsha=config(run,binary);hits=[];manifest=[];expected={'run.cfg','index.tsv','hits.tsv'};cursor=c['start']
    for j in range(c['group']):
        stem=f's{j:04x}';p=run/(stem+'.tsv')
        if not p.exists():break
        raw=p.read_bytes();need(len(raw)>=75 and raw[-75:-65]==b'state_sha\t','footer')
        need(raw[-65:-1].decode()==sha(raw[:-75]),'state digest')
        z=lines(raw[:-75]);need(z[0]=='A348425-SEG-1','segment schema')
        lo,hi=bounds(c,j);need(lo==cursor,'coverage join')
        need(z[1:5]==['cfg_sha\t'+cfgsha,'id\t'+f'{j:04x}','low\t'+str(lo),'high\t'+str(hi)],'segment metadata')
        values=[]
        for key,row in zip(['next','elapsed_ns','hits'],z[5:8],strict=True):
            pair=row.split('\t');need(len(pair)==2 and pair[0]==key,'state field');values.append(num(pair[1]))
        nxt,elapsed,count=values;need(lo<=nxt<=hi+1 and(nxt==hi+1 or(nxt-lo)%c['block']==0),'next cursor')
        need(len(z)==8+count and count<=nxt-lo,'hit count')
        found=[]
        for row in z[8:]:
            f=row.split('\t');need(len(f)==5,'hit shape');h=tuple(num(x,64 if i in [0,4]else 128)for i,x in enumerate(f))
            need(lo<=h[0]<nxt and h[1]==h[0]**2 and h[3]==h[4]**2,'hit semantics')
            need(not found or h[0]>found[-1][0],'hit order')
            if positive:need(witness(h[0])==h,'independent positive')
            found.append(h)
        expected.add(stem+'.tsv');seal=run/(stem+'.sha256')
        if not seal.exists():
            need(not complete,'incomplete seal');break
        need(nxt==hi+1 and seal.read_text()==sha(raw)+'\n','seal')
        expected.add(stem+'.sha256');cursor=nxt;hits+=found
        manifest.append(f'{j:04x}\t{lo}\t{hi}\t{sha(raw)}\t{elapsed}\t{count}')
    if complete:need(cursor==c['end']+1,'incomplete target')
    need(set(p.name for p in run.iterdir())==expected,'unexpected run payload')
    need(lines((run/'index.tsv').read_bytes())==['A348425-MANIFEST-1\tcfg_sha='+cfgsha,'id\tlow\thigh\tstate_sha\telapsed_ns\thits']+manifest,'aggregate index')
    need(lines((run/'hits.tsv').read_bytes())==['A348425-HITS-1\tcfg_sha='+cfgsha,'r\tn\tx\ty\tR']+['\t'.join(map(str,h))for h in hits],'aggregate hits')
    return c,hits

def invoke(binary,*args,ok=0):
    p=subprocess.run([str(binary),*map(str,args)],capture_output=True,text=True,timeout=60)
    need(p.returncode==ok,f'CLI {args}: {p.returncode} expected{ok}: {p.stderr[-500:]}')
    return p

def regression(binary):
    events=[]
    with tempfile.TemporaryDirectory(prefix='a348425-')as td:
        tmp=Path(td)
        def run(name,low,high,block,groups,threads):
            out=tmp/name;invoke(binary,'init',out,low,high,block,groups,threads)
            for _ in range(groups):invoke(binary,'next',out)
            invoke(binary,'verify',out);c,h=records(out,binary);return out,h
        _,known=run('known',0,6500,16384,1,1)
        need([h[1]for h in known]==PREFIX,'known35 positives/complete bounded census')
        exact=[w for r in range(5624,6501)if(w:=witness(r,True))]
        _,window=run('window',5624,6500,16384,1,16);need(window==exact,'877 direct-trial window')
        events.append({'id':'known','positive_count':len(known),'complete_trial_roots':877,'new_index_claims':False})
        _,whole=run('whole',934465,1000000,16384,1,1)
        parted,split=run('parted',934465,1000000,16384,4,16)
        need(whole==split and any(whole),'partition/thread positive-path equivalence')
        expected=[w for r in range(999001,1000001)if(w:=witness(r,True))]
        need(expected==[h for h in split if h[0]>=999001],'1000-root complete high trial oracle')
        events.append({'id':'part','roots':65536,'oracle_roots':1000,'hits':len(split)})
        # First/no/one/multiple/complete checkpoint states with nonzero lower bound.
        out=tmp/'resume';invoke(binary,'init',out,934465,1000000,16384,1,16)
        status=invoke(binary,'status',out).stdout;need('committed_next=934465'in status,'empty nonzero cursor')
        invoke(binary,'verify',out,ok=2)
        # Valid predecessor snapshots from the real producer's first checkpoints.
        # External signal simulates interruption; no artificial state frontier.
        p=subprocess.Popen([str(binary),'next',str(out)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ready,_,_=select.select([p.stderr],[],[],60)
        need(bool(ready),"producer START deadline")
        first=p.stderr.readline();need(first.startswith("START"),"producer entered arithmetic path")
        p.send_signal(signal.SIGINT);stdout,stderr=p.communicate(timeout=60);stderr=first+stderr
        need(p.returncode in [0,2],'interrupt status')
        invoke(binary,'next',out);invoke(binary,'verify',out);_,recovered=records(out,binary)
        need(recovered==whole,'SIGINT resume equality')
        events.append({'id':'resume','signal_exit':p.returncode,'stderr':stderr[-1500:]})
        # Concurrent invocation refuses a lock held on the actual config inode.
        with (out/'run.cfg').open()as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            invoke(binary,'next',out,ok=1)
        # Hash-valid short aggregate prefixes are repaired from sealed authority.
        original=(parted/'hits.tsv').read_bytes();(parted/'hits.tsv').write_bytes(b'\n'.join(original.split(b'\n')[:2])+b'\n')
        invoke(binary,'status',parted,ok=2);invoke(binary,'next',parted);records(parted,binary)
        # Tampered data, seals, payload and input grammar must fail closed.
        for filename in ['s0000.tsv','s0000.sha256','index.tsv','hits.tsv','run.cfg']:
            out=tmp/('bad'+str(len(events)));shutil.copytree(parted,out);p=out/filename;b=p.read_bytes();p.write_bytes(b[:-2]+b'X\n')
            invoke(binary,'verify',out,ok=1);events.append({'id':'corrupt','file':filename})
        foreign=tmp/'foreign';shutil.copytree(parted,foreign);(foreign/'unknown').write_text('x');invoke(binary,'verify',foreign,ok=1)
        invoke(binary,'init',parted,0,1,16384,1,1,ok=1)
        for lo,hi,block,groups,threads in [('-1',1,16384,1,1),(0,CAP+1,16384,1,1),(2,1,16384,1,1),(0,1,0,1,1),(0,1,16385,1,1),(0,1,16384,2,1),(0,1,16384,1,17),(0,1,16384,1,0),('1x',1,16384,1,1)]:
            invoke(binary,'init',tmp/'invalid',lo,hi,block,groups,threads,ok=1)
        events.append({'id':'CLI','invalid_cases':9,'lock_and_no_clobber':True})
        # True high-scale two-eigenvalue family, including u128 output.
        r=529*7**7*3**3;need(r<=CAP,'high positive capacity');expected=witness(r)
        need(expected is not None and expected[1]>2**64,'wide positive fixture')
        _,found=run('wide',r,r,16384,1,16);need(found==[expected],'wide hit serialization/aggregation')
        for r in [CAP-1,CAP]:
            _,found=run('edge'+str(r%2),r,r,65536,1,16)
            expected=witness(r);need(found==([expected]if expected else[]),'capacity edge predicate')
        events.append({'id':'wide','r':529*7**7*3**3,'n':str((529*7**7*3**3)**2),'cap_edges':[CAP-1,CAP]})
    return events

def main():
    need(sympy.__version__=='1.12','tested SymPy1.12 required')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,default=ROOT/'src/a348425');p.add_argument('--run',type=Path);p.add_argument('--low',type=int);p.add_argument('--high',type=int);a=p.parse_args();binary=a.binary.resolve()
    base=(ROOT/'data/b348425.txt').read_bytes();need(base.endswith(b'\n\n')and not base.endswith(b'\n\n\n'),'canonical b framing')
    values=[tuple(map(int,line.split()))for line in base.splitlines()if line]
    need(values[:35]==list(enumerate(PREFIX,1)),'admitted indexed common prefix')
    need([i for i,n in values]==list(range(1,len(values)+1)),'canonical index continuity')
    need(all(n>=0 and math.isqrt(n)**2==n for i,n in values),'canonical square values')
    need(all(values[j][1]<values[j+1][1]for j in range(len(values)-1)),'canonical order')
    for i,n in values[35:]:need(witness(math.isqrt(n))is not None,'canonical positive arithmetic')
    need(sha((''.join(f'{i} {n}\n'for i,n in values[:35])+'\n').encode())==BASE_SHA,'35-row fixture identity')
    result={'author':'Carlo Corti','status':'PASS','canonical_rows':len(values),'sympy':sympy.__version__,'binary_sha256':sha(binary.read_bytes()),'scope':'bounded independent tests; sealed-record audit is not independent global enumeration'}
    if a.run:
        c,h=records(a.run,binary);result['recorded_range']=[c['start'],c['end']];result['positive_rows']=len(h)
        need((a.low is None)==(a.high is None),'both oracle endpoints')
        if a.low is not None:
            need(c['start']<=a.low<=a.high<=c['end']and a.high-a.low<10000,'bounded oracle window')
            trial=a.high<=1000000
            expected=[w for r in range(a.low,a.high+1)if(w:=witness(r,trial))]
            need(expected==[v for v in h if a.low<=v[0]<=a.high],'complete independent window')
            result['independent_roots']=a.high-a.low+1
    else:
        need(a.low is None and a.high is None,'window requires run');result['tests']=regression(binary)
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.TimeoutExpired)as e:raise SystemExit('FAIL: '+str(e))
