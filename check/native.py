#!/usr/bin/env python3
"""Bounded C helper fixtures; shared producer code, NOT independent arithmetic.
Carlo Corti. Independent expected coordinates are generated via verify.py.
"""
from pathlib import Path
import hashlib,json,subprocess,tempfile
import verify
ROOT=Path(__file__).resolve().parents[1]
def main():
    source=ROOT/'src/a348425.c'
    body=r'''
#define main producer_main
#include "SOURCE"
#undef main
#include <assert.h>
int main(void) {
 assert(square_root(0)==0&&square_root(1)==1);
 uint64_t q=MAX_ROOT;u128 sq=(u128)q*q;
 assert(square_root(sq)==q&&square_root(sq-1)==q-1);
 assert(square_root(MAX_Y)==MAX_ROOT);
 assert(prime64(UINT64_C(18446744073709551557)));
 assert(!prime64(UINT64_C(341550071728321))&&!prime64(UINT64_MAX));
 bool fb=false;u128 check_d;
 assert(derivative64(10403,&check_d,&fb)&&check_d==204&&fb);
 fb=false;Hit edge;
 (void)gcd64(101,103);(void)rho_step(2,1,101);
 assert(predicate(0,0,&edge,&fb)==1&&edge.n==0&&edge.root==0);
 assert(predicate(1,0,&edge,&fb)==1&&edge.n==1&&edge.root==0);
 assert(predicate(5927,1,&edge,&fb)==1&&edge.y==5929&&edge.root==77);
 uint64_t roots[]={0,1,6500,CAP-1,CAP};
 for(size_t z=0;z<sizeof roots/sizeof *roots;++z) {
   uint64_t B=roots[z];
   uint64_t K=B/65536+1;
   uint64_t choices[]={1,K<512?K:512};
   for(unsigned k=0;k<2;++k) {
     Config c={.start=0,.end=B,.block=65536,.group=choices[k],.threads=16};
     uint64_t prev=0;
     for(uint64_t j=0;j<c.group;++j) {
       uint64_t lo,hi;seg_bounds(&c,j,&lo,&hi);
       assert(lo==prev&&lo<=hi&&hi<=B);prev=hi+1;
     }
     assert(prev==B+1);
   }
 }
 FIXTURES
 puts("native PASS: exact square/domain/partition/fallback/wide fixtures");return 0;
}
'''
    fixtures=[]
    for r in [0,1,5927,7919,8464,47*7**7,529*7**7*3**3]:
        w=verify.witness(r);verify.need(w is not None,'fixture positive')
        fixtures.append('{bool f=false;u128 d;Hit h;char b[40];assert(derivative64('+str(r)+',&d,&f)&&d<=MAX_D);assert(predicate('+str(r)+',(uint64_t)d,&h,&f)==1);fmt128(h.y,b);assert(!strcmp(b,"'+str(w[3])+'"));assert(verified_hit(&h));}')
    body=body.replace('SOURCE',str(source)).replace('FIXTURES','\n'.join(fixtures))
    with tempfile.TemporaryDirectory(prefix='a348425-native-')as td:
        p=Path(td);(p/'unit.c').write_text(body)
        flags=['gcc','-std=c17','-O2','-Wall','-Wextra','-Wpedantic','-Wshadow','-Wconversion','-Wdouble-promotion','-Wformat=2','-Werror','-fopenmp','-DA348425_FORCE_FALLBACK','-DA348425_SOURCE_SHA="fixture"','-DA348425_MAKE_SHA="fixture"',str(p/'unit.c'),'-lcrypto','-lm','-o',str(p/'unit')]
        built=subprocess.run(flags,capture_output=True,text=True,timeout=60)
        if built.returncode:raise SystemExit(built.stderr)
        v=subprocess.run([str(p/'unit')],check=True,capture_output=True,text=True,timeout=60)
        print(json.dumps({'status':'PASS','author':'Carlo Corti','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'shared-code helper fixtures; separate from release-executable end-to-end tests','stdout':v.stdout},indent=2))
if __name__=='__main__':main()
