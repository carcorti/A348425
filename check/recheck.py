#!/usr/bin/env python3
"""Reviewer-side recomputation (Claude, r02). Pure Python, no SymPy, no author code.
Usage: recheck.py BFILE AFILE TEX ZIPDIR"""
import sys, math, gzip, re, json
from collections import Counter, defaultdict

bpath, apath, texpath, zdir = sys.argv[1:5]

def primes_upto(n):
    s = bytearray([1]) * (n + 1); s[0] = s[1] = 0
    for i in range(2, int(n**0.5) + 1):
        if s[i]: s[i*i::i] = bytearray(len(s[i*i::i]))
    return [i for i in range(n + 1) if s[i]]
PR = primes_upto(2_000_000)

def fac(n):
    assert n >= 1
    f = Counter()
    for p in PR:
        if p * p > n: break
        while n % p == 0: f[p] += 1; n //= p
    if n > 1:
        assert n < PR[-1] ** 2, 'cofactor beyond certified trial bound'
        f[n] += 1
    return f

def Dm(n, f):  # derivative from a factorization
    return 0 if n < 2 else sum(e * (n // p) for p, e in f.items())

def D(n):
    return 0 if n < 2 else Dm(n, fac(n))

def sq(y):
    s = math.isqrt(y); return s * s == y

out = {}
raw = open(bpath, 'rb').read()
assert raw.endswith(b'\n\n') and not raw.endswith(b'\n\n\n') and b'\r' not in raw
rows = [tuple(map(int, l.split())) for l in raw.splitlines() if l]
assert [i for i, _ in rows] == list(range(1, 9115))
roots = [math.isqrt(n) for _, n in rows]
assert all(r * r == n for r, (_, n) in zip(roots, rows))
assert all(a < b for a, b in zip(roots, roots[1:]))
# positive arithmetic via merged multiset of 2 r D(r) (no root-reduction identity)
for r in roots:
    if r < 2: continue
    fr = fac(r); d = Dm(r, fr); fd = fac(d)
    fx = Counter({2: 1}) + fr + fd
    x = 2 * r * d
    assert math.prod(p**e for p, e in fx.items()) == x
    assert sq(Dm(x, fx)), r
out['positives_rechecked'] = len(roots)
out['endpoints'] = dict(a36=rows[35], a198=rows[197], a9114=rows[-1], r36=roots[35], r198=roots[197], r9114=roots[-1],
                        r33=roots[32], first_after_1e6=roots[197], prefix197_last=roots[196])
# a-file consistency
araw = open(apath, 'rb').read()
arows = [tuple(map(int, l.split())) for l in araw.splitlines() if l and not l.startswith(b'#')]
assert [(a[0], a[2]) for a in arows] == rows and all(a[1] == r for a, r in zip(arows, roots))
out['afile_equals_bfile'] = True
# structure
cat = Counter(); rates = Counter(); classes = defaultdict(list); powers = Counter(); inter = []
for i, r in enumerate(roots, 1):
    n = r * r
    if sq(2 * r * D(r)): inter.append(n)
    if r < 2: cat['01'] += 1; continue
    f = fac(r)
    m = math.prod(p ** (e % p) for p, e in f.items()); lam = sum(e // p for p, e in f.items())
    rates[lam] += 1
    if lam: classes[(m, lam)].append(r)
    if len(f) == 1:
        k = next(iter(f.values())); powers[k] += 1
        cat['prime' if k == 1 else 'pp'] += 1
    else:
        cat['mixed'] += 1
out['categories'] = dict(cat); out['rates'] = dict(sorted(rates.items())); out['pp_exponents'] = dict(sorted(powers.items()))
out['A266890_intersection_in_data'] = inter
inh = {(47, 1), (125, 1), (875, 1), (529, 2)}
part = Counter()
for r in roots:
    if r < 2: part['01'] += 1; continue
    f = fac(r)
    m = math.prod(p ** (e % p) for p, e in f.items()); lam = sum(e // p for p, e in f.items())
    if len(f) == 1 and next(iter(f.values())) <= 3: part['k123'] += 1
    elif (m, lam) in inh: part['inh'] += 1
    elif lam: part['otherpos'] += 1
    else: part['rest0'] += 1
out['partition'] = dict(part)
def C(m, lam):
    b = D(m) + lam * m; mb = m * b
    Dmb = Dm(mb, fac(m) + fac(b))
    return b, Dmb, 2 * Dmb + (4 * lam + 1) * mb
mine = {}
for (m, lam), mem in classes.items():
    b, Dmb, c = C(m, lam); assert sq(c)
    mine[(m, lam)] = (math.isqrt(c), len(mem))
out['classes'] = len(mine); out['class_members'] = sum(v[1] for v in mine.values())
out['inherited_cert'] = {f'{m},{l}': dict(zip(['b', 'Dmb', 'C'], C(m, l))) for m, l in sorted(inh)}
# compare to manuscript longtable
tex = open(texpath).read()
lt = tex[tex.index('\\endfoot'):tex.index('\\end{longtable}')]
tab = {}
for line in lt.splitlines():
    z = re.findall(r'\d+', line.replace('^{*}', ''))
    if len(z) == 4: tab[(int(z[0]), int(z[1]))] = (int(z[2]), int(z[3]))
out['longtable_rows'] = len(tab); out['longtable_matches'] = tab == mine
out['longtable_sum_h'] = sum(v[1] for v in tab.values())
out['longtable_sorted_by_m'] = list(tab) == sorted(tab)
# examples / bound
out['C96'] = C(9, 6); out['C1847'] = C(1847, 1)
w = 529 * 7**7 * 3**3; fw = fac(w); dw = Dm(w, fw); yw = Dm(2*w*dw, Counter({2:1}) + fw + fac(dw))
out['old_witness'] = dict(r=w, n=w * w, R=math.isqrt(yw), sq=sq(yw))
p = 10009802399
out['new_witness'] = dict(isprime=all(p % q for q in PR if q * q <= p), isqrtp=math.isqrt(p), p2=p * p,
                          Dp2=2*p, DDp2=Dm(2*p, Counter({2:1, p:1})), is100049sq=Dm(2*p, Counter({2:1, p:1})) == 100049**2)
out['parameter_counterexample'] = (5 * 599**2 - 6, fac(5 * 599**2 - 6))
out['examples'] = dict(D49=D(49), D14=D(14), D256=D(256), D1024=D(1024))
# providers, own derivative
def bf(name):
    return [tuple(map(int, l.split())) for l in gzip.decompress(open(f'{zdir}/more/{name}.gz', 'rb').read()).splitlines()
            if l.strip() and not l.startswith(b'#')]
rs = set(roots)
a871 = bf('b028871'); a873 = bf('b028873'); a787 = bf('b201787')
out['prov_028871'] = dict(rows=len(a871), row8889=a871[8888], mapped=sum(1 for _, q in a871 if q <= 10**10),
                          incl=all(q in rs for _, q in a871 if q <= 10**10))
m873 = [(s * s - 3)**2 for _, s in a873 if (s * s - 3)**2 <= 10**10]
m787 = [q**3 for _, q in a787 if q**3 <= 10**10]
out['prov_028873'] = dict(mapped=len(m873), incl=all(x in rs for x in m873))
out['prov_201787'] = dict(mapped=len(m787), incl=all(x in rs for x in m787))
pp = bf('b056798'); dd = bf('b192084')
cnt = 0; ok = True
for (i, n), (j, y) in zip(pp, dd):
    yy = D(D(n)); ok &= (i == j and yy == y)
    if sq(yy):
        cnt += 1; ok &= math.isqrt(n) in rs
out['paired'] = dict(rows=(len(pp), len(dd)), agree=ok, squares=cnt, last=pp[-1])
caps = [6500, 10**6, 10**7, 10**8, 10**9, 10**10]
out['counts_at_caps'] = {c: sum(r <= c for r in roots) for c in caps}
print(json.dumps(out, indent=1, default=str))
